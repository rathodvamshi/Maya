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
from app.services import memory_service
from app.utils.history import trim_history
try:
    from app.memory.manager import memory_manager as _memory_manager
except Exception:  # noqa: BLE001
    _memory_manager = None

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

    # 3) Profile (Redis-cached -> Mongo deterministic)
    try:
        cached_prof = await memory_store.get_cached_user_profile(user_id)
    except Exception:
        cached_prof = None
    if cached_prof:
        profile = cached_prof
    else:
        try:
            profile = profile_service.get_profile(user_id)
            # Warm cache best-effort
            try:
                await memory_store.cache_user_profile(user_id, profile)
            except Exception:
                pass
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

    # 4b) Unified manager fallback for cross-session retrieval
    # If we skipped Neo4j due to timeout or Pinecone returned empty, query via MemoryManager
    try:
        if _memory_manager is not None and (not neo4j_facts or not pinecone_context):
            mm_res = await _memory_manager.get_memory(
                user_id=user_id,
                query=latest_user_message,
                memory_type=None,
                session_id=session_id,
            )
            if not neo4j_facts:
                alt_graph = (mm_res or {}).get("neo4j") or ""
                if alt_graph:
                    neo4j_facts = alt_graph
            if not pinecone_context:
                # Convert list of matches into compact context
                matches = (mm_res or {}).get("pinecone") or []
                if matches:
                    txts = [m.get("text") for m in matches if isinstance(m, dict) and m.get("text")]
                    if txts:
                        pinecone_context = "\n---\n".join(txts[:top_k_semantic])
    except Exception as _e:  # noqa: BLE001
        # Fallback is best-effort; do not fail context build
        pass

    # 4) Trim history to budget
    trimmed_history = trim_history(history, max_chars=history_char_budget)

    # 5) Long-term memories (Mongo) basic retrieval (priority + salience ordering)
    persistent_memories: List[dict] = []
    blocked_memories: List[str] = []
    scoring_records: List[dict] = []
    try:
        from app.services.pinecone_service import query_user_memories
        # Base docs for metadata (salience, priority, recency)
        raw_mems = await memory_service.list_memories(user_id, limit=300, lifecycle=["active", "candidate", "distilled"])
        mem_by_id = {m.get("_id"): m for m in raw_mems}
        pine_matches = query_user_memories(user_id, latest_user_message, top_k=15) or []
        SENSITIVE_KEYWORDS = ["password", "ssn", "account", "credit card", "bank"]
        priority_weights = {"system": 1.3, "critical": 1.15, "normal": 1.0, "low": 0.9}
        redis_cli = getattr(redis_async_service, "redis_client", None)
        gating_cfg = {
            "enable": getattr(__import__('app.config').config.settings, 'MEMORY_GATE_ENABLE', True),
            "min_salience": getattr(__import__('app.config').config.settings, 'MEMORY_GATE_MIN_SALIENCE', 0.85),
            "min_trust": getattr(__import__('app.config').config.settings, 'MEMORY_GATE_MIN_TRUST', 0.55),
            "min_composite": getattr(__import__('app.config').config.settings, 'MEMORY_GATE_MIN_COMPOSITE', 0.35),
            "log_skipped": getattr(__import__('app.config').config.settings, 'MEMORY_GATE_LOG_SKIPPED', True),
        }
        for pm in pine_matches:
            mid = pm.get("memory_id")
            if not mid or mid not in mem_by_id:
                continue
            m = mem_by_id[mid]
            val_text = (m.get("value") or "")
            sens_level = (m.get("sensitivity") or {}).get("level")
            low_val = val_text.lower()
            sensitive_flag = (sens_level and sens_level != "none") or any(k in low_val for k in SENSITIVE_KEYWORDS)
            if sensitive_flag:
                blocked_memories.append(mid)
                try:
                    from app.services.memory_service import log_pii_block as _log
                    rule = sens_level or next((kw for kw in SENSITIVE_KEYWORDS if kw in low_val), "keyword_match")
                    _log(user_id, mid, latest_user_message, rule, sens_level or "keyword")
                except Exception:
                    pass
                continue
            priority = m.get("priority", "normal")
            salience = m.get("salience_score", 1.0) or 1.0
            recency_days = 999
            try:
                ts = m.get("last_accessed_at") or m.get("updated_at")
                if ts:
                    dt = datetime.fromisoformat(ts.replace("Z", ""))
                    recency_days = max(0, (datetime.utcnow() - dt).days)
            except Exception:
                pass
            recency_factor = 1.0
            if recency_days < 1:
                recency_factor = 1.15
            elif recency_days < 7:
                recency_factor = 1.05
            elif recency_days > 45:
                recency_factor = 0.85
            similarity = pm.get("similarity") or 0.0001
            trust_conf = (m.get("trust") or {}).get("confidence") or 0.75
            trust_factor = 0.8 + 0.2 * float(trust_conf)
            base = similarity * priority_weights.get(priority, 1.0) * salience * recency_factor * trust_factor
            # --- Proactive Recall Gating ---
            gated = False
            if gating_cfg["enable"]:
                user_flags = m.get("user_flags") or {}
                override = user_flags.get("gating_override") is True
                composite = (similarity or 0.0) * float(salience) * float(trust_conf)
                if not override and (
                    salience < gating_cfg["min_salience"] or
                    trust_conf < gating_cfg["min_trust"] or
                    composite < gating_cfg["min_composite"]
                ):
                    gated = True
            if gated:
                if gating_cfg["log_skipped"]:
                    scoring_records.append({
                        "memory_id": mid,
                        "similarity": round(float(similarity), 4),
                        "recency_days": recency_days,
                        "priority": priority,
                        "salience": salience,
                        "recency_factor": round(recency_factor, 3),
                        "trust_factor": round(trust_factor, 3),
                        "score": round(base, 5),
                        "gated": True,
                    })
                continue
            scoring_records.append({
                "memory_id": mid,
                "similarity": round(float(similarity), 4),
                "recency_days": recency_days,
                "priority": priority,
                "salience": salience,
                "recency_factor": round(recency_factor, 3),
                "trust_factor": round(trust_factor, 3),
                "score": round(base, 5),
                "gated": False,
            })
        scoring_records.sort(key=lambda r: r["score"], reverse=True)
        top_records = scoring_records[: top_k_user_facts]
        for r in top_records:
            mid = r["memory_id"]
            mm = mem_by_id.get(mid)
            if mm:
                persistent_memories.append({
                    "id": mm.get("_id"),
                    "title": mm.get("title"),
                    "value": mm.get("value"),
                    "priority": mm.get("priority"),
                    "lifecycle_state": mm.get("lifecycle_state"),
                })
                # Frequency counter increment
                if redis_cli:
                    try:
                        await redis_cli.incr(f"user:{user_id}:memory_freq:{mid}")
                    except Exception:
                        pass
        try:
            asyncio.create_task(memory_service.log_recall_event(user_id, latest_user_message, scoring_records[:40]))
        except Exception:
            pass
    except Exception as e:
        logger.debug(f"Memory retrieval failed (similarity layer): {e}")

    return {
        "state": state,
        "history": trimmed_history,
        "pinecone_context": pinecone_context,
        "neo4j_facts": neo4j_facts,
        "profile": profile,
        "user_facts_semantic": user_fact_snippets,
        "persistent_memories": persistent_memories,
        "blocked_memory_ids": blocked_memories,
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


async def post_message_update_async(
    *,
    user_id: str,
    user_key: str,
    session_id: str,
    user_message: str,
    ai_message: str,
    state: Optional[str] = None,
):
    """Async variant to be awaited by async routers/services.

    Responsibilities:
      - Fire-and-forget append of conversation history
      - Optional session state update
      - Synchronous embedding upsert (CPU / network bound; left sync)
      - Gated background fact extraction scheduling
    """
    # a) Append to Redis history & optional state
    try:
        asyncio.create_task(_append_history(session_id, user_message, ai_message))
    except Exception:  # noqa: BLE001
        pass
    if state:
        try:
            asyncio.create_task(memory_store.set_session_state(session_id, state))
        except Exception:  # noqa: BLE001
            pass

    # b) Upsert embeddings (sync call encapsulates its own try/except)
    _upsert_embeddings(user_id, session_id, user_message, ai_message)

    # c) Gate fact extraction
    try:
        long_message = len(user_message) > 220
        counter = await memory_store.increment_user_message_counter(user_id)
        should_extract = long_message or (counter % 3 == 0)
        if should_extract:
            try:
                await memory_store.invalidate_facts_cache(user_id)
            except Exception:  # noqa: BLE001
                pass
            from app.celery_worker import extract_and_store_facts_task
            extract_and_store_facts_task.delay(
                user_message=user_message, assistant_message=ai_message, user_id=user_id
            )
    except Exception as e:  # noqa: BLE001
        logger.debug(f"Gated fact extraction scheduling failed: {e}")


def post_message_update(**kwargs):
    """Backward compatible sync shim.

    If called in a running event loop, schedule the async version.
    Otherwise, create a new loop and run (should be rare in FastAPI context).
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        loop.create_task(post_message_update_async(**kwargs))
    else:
        asyncio.run(post_message_update_async(**kwargs))
