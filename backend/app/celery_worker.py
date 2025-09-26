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

from app.config import settings
from app.database import db_client
from app.services import ai_service
from app.services.neo4j_service import neo4j_sync_service
from app.services.redis_service import redis_client as _redis_client
from app.services import pinecone_service, memory_store, profile_service
from app.services import deterministic_extractor

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


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
    logger.info("Configured periodic task: worker heartbeat every 600 seconds")


@celery_app.task(name="heartbeat")
def heartbeat():
    logger.info("Celery worker heartbeat - scheduler active")


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

        # 3. Semantic user facts enqueue
        semantic_facts = det.get("semantic_facts", []) or []
        if semantic_facts:
            import asyncio
            try:
                try:
                    loop = asyncio.get_event_loop()
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
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
                    loop.run_until_complete(memory_store.enqueue_embedding_job(payload))
            except Exception:
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
            import asyncio as _asyncio
            try:
                loop = _asyncio.get_event_loop()
            except RuntimeError:
                loop = _asyncio.new_event_loop(); _asyncio.set_event_loop(loop)
            loop.run_until_complete(memory_store.invalidate_facts_cache(user_id))
            facts_str = neo4j_sync_service.get_user_facts_sync(user_id)
            if facts_str:
                loop.run_until_complete(memory_store.set_cached_facts(user_id, facts_str, ttl_seconds=60))
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
    """Apply user feedback to correct a fact in Neo4j (sync)."""
    try:
        logger.info(f"Processing feedback: {fact_id} -> '{correction}' (user {user_id})")
        neo4j_sync_service.connect()
        neo4j_sync_service.update_fact_sync(fact_id, correction, user_id)
        logger.info(f"Feedback processed for fact {fact_id}")
    except Exception as e:
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
    """Periodic task to drain the Redis embedding queue and submit one batch."""
    try:
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        batch = loop.run_until_complete(memory_store.dequeue_embedding_batch(max_items=max_items))
        if batch:
            store_embeddings_batch.delay(batch)
    except Exception:
        logger.exception("Failed draining embedding queue")
