"""
Celery Worker Tasks for Background Processing
- Fully Windows-compatible (async + eventlet)
- Integrated email & OTP sending
- Memory lifecycle, embeddings, distillation, and fact extraction
- Robust logging and error handling
"""

import os
import json
import asyncio
import logging
from datetime import datetime, timedelta
from bson import ObjectId
from celery import Celery, shared_task
from app.config import settings
from app.database import db_client, get_memories_collection
from app.services import (
    ai_service,
    memory_store,
    profile_service,
    deterministic_extractor,
    pinecone_service,
)
from app.services.neo4j_service import neo4j_sync_service
from app.services.redis_service import redis_client as _redis_client
from app.services.pinecone_service import upsert_memory_embedding
from app.utils import email_utils

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# --- Eventlet patching for Windows Celery worker ---
if os.environ.get("CELERY_WORKER") and os.environ.get("CELERY_USE_EVENTLET") == "1":
    try:
        import importlib
        _eventlet_spec = importlib.util.find_spec("eventlet")
        if _eventlet_spec:
            _eventlet = importlib.import_module("eventlet")
            _eventlet.monkey_patch()
    except Exception as e:
        logger.warning(f"Eventlet patching failed: {e}")


# --- Helper: Fire-and-forget coroutine ---
def _fire_and_forget(coro):
    """Run async coroutine safely from sync context."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        asyncio.run(coro)
    else:
        return loop.create_task(coro)


# --- Celery configuration ---
celery_app = Celery(
    "maya_tasks",
    broker=f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}",
    backend=f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}",
    include=['app.celery_worker'],
)
celery_app.conf.timezone = "UTC"

# Connect Neo4j if in worker
if os.environ.get("CELERY_WORKER"):
    try:
        neo4j_sync_service.connect()
    except Exception as e:
        logger.error(f"Neo4j sync connect failed: {e}")


# --- Periodic tasks setup ---
@celery_app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    sender.add_periodic_task(600.0, heartbeat.s(), name="worker_heartbeat")
    sender.add_periodic_task(15.0, drain_embedding_queue.s(), name="drain_embedding_queue_15s")
    sender.add_periodic_task(21600.0, update_memory_salience.s(), name="update_memory_salience_6h")
    sender.add_periodic_task(43200.0, lifecycle_maintenance.s(), name="memory_lifecycle_12h")
    sender.add_periodic_task(86400.0, distillation_scan.s(), name="memory_distillation_scan_24h")
    sender.add_periodic_task(60.0, reminder_sweep.s(), name="reminder_sweep_60s")
    logger.info("Periodic tasks configured successfully.")


# --- Heartbeat task ---
@celery_app.task(name="heartbeat")
def heartbeat():
    logger.info("Celery worker heartbeat - scheduler active")


# --- Audit logging ---
@celery_app.task(name="audit_log")
def audit_log(event: str, payload: dict | None = None, **kwargs):
    try:
        parts = []
        if payload:
            parts.extend(f"{k}={payload[k]}" for k in payload)
        if kwargs:
            parts.extend(f"{k}={kwargs[k]}" for k in kwargs)
        suffix = " " + " ".join(parts) if parts else ""
        logger.info(f"[Audit] {event}{suffix}")
    except Exception:
        logger.info(f"[Audit] {event}")


# --- Reminder sweep with async email sending ---
@celery_app.task(name="reminder_sweep")
def reminder_sweep(window_seconds: int = 60):
    try:
        db = db_client
        if not db.healthy():
            return

        tasks = db.get_tasks_collection()
        notifications = db.get_notifications_collection()
        profiles = db.get_user_profile_collection()
        now = datetime.utcnow()
        window_start = now - timedelta(seconds=window_seconds)

        query = {
            "due_date": {"$gte": window_start, "$lte": now},
            "status": {"$in": ["todo", "pending"]},
        }

        for t in tasks.find(query).limit(200):
            try:
                user_id = t.get("user_id")
                title = t.get("title", "Reminder")
                notes = t.get("description")
                channel = t.get("notify_channel") or "email"
                last_sent = t.get("last_sent_at")
                if last_sent and isinstance(last_sent, str):
                    try:
                        last_sent = datetime.fromisoformat(last_sent)
                    except Exception:
                        last_sent = None
                if last_sent and (now - last_sent).total_seconds() < window_seconds:
                    continue

                # Create notification in DB
                notif = {
                    "_id": str(ObjectId()),
                    "user_id": str(user_id),
                    "title": "Reminder",
                    "message": f"It's time: {title}",
                    "type": "info",
                    "action_url": None,
                    "read": False,
                    "created_at": now,
                }
                try:
                    notifications.insert_one(notif)
                except Exception:
                    pass

                # Send email asynchronously
                if channel in ("email", "both"):
                    try:
                        profile = profiles.find_one({"user_id": str(user_id)}) or {}
                        to_email = profile.get("email") or profile.get("user_email") or t.get("email")
                        if to_email:
                            due_dt = t.get("due_date")
                            pretty_time = str(due_dt)
                            try:
                                aware = due_dt.replace(tzinfo=datetime.timezone.utc) if due_dt and due_dt.tzinfo is None else due_dt
                                tzname = profile.get("timezone") or "UTC"
                                try:
                                    from zoneinfo import ZoneInfo
                                    local_dt = aware.astimezone(ZoneInfo(tzname)) if aware else None
                                    pretty_time = local_dt.strftime("%Y-%m-%d %H:%M %Z") if local_dt else str(due_dt)
                                except Exception:
                                    pretty_time = aware.strftime("%Y-%m-%d %H:%M UTC") if aware else str(due_dt)
                            except Exception:
                                pass

                            subject = f"Reminder: {title}"
                            body = (
                                "Hi there,\n\n"
                                f"This is a friendly reminder for your scheduled task:\n\n"
                                f"Title: {title}\n"
                                f"Time: {pretty_time}\n"
                                f"Details: {notes or 'No additional details provided.'}\n\n"
                                "Stay productive,\nYour Personal AI Assistant"
                            )
                            html_body = f"""
                            <html>
                              <body>
                                <p>Hi there,</p>
                                <p>This is a friendly reminder for your scheduled task:</p>
                                <p><strong>Title:</strong> {title}<br>
                                   <strong>Time:</strong> {pretty_time}<br>
                                   <strong>Details:</strong> {notes or 'No additional details provided.'}</p>
                                <p>Stay productive,<br>Your Personal AI Assistant</p>
                              </body>
                            </html>
                            """
                            # Async send email via Celery
                            send_email_task.delay(to_email, subject, body, html_body)
                    except Exception:
                        pass

                # Update task sent info
                tasks.update_one({"_id": t.get("_id")}, {"$set": {"last_sent_at": now}, "$inc": {"sent_count": 1}})
            except Exception:
                continue
    except Exception as e:
        logger.exception(f"Reminder sweep failed: {e}")


# --- Celery Email Tasks ---
@shared_task(name="send_email_task", autoretry_for=(email_utils.EmailSendError,), retry_kwargs={"max_retries":3, "countdown":10})
def send_email_task(recipient: str, subject: str, body: str, html: str = None):
    email_utils.send_email(recipient, subject, body, html)


@shared_task(name="send_otp_email_task", autoretry_for=(email_utils.EmailSendError,), retry_kwargs={"max_retries":3, "countdown":5})
def send_otp_email_task(to_email: str, otp_code: str):
    email_utils.send_otp_email(to_email, otp_code)


# --- Memory Salience Update ---
@celery_app.task(name="update_memory_salience")
def update_memory_salience():
    if not _redis_client:
        return
    try:
        mem_coll = get_memories_collection()
        cursor = 0
        counts = {}
        pattern = "user:*:memory_freq:*"
        while True:
            cursor, keys = _redis_client.scan(cursor=cursor, match=pattern, count=500)
            for k in keys:
                try:
                    val = int(_redis_client.get(k) or 0)
                    if val <= 0:
                        continue
                    parts = k.split(":")
                    if len(parts) >= 4:
                        uid = parts[1]
                        mid = parts[-1]
                        counts.setdefault(uid, {})[mid] = val
                except Exception:
                    continue
            if cursor == 0:
                break

        import math
        for uid, mem_map in counts.items():
            if not mem_map:
                continue
            max_freq = max(mem_map.values()) or 1
            bulk_ops = []
            for mid, freq in mem_map.items():
                norm = math.log(1 + freq) / math.log(1 + max_freq)
                salience = 0.8 + norm * 0.45
                try:
                    bulk_ops.append({
                        "filter": {"_id": ObjectId(mid), "user_id": uid},
                        "update": {"$set": {"salience_score": round(salience, 4), "updated_at": datetime.utcnow().isoformat()}},
                    })
                except Exception:
                    continue
            for op in bulk_ops:
                try:
                    mem_coll.update_one(op["filter"], op["update"])
                except Exception:
                    pass

        # Clear frequency counters in Redis
        for uid, mem_map in counts.items():
            for mid in mem_map:
                try:
                    _redis_client.delete(f"user:{uid}:memory_freq:{mid}")
                except Exception:
                    pass

        logger.info(f"Salience update complete for {sum(len(m) for m in counts.values())} memories across {len(counts)} users")
    except Exception as e:
        logger.exception(f"Salience update failed: {e}")


# --- Lifecycle Maintenance ---
@celery_app.task(name="memory_lifecycle_maintenance")
def lifecycle_maintenance():
    try:
        mem_coll = get_memories_collection()
        now = datetime.utcnow()
        iso_now = now.isoformat()
        thirty_days_ago = (now - timedelta(days=30)).isoformat()
        sixty_days_ago = (now - timedelta(days=60)).isoformat()
        undo_expiry = (now + timedelta(days=30)).isoformat()

        # Aging stage
        aging_candidates = mem_coll.find({
            "lifecycle_state": "active",
            "$or": [
                {"last_accessed_at": {"$lt": thirty_days_ago}},
                {"salience_score": {"$lt": 0.9}},
            ],
            "user_flags.pinned": {"$ne": True},
        }).limit(500)

        moved_aging = 0
        for doc in aging_candidates:
            try:
                mem_coll.update_one({"_id": doc["_id"]}, {"$set": {"lifecycle_state": "aging", "updated_at": iso_now, "aging_at": iso_now}})
                moved_aging += 1
            except Exception:
                continue

        # Archival stage
        aging_to_archive = mem_coll.find({
            "lifecycle_state": "aging",
            "last_accessed_at": {"$lt": sixty_days_ago},
            "salience_score": {"$lt": 0.95},
        }).limit(500)

        archived = 0
        for doc in aging_to_archive:
            try:
                mem_coll.update_one({"_id": doc["_id"]}, {"$set": {"lifecycle_state": "archived", "archived_at": iso_now, "undo_expiry_at": undo_expiry, "updated_at": iso_now}})
                archived += 1
            except Exception:
                continue

        if moved_aging or archived:
            logger.info(f"Lifecycle maintenance: moved {moved_aging} -> aging, archived {archived}")
    except Exception as e:
        logger.exception(f"Lifecycle maintenance failed: {e}")


# --- Distillation Scan ---
@celery_app.task(name="distillation_scan")
def distillation_scan(batch_limit_per_user: int = 30, max_users: int = 200):
    try:
        mem_coll = get_memories_collection()
        pipeline = [
            {"$match": {
                "lifecycle_state": {"$in": ["aging", "archived"]},
                "salience_score": {"$lte": 0.93},
                "type": {"$ne": "distilled"},
                "lineage.distilled_id": {"$exists": False},
            }},
            {"$group": {"_id": "$user_id", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": max_users},
        ]
        user_groups = list(mem_coll.aggregate(pipeline))
        created_total = 0

        from app.services import memory_service as ms
        global_cap = getattr(settings, "DISTILLATION_SCAN_GLOBAL_CAP", 25)
        per_user_cap = getattr(settings, "DISTILLATION_SCAN_PER_USER_CAP", 2)
        group_size = getattr(settings, "DISTILLATION_GROUP_SIZE", 8)

        if global_cap <= 0 or per_user_cap <= 0:
            logger.info("Distillation scan skipped (caps disabled)")
            return

        for ug in user_groups:
            if created_total >= global_cap:
                break
            uid = ug.get("_id")
            if not uid:
                continue
            remaining_for_user = per_user_cap
            cands = asyncio.run(ms.get_distillation_candidates(uid, limit=batch_limit_per_user))
            if not cands:
                continue
            start = 0
            while start < len(cands) and remaining_for_user > 0 and created_total < global_cap:
                chunk = cands[start:start+group_size]
                start += group_size
                ids = [c.get("_id") for c in chunk if c.get("_id")]
                if not ids:
                    continue
                result = asyncio.run(ms.run_distillation_batch(uid, ids))
                if result.get("created"):
                    created_total += 1
                    remaining_for_user -= 1

        if created_total:
            logger.info(f"Distillation scan created {created_total} distilled memories (global cap {global_cap})")
    except Exception as e:
        logger.exception(f"Distillation scan failed: {e}")


# --- Re-embed Outdated Memories ---
@celery_app.task(name="reembed_outdated_memories")
def reembed_outdated_memories(batch_size: int = 300):
    try:
        target_version = settings.EMBEDDING_MODEL_VERSION
        coll = get_memories_collection()
        outdated = coll.find({"model_version": {"$ne": target_version}}, projection=["_id", "title", "value", "lifecycle_state", "user_id"], limit=batch_size)
        count = 0
        for doc in outdated:
            try:
                text = f"{doc.get('title')}: {doc.get('value','')}"
                upsert_memory_embedding(str(doc["_id"]), doc.get("user_id"), text, doc.get("lifecycle_state", "active"))
                coll.update_one({"_id": doc["_id"]}, {"$set": {"model_version": target_version, "updated_at": datetime.utcnow().isoformat()}})
                count += 1
            except Exception:
                continue
        if count:
            logger.info(f"Re-embedded {count} outdated memories -> version {target_version}")
    except Exception as e:
        logger.exception(f"Re-embed task failed: {e}")


# --- Fire-and-forget Embedding Queue ---
@celery_app.task(name="drain_embedding_queue")
def drain_embedding_queue(max_items: int = 40):
    async def _inner():
        try:
            batch = await memory_store.dequeue_embedding_batch(max_items=max_items)
            if batch:
                store_embeddings_batch.delay(batch)
        except Exception:
            logger.exception("Failed draining embedding queue")
    _fire_and_forget(_inner())


@celery_app.task(name="store_embeddings_batch")
def store_embeddings_batch(batch: list[dict]):
    try:
        pinecone_service.initialize_pinecone()
        pinecone_service.bulk_upsert(batch)
    except Exception:
        logger.exception("Failed batch embedding upsert")


# --- Extract & Store Facts ---
@celery_app.task(
    name="extract_and_store_facts",
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 3, "countdown": 10},
    retry_backoff=True
)
def extract_and_store_facts_task(user_message: str, assistant_message: str, user_id: str):
    try:
        transcript = f"Human: {user_message}\nAssistant: {assistant_message}"
        neo4j_sync_service.connect()
        det = deterministic_extractor.extract(user_message, assistant_message)

        if det.get("profile_update"):
            try:
                profile_service.merge_update(user_id, **det["profile_update"])
            except Exception:
                logger.exception("Profile merge_update failed")

        # Preferences
        for pref in det.get("preferences", []) or []:
            if pref.get("type") == "hobby" and pref.get("value"):
                try:
                    neo4j_sync_service.upsert_user_preference_sync(user_id, pref["value"], "HOBBY")
                except Exception:
                    logger.debug("Failed preference upserts")

        # Friend locations
        for fl in det.get("friend_locations", []) or []:
            friend = fl.get("friend")
            city = fl.get("city")
            if friend and city:
                try:
                    neo4j_sync_service.upsert_friend_location_sync(user_id, friend, city)
                except Exception:
                    logger.debug("Failed friend location upserts")

        # Semantic facts enqueue
        semantic_facts = det.get("semantic_facts", []) or []
        if semantic_facts:
            try:
                ts = datetime.utcnow().isoformat()
                for fact in semantic_facts:
                    payload = {"user_id": user_id, "session_id": "", "text": fact, "role": "fact", "timestamp": ts, "kind": "user_fact"}
                    _fire_and_forget(memory_store.enqueue_embedding_job(payload))
            except Exception:
                logger.exception("Failed to enqueue semantic facts")

        # AI service extraction
        facts_data = ai_service.extract_facts_from_text(transcript)
        entities, relationships = [], []
        parsed = None
        if facts_data:
            if isinstance(facts_data, str):
                try:
                    parsed = json.loads(facts_data)
                except json.JSONDecodeError:
                    logger.error("AI returned invalid JSON for facts")
            elif isinstance(facts_data, dict):
                parsed = facts_data
            if parsed:
                entities = parsed.get("entities", []) if isinstance(parsed.get("entities"), list) else []
                relationships = parsed.get("relationships", []) if isinstance(parsed.get("relationships"), list) else []

        valid_entities = [e for e in entities if isinstance(e, dict) and e.get("name")]
        user_node_name = f"User_{user_id}"
        valid_entities.append({"name": user_node_name, "label": "User", "id": user_id})
        person_entity = next((e for e in valid_entities if e.get("label") == "PERSON"), None)
        if person_entity:
            relationships.append({"source": user_node_name, "target": person_entity["name"], "type": "IS_NAMED"})
            try:
                neo4j_sync_service.run_query(f"MERGE (u:User {{id: '{user_id}'}})")
            except Exception:
                logger.debug("Failed to merge user node in Neo4j")
    except Exception as e:
        logger.exception(f"Fact extraction task failed: {e}")


# --- Suggestions for future improvements ---
# 1. Consider batch processing emails for high volume to reduce SMTP connections.
# 2. Use async email library like aiosmtplib if more concurrency is needed.
# 3. Monitor Celery task queue lengths to dynamically scale workers.
# 4. Add detailed metrics/logs for memory embeddings and distillation tasks.
# 5. Add proper type hints for all task arguments for better code clarity.
