"""Celery worker tasks for background processing (Windows-friendly with sync Neo4j)."""

# Apply eventlet monkey patch only when running as a Celery worker process.
# Avoid patching when this module is imported by the FastAPI app.
import os
if os.environ.get("CELERY_WORKER", ""):  # set CELERY_WORKER=1 in worker environment or command
    try:
        import eventlet
        eventlet.monkey_patch()
    except Exception:
        pass

import logging
import json
from celery import Celery
import asyncio

from app.config import settings
from app.database import db_client
from app.services import ai_service
from app.services.neo4j_service import neo4j_sync_service
from app.services.redis_service import redis_client as _redis_client
from app.services import pinecone_service, memory_store, profile_service
from app.services import deterministic_extractor
from app.database import get_memories_collection
from app.config import settings
from app.services.pinecone_service import upsert_memory_embedding

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def _fire_and_forget(coro):
    """Run/queue an async coroutine from sync context safely.

    If an event loop is already running (e.g. inside an eventlet green thread
    with an active asyncio loop), schedule the task and return immediately.
    Otherwise create a temporary loop and run it to completion.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        asyncio.run(coro)
        return None
    else:
        # Schedule without awaiting (fire-and-forget semantics)
        return loop.create_task(coro)


# --- Configure Celery ---
celery_app = Celery(
    "maya_tasks",
    broker=f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}",
    backend=f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}",
    include=['app.celery_worker'],
)

celery_app.conf.timezone = "UTC"


# Ensure Neo4j sync connection is available in the worker process
try:
    neo4j_sync_service.connect()
except Exception as e:
    logger.error(f"Neo4j sync connect failed in worker: {e}")


# --- Periodic tasks ---
@celery_app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    sender.add_periodic_task(600.0, heartbeat.s(), name="worker_heartbeat")
    # Drain embedding queue every 15s
    sender.add_periodic_task(15.0, drain_embedding_queue.s(), name="drain_embedding_queue_15s")
    # Salience update every 6 hours (can be adjusted to 86400 for daily)
    sender.add_periodic_task(21600.0, update_memory_salience.s(), name="update_memory_salience_6h")
    # Lifecycle aging/archival every 12h
    sender.add_periodic_task(43200.0, lifecycle_maintenance.s(), name="memory_lifecycle_12h")
    # Distillation scan every 24h
    sender.add_periodic_task(86400.0, distillation_scan.s(), name="memory_distillation_scan_24h")
    logger.info("Configured periodic task: worker heartbeat every 600 seconds")


@celery_app.task(name="heartbeat")
def heartbeat():
    logger.info("Celery worker heartbeat - scheduler active")


@celery_app.task(name="update_memory_salience")
def update_memory_salience():
    """Aggregate Redis frequency counters into Mongo salience_score.

    salience_score = clamp(0.8, 1.25, 0.8 + (log(1+freq)/log(1+max_freq))*0.45)
    After update, delete the frequency keys.
    """
    if not _redis_client:
        return
    try:
        mem_coll = get_memories_collection()
        cursor = 0
        counts = {}
        pattern = "user:*:memory_freq:*"
        # Scan to collect counts
        while True:
            cursor, keys = _redis_client.scan(cursor=cursor, match=pattern, count=500)
            for k in keys:
                try:
                    val = int(_redis_client.get(k) or 0)
                    if val <= 0:
                        continue
                    # key format user:{uid}:memory_freq:{mid}
                    parts = k.split(":")
                    if len(parts) >= 4:
                        uid = parts[1]
                        mid = parts[-1]
                        counts.setdefault(uid, {})[mid] = val
                except Exception:
                    continue
            if cursor == 0:
                break
        # Compute updates per user
        import math
        for uid, mem_map in counts.items():
            if not mem_map:
                continue
            max_freq = max(mem_map.values()) or 1
            bulk_ops = []
            for mid, freq in mem_map.items():
                norm = math.log(1 + freq) / math.log(1 + max_freq)
                salience = 0.8 + norm * 0.45  # -> [0.8, 1.25]
                try:
                    from bson import ObjectId
                    bulk_ops.append({
                        "filter": {"_id": ObjectId(mid), "user_id": uid},
                        "update": {"$set": {"salience_score": round(salience, 4), "updated_at": __import__('datetime').datetime.utcnow().isoformat()}},
                    })
                except Exception:
                    continue
            # Execute bulk updates
            for op in bulk_ops:
                try:
                    mem_coll.update_one(op["filter"], op["update"])
                except Exception:
                    pass
        # Cleanup keys
        for uid, mem_map in counts.items():
            for mid in mem_map:
                try:
                    _redis_client.delete(f"user:{uid}:memory_freq:{mid}")
                except Exception:
                    pass
        logger.info(f"Salience update complete for {sum(len(m) for m in counts.values())} memories across {len(counts)} users")
    except Exception as e:
        logger.exception(f"Salience update failed: {e}")


@celery_app.task(name="memory_lifecycle_maintenance")
def lifecycle_maintenance():
    """Demote stale or low-value memories through lifecycle states.

    Rules (initial heuristics):
      active -> aging if (last_accessed_at > 30d OR salience_score < 0.9) AND not pinned
      aging -> archived if (last_accessed_at > 60d AND salience_score < 0.95)
    Archived memories get undo_expiry_at = now + 30d for potential restore.
    """
    try:
        mem_coll = get_memories_collection()
        now = __import__('datetime').datetime.utcnow()
        iso_now = now.isoformat()
        from datetime import timedelta
        # Active -> Aging
        thirty_days_ago = (now - timedelta(days=30)).isoformat()
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
        # Aging -> Archived
        sixty_days_ago = (now - timedelta(days=60)).isoformat()
        aging_to_archive = mem_coll.find({
            "lifecycle_state": "aging",
            "last_accessed_at": {"$lt": sixty_days_ago},
            "salience_score": {"$lt": 0.95},
        }).limit(500)
        archived = 0
        undo_expiry = (now + timedelta(days=30)).isoformat()
        for doc in aging_to_archive:
            try:
                mem_coll.update_one({"_id": doc["_id"]}, {"$set": {"lifecycle_state": "archived", "archived_at": iso_now, "undo_expiry_at": undo_expiry, "updated_at": iso_now}})
                archived += 1
            except Exception:
                continue
        if moved_aging or archived:
            logger.info(f"Lifecycle maintenance: moved {moved_aging} -> aging, archived {archived}")
    except Exception as e:  # noqa: BLE001
        logger.exception(f"Lifecycle maintenance failed: {e}")


@celery_app.task(name="reembed_outdated_memories")
def reembed_outdated_memories(batch_size: int = 300):
    """Re-embed memories whose model_version != current EMBEDDING_MODEL_VERSION.

    Processes in batches to avoid long-running task monopolization.
    """
    try:
        target_version = settings.EMBEDDING_MODEL_VERSION
        coll = get_memories_collection()
        outdated = coll.find({"model_version": {"$ne": target_version}}, projection=["_id", "title", "value", "lifecycle_state", "user_id"], limit=batch_size)
        count = 0
        for doc in outdated:
            try:
                text = f"{doc.get('title')}: {doc.get('value','')}"
                upsert_memory_embedding(str(doc["_id"]), doc.get("user_id"), text, doc.get("lifecycle_state", "active"))
                coll.update_one({"_id": doc["_id"]}, {"$set": {"model_version": target_version, "updated_at": __import__('datetime').datetime.utcnow().isoformat()}})
                count += 1
            except Exception:
                continue
        if count:
            logger.info(f"Re-embedded {count} outdated memories -> version {target_version}")
    except Exception as e:  # noqa: BLE001
        logger.exception(f"Re-embed task failed: {e}")


@celery_app.task(name="distillation_scan")
def distillation_scan(batch_limit_per_user: int = 30, max_users: int = 200):
    """Scan for distillation candidates and create distilled summaries.

    Heuristic: for each user with candidates, group first N by shared low salience.
    Placeholder grouping: take up to 8 oldest/lowest-salience candidates per distilled summary.
    """
    try:
        mem_coll = get_memories_collection()
        # Find distinct user_ids with aging/archived low-salience non-distilled memories needing distillation
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
        from app.config import settings as _settings
        global_cap = getattr(_settings, "DISTILLATION_SCAN_GLOBAL_CAP", 25)
        per_user_cap = getattr(_settings, "DISTILLATION_SCAN_PER_USER_CAP", 2)
        group_size = getattr(_settings, "DISTILLATION_GROUP_SIZE", 8)
        if global_cap <= 0 or per_user_cap <= 0:
            logger.info("Distillation scan skipped (caps disabled)")
            return
        for ug in user_groups:
            if created_total >= global_cap:
                break
            uid = ug.get("_id")
            if not uid:
                continue
            # Fetch candidates for this user (limit broad to allow multiple groups if needed)
            remaining_for_user = per_user_cap
            cands = __import__('asyncio').run(ms.get_distillation_candidates(uid, limit=batch_limit_per_user))
            if not cands:
                continue
            # Iterate through candidate slices while respecting caps
            start = 0
            while start < len(cands) and remaining_for_user > 0 and created_total < global_cap:
                chunk = cands[start:start+group_size]
                start += group_size
                ids = [c.get("_id") for c in chunk if c.get("_id")]
                if not ids:
                    continue
                result = __import__('asyncio').run(ms.run_distillation_batch(uid, ids))
                if result.get("created"):
                    created_total += 1
                    remaining_for_user -= 1
        if created_total:
            logger.info(f"Distillation scan created {created_total} distilled memories (global cap {global_cap})")
    except Exception as e:
        logger.exception(f"Distillation scan failed: {e}")


# --- Tasks ---
@celery_app.task(name="summarize_and_archive_task")
def summarize_and_archive_task(session_id: str):
    """Summarize session transcript and archive in Neo4j (stub)."""
    try:
        logger.info(f"Summarizing and archiving session {session_id}")
        # transcript = db_client.fetch_session_transcript(session_id)
        # summary = ai_service.summarize_text(transcript)
        # neo4j_sync_service.store_session_summary_sync(session_id, summary)
    except Exception as e:
        logger.exception(f"Error summarizing session {session_id}: {e}")


@celery_app.task(
    name="extract_and_store_facts",
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 3, "countdown": 10},
    retry_backoff=True,
)
def extract_and_store_facts_task(user_message: str, assistant_message: str, user_id: str):
    """Analyze exchange, update profile, enqueue semantic & graph facts, refresh caches.

    Pipeline:
        1. Deterministic extractor → profile_update / semantic_facts / preferences
        2. Profile merge (Mongo) + preference edges (Neo4j)
        3. Enqueue semantic user facts for embedding
        4. LLM extraction (best-effort) adds richer entities/relationships
        5. Upsert graph facts (Neo4j)
        6. Invalidate + prewarm facts cache (Redis)
    """
    logger.info(f"REAL-TIME EXTRACTION: Analyzing messages for user {user_id}.")
    transcript = f"Human: {user_message}\nAssistant: {assistant_message}"

    try:
        neo4j_sync_service.connect()

        # 1. Deterministic extraction
        det = deterministic_extractor.extract(user_message, assistant_message)
        if det.get("profile_update"):
            try:
                profile_service.merge_update(user_id, **det["profile_update"])  # type: ignore[arg-type]
            except Exception:
                logger.exception("Profile merge_update failed")

        # 2. Preferences (hobbies)
        try:
            for pref in det.get("preferences", []) or []:
                if pref.get("type") == "hobby" and pref.get("value"):
                    neo4j_sync_service.upsert_user_preference_sync(user_id, pref["value"], "HOBBY")
        except Exception:  # noqa: BLE001
            logger.debug("Failed preference upserts")

        # 2b. Friend locations
        try:
            for fl in det.get("friend_locations", []) or []:
                friend = fl.get("friend")
                city = fl.get("city")
                if friend and city:
                    neo4j_sync_service.upsert_friend_location_sync(user_id, friend, city)
        except Exception:  # noqa: BLE001
            logger.debug("Failed friend location upserts")

        # 3. Semantic user facts enqueue
        semantic_facts = det.get("semantic_facts", []) or []
        if semantic_facts:
            try:
                ts = __import__("datetime").datetime.utcnow().isoformat()
                for fact in semantic_facts:
                    payload = {
                        "user_id": user_id,
                        "session_id": "",
                        "text": fact,
                        "role": "fact",
                        "timestamp": ts,
                        "kind": "user_fact",
                    }
                    _fire_and_forget(memory_store.enqueue_embedding_job(payload))
            except Exception:  # noqa: BLE001
                logger.exception("Failed to enqueue semantic facts")

        # 4. LLM extraction (optional)
        facts_data = ai_service.extract_facts_from_text(transcript)
        entities: list = []
        relationships: list = []
        if facts_data:
            parsed = None
            if isinstance(facts_data, str):
                try:
                    parsed = json.loads(facts_data)
                except json.JSONDecodeError:
                    logger.error("AI returned invalid JSON for facts")
                    logger.debug(f"AI raw output: {facts_data[:400]}")
            elif isinstance(facts_data, dict):
                parsed = facts_data
            if parsed:
                entities = parsed.get("entities", []) if isinstance(parsed.get("entities"), list) else []
                relationships = parsed.get("relationships", []) if isinstance(parsed.get("relationships"), list) else []

        # 5. Build final graph fact payload
        valid_entities = [e for e in entities if isinstance(e, dict) and e.get("name")]
        user_node_name = f"User_{user_id}"
        valid_entities.append({"name": user_node_name, "label": "User", "id": user_id})
        person_entity = next((e for e in valid_entities if e.get("label") == "PERSON"), None)
        if person_entity:
            relationships.append({
                "source": user_node_name,
                "target": person_entity["name"],
                "type": "IS_NAMED",
            })
            try:
                neo4j_sync_service.run_query(
                    "MERGE (u:User {id: $uid}) SET u.name = $uname",
                    {"uid": user_id, "uname": person_entity["name"]},
                )
            except Exception:  # noqa: BLE001
                logger.debug("Failed to persist user name on User node")

        final_facts = {"entities": valid_entities, "relationships": relationships}
        if final_facts["entities"] or final_facts["relationships"]:
            neo4j_sync_service.add_entities_and_relationships_sync(final_facts)
            logger.info(f"Stored graph facts for user {user_id}")
        else:
            logger.info(f"No new graph facts for user {user_id}")

        # 6. Invalidate + prewarm facts cache
        try:
            _fire_and_forget(memory_store.invalidate_facts_cache(user_id))
            facts_str = neo4j_sync_service.get_user_facts_sync(user_id)
            if facts_str:
                _fire_and_forget(memory_store.set_cached_facts(user_id, facts_str, ttl_seconds=60))
        except Exception:  # noqa: BLE001
            logger.debug("Failed facts cache prewarm", exc_info=True)

    except Exception as e:  # noqa: BLE001
        logger.exception(f"Error extracting facts for user {user_id}: {e}")
        raise


@celery_app.task(name="prefetch_destination_info")
def prefetch_destination_info_task(destination: str, session_id: str):
    """Preload info for a destination and cache in Redis."""
    try:
        logger.info(f"Prefetching info for {destination}, session {session_id}")
        # info = ai_service.fetch_destination_info(destination)
        # if _redis_client:
        #     _redis_client.set(f"prefetched_info:{session_id}", json.dumps(info), ex=3600)
    except Exception as e:
        logger.exception(f"Error prefetching info for {destination}: {e}")


@celery_app.task(name="process_feedback_task")
def process_feedback_task(fact_id: str, correction: str, user_id: str):
    """Apply user feedback:
      - Attempt Neo4j fact update (legacy path)
      - Adjust memory trust + salience if memory_id matches
      - Log memory feedback event
    """
    from app.database import get_memory_feedback_collection, get_memories_collection
    try:
        logger.info(f"Processing feedback: {fact_id} -> '{correction}' (user {user_id})")
        # Neo4j path best-effort
        try:
            neo4j_sync_service.connect()
            neo4j_sync_service.update_fact_sync(fact_id, correction, user_id)
        except Exception:
            logger.debug("Neo4j fact update failed or not applicable")

        mem_coll = get_memories_collection()
        mem = None
        try:
            from bson import ObjectId
            mem = mem_coll.find_one({"_id": ObjectId(fact_id), "user_id": user_id})
        except Exception:
            mem = None
        if mem:
            # Adjust trust.confidence (increase if user corrects with new value, else maybe decrease?)
            trust = mem.get("trust") or {}
            base_conf = float(trust.get("confidence") or 0.7)
            # If correction is non-empty & different -> treat as improvement (user engaged) but previous value was wrong → slight confidence decrease
            new_conf = max(0.1, min(0.99, base_conf - 0.05)) if correction and correction != mem.get("value") else min(0.99, base_conf + 0.02)
            updates = {"trust.confidence": new_conf, "updated_at": __import__('datetime').datetime.utcnow().isoformat()}
            if correction and correction not in (mem.get("value") or ""):
                updates["value"] = correction
            # Adjust salience downward slightly if user corrected value (to avoid over-prioritization)
            if correction and correction != mem.get("value"):
                sal = float(mem.get("salience_score") or 1.0)
                updates["salience_score"] = max(0.8, sal * 0.92)
            mem_coll.update_one({"_id": mem["_id"]}, {"$set": updates})

        # Log feedback event
        fb_coll = get_memory_feedback_collection()
        fb_coll.insert_one({
            "user_id": user_id,
            "memory_id": fact_id,
            "correction": correction,
            "applied": bool(mem),
            "created_at": __import__('datetime').datetime.utcnow().isoformat(),
        })
        logger.info(f"Feedback processed for memory/fact {fact_id}")
    except Exception as e:  # noqa: BLE001
        logger.exception(f"Error processing feedback for {fact_id}: {e}")


@celery_app.task(name="store_embeddings_batch")
def store_embeddings_batch(batch: list[dict]):
    """Upsert a batch of embeddings for messages and user facts."""
    try:
        pinecone_service.initialize_pinecone()
        pinecone_service.bulk_upsert(batch)
    except Exception:  # noqa: BLE001
        logger.exception("Failed batch embedding upsert")


@celery_app.task(name="drain_embedding_queue")
def drain_embedding_queue(max_items: int = 40):
    """Periodic task to drain the Redis embedding queue and submit one batch.

    Uses fire-and-forget scheduling to avoid nesting event loops inside the Celery
    worker (fixes 'This event loop is already running' errors).
    """
    async def _inner():  # local coroutine
        try:
            batch = await memory_store.dequeue_embedding_batch(max_items=max_items)
            if batch:
                store_embeddings_batch.delay(batch)
        except Exception:  # noqa: BLE001
            logger.exception("Failed draining embedding queue")

    _fire_and_forget(_inner())
    # Return immediately; result of async work will be logged when done.
