"""
Memory Coordinator
------------------
Central, well-documented helpers to combine and manage the three memory layers:
 - Redis: short-term session state and recent conversation history
 - Neo4j: structured long-term facts & relationships
 - Pinecone: semantic memory via embeddings for similarity recall

These helpers are imported by request handlers (e.g., sessions router) to:
 1) Gather memory context before generating an AI response
 2) Persist embeddings and schedule background fact extraction after responding

Design notes:
 - We reuse existing services to avoid risky rewrites.
 - History in Redis uses the existing redis_cache module (stable sync client).
 - Session state is read from redis_service if available; default if not.
 - Neo4j async service is used in the FastAPI process; the Celery worker uses sync service.
 - Pinecone is used for message-level embeddings and similarity queries.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from datetime import datetime
import asyncio
import time

from app.services import pinecone_service, profile_service
from app.services.neo4j_service import neo4j_service
from app.services import redis_service as redis_async_service  # may be None in some envs
from app.services import memory_store
from app.utils.history import trim_history

logger = logging.getLogger(__name__)


# -----------------------------
# Types
# -----------------------------
Message = Dict[str, Any]  # {"sender": "user"|"assistant", "text": str}


async def gather_memory_context(
    *,
    user_id: str,
    user_key: str,
    session_id: str,
    latest_user_message: str,
    recent_messages: Optional[List[Message]] = None,
    top_k_semantic: int = 3,
    top_k_user_facts: int = 3,
    history_char_budget: int = 6000,
    facts_cache_ttl: int = 60,
    semantic_budget_ms: int = 140,
    graph_budget_ms: int = 160,
) -> Dict[str, Any]:
    """Collect multi-layer context with soft time budgets.

    Adds:
      - profile: deterministic Mongo-backed attributes
      - user_facts_semantic: top semantic user_fact vectors (separate from message recall)
    Late layers (Pinecone/Neo4j) are skipped if they exceed budgets.
    """

    # 1) Redis: state + history
    try:
        # Session state via unified store (falls back inside if redis unavailable)
        state = await memory_store.get_session_state(session_id, default="general_conversation")
    except Exception:  # noqa: BLE001
        state = "general_conversation"

    # Try session-specific history first
    history: List[Message] = []
    try:
        sess_hist = await memory_store.get_session_history(session_id, limit=50)
        # Normalize to expected structure {role/content} -> convert to sender/text pair for compatibility
        for m in sess_hist:
            history.append({"role": m.get("role"), "content": m.get("content")})
    except Exception:  # noqa: BLE001
        history = []

    # If no Redis history available, fallback to provided recent_messages (from DB)
    if not history and recent_messages:
        history = recent_messages[-50:]

    # 2) Neo4j: structured facts (with Redis cache + hard timeout)
    neo4j_facts = ""
    graph_time_ms: float = 0.0
    skipped_layers: List[str] = []
    cache_key = f"facts_cache:{user_id}"
    try:
        redis_cli = getattr(redis_async_service, "redis_client", None)
        cache_hit = False
        if redis_cli:
            cached = await redis_cli.get(cache_key)
            if cached:
                neo4j_facts = cached
                cache_hit = True
        if not neo4j_facts:
            # Launch async Neo4j retrieval with timeout
            start_graph = time.time()
            try:
                neo4j_task = asyncio.create_task(neo4j_service.get_user_facts(user_id))
                neo4j_facts = await asyncio.wait_for(neo4j_task, timeout=graph_budget_ms / 1000.0) or ""
                graph_time_ms = (time.time() - start_graph) * 1000
            except asyncio.TimeoutError:
                skipped_layers.append("neo4j")
                graph_time_ms = (time.time() - start_graph) * 1000
                try:
                    neo4j_task.cancel()
                except Exception:  # noqa: BLE001
                    pass
            except Exception as e:  # noqa: BLE001
                graph_time_ms = (time.time() - start_graph) * 1000
                logger.warning(f"Neo4j facts retrieval failed: {e}")
            # Cache fresh value if present
            if neo4j_facts and redis_cli:
                try:
                    await redis_cli.set(cache_key, neo4j_facts, ex=facts_cache_ttl)
                except Exception:  # noqa: BLE001
                    pass
            if cache_hit:
                graph_time_ms = 0.0
    except Exception:  # noqa: BLE001
        pass

    # 3) Profile (Mongo deterministic)
    try:
        profile = profile_service.get_profile(user_id)
    except Exception:  # noqa: BLE001
        profile = {}

    # 4) Pinecone queries (progressive time budgeting)
    pinecone_context = None
    user_fact_snippets: List[str] = []
    semantic_time_ms: float = 0.0
    try:
        start_sem = time.time()
        pinecone_context = pinecone_service.query_similar_texts(
            user_id=user_id, text=latest_user_message, top_k=top_k_semantic
        )
        semantic_time_ms = (time.time() - start_sem) * 1000
        # Only run user_fact query if within remaining budget window
        if semantic_time_ms < semantic_budget_ms:
            user_fact_snippets = pinecone_service.query_user_facts(
                user_id=user_id, hint_text=latest_user_message, top_k=top_k_user_facts
            )
        else:
            skipped_layers.append("pinecone_user_facts")
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Pinecone query failed: {e}")
        pinecone_context = None

    # 4) Trim history to budget
    trimmed_history = trim_history(history, max_chars=history_char_budget)

    return {
        "state": state,
        "history": trimmed_history,
        "pinecone_context": pinecone_context,
        "neo4j_facts": neo4j_facts,
        "profile": profile,
        "user_facts_semantic": user_fact_snippets,
        "timings": {
            "semantic_ms": round(semantic_time_ms, 2),
            "graph_ms": round(graph_time_ms, 2),
            "skipped": skipped_layers,
        },
    }


async def _append_history(session_id: str, user_message: str, ai_message: str):
    """Append messages to unified session history asynchronously."""
    try:
        await memory_store.append_session_messages(
            session_id,
            [
                {"role": "user", "content": user_message},
                {"role": "assistant", "content": ai_message},
            ],
        )
    except Exception:  # noqa: BLE001
        logger.debug("Failed to append session history (non-fatal).")


def _upsert_embeddings(user_id: str, session_id: str, user_message: str, ai_message: str):
    """Store embeddings for user & assistant messages to enable semantic recall later."""
    try:
        ts = datetime.utcnow().isoformat()
        pinecone_service.upsert_message_embedding(
            user_id=user_id, session_id=session_id, text=user_message, role="user", timestamp=ts
        )
        pinecone_service.upsert_message_embedding(
            user_id=user_id, session_id=session_id, text=ai_message, role="assistant", timestamp=ts
        )
    except Exception as e:
        logger.debug(f"Failed to upsert embeddings: {e}")


def post_message_update(
    *,
    user_id: str,
    user_key: str,
    session_id: str,
    user_message: str,
    ai_message: str,
    state: Optional[str] = None,
):
    """Call after the AI response is generated to update memories and dispatch tasks.

    - Appends conversation messages to Redis history
    - Optionally updates Redis session state
    - Upserts message embeddings into Pinecone
    - Enqueues fact extraction into Neo4j via Celery
    """
    # a) Append to Redis history and session state (best-effort)
    # Append conversation history (fire-and-forget best effort)
    try:
        import asyncio
        asyncio.create_task(_append_history(session_id, user_message, ai_message))
    except Exception:  # noqa: BLE001
        pass

    # Update session state if provided
    if state:
        try:
            import asyncio
            asyncio.create_task(memory_store.set_session_state(session_id, state))
        except Exception:  # noqa: BLE001
            pass

    # b) Upsert embeddings
    _upsert_embeddings(user_id, session_id, user_message, ai_message)

    # c) Extract and store facts (background) with gating
    try:
        should_extract = False
        # Gate by message length OR every 3rd user message overall
        long_message = len(user_message) > 220  # heuristic threshold
        try:
            import asyncio as _asyncio
            counter = _asyncio.get_event_loop().run_until_complete(
                memory_store.increment_user_message_counter(user_id)
            )
        except Exception:
            counter = 0
        if long_message or (counter % 3 == 0):
            should_extract = True

        if should_extract:
            # Invalidate facts cache so next retrieval picks up new facts
            try:
                import asyncio as _asyncio
                _asyncio.get_event_loop().run_until_complete(memory_store.invalidate_facts_cache(user_id))
            except Exception:  # noqa: BLE001
                pass
            from app.celery_worker import extract_and_store_facts_task
            extract_and_store_facts_task.delay(
                user_message=user_message, assistant_message=ai_message, user_id=user_id
            )
    except Exception as e:  # noqa: BLE001
        logger.debug(f"Gated fact extraction scheduling failed: {e}")
