"""Unified async Redis memory store.

Goals:
 - Provide a single async interface for session state, conversation history,
   user profile cache, and facts cache.
 - Replace split usage of `redis_service` (async) and `redis_cache` (sync).
 - Keep functions idempotent and safe when Redis is unavailable.

Key design:
 - Session history stored per session: list at key `sess:{session_id}:msgs`.
 - Each list item is a compact JSON string: {"role": "user"|"assistant", "content": str}.
 - Trim history to a max length (default 50) on every append.
 - Session state stored at `session:state:{session_id}`.
 - User profile cache key: `user:{user_id}:profile`.
 - Facts cache key: `facts_cache:{user_id}` (kept for backward compatibility with existing usage).
 - Embedding queue (batching prep for later step) keys reserved: `embed:queue` (list) and `embed:lock`.

This module is intentionally minimal and dependency-free beyond the existing
`redis_service.redis_client` instance.
"""
from __future__ import annotations

from typing import List, Dict, Optional, Any
import json
import logging

from app.services import redis_service

logger = logging.getLogger(__name__)

def _client():
    try:
        return redis_service.get_client()
    except Exception:
        return None

# -----------------------------
# Session State
# -----------------------------
async def get_session_state(session_id: str, default: str = "general_conversation") -> str:
    client = _client()
    if not client:
        return default
    try:
        v = await client.get(f"session:state:{session_id}")
        return v or default
    except Exception:  # noqa: BLE001
        return default


async def set_session_state(session_id: str, state: str, ttl_seconds: int = 86400) -> None:
    client = _client()
    if not client:
        return
    try:
        await client.set(f"session:state:{session_id}", state, ex=ttl_seconds)
    except Exception:  # noqa: BLE001
        logger.debug("Failed to set session state", exc_info=True)


# -----------------------------
# Conversation History (per session)
# -----------------------------
async def append_session_messages(
    session_id: str,
    messages: List[Dict[str, str]],
    max_items: int = 50,
    ttl_seconds: int = 3 * 86400,
) -> None:
    """Append messages to session history list and trim.

    messages: list of {role, content}.
    """
    client = _client()
    if not client or not messages:
        return
    key = f"sess:{session_id}:msgs"
    try:
        # Prepare pipeline for efficiency
        pipe = client.pipeline(transaction=False)
        for m in messages:
            pipe.rpush(key, json.dumps({"role": m.get("role"), "content": m.get("content", "")}))
        pipe.ltrim(key, -max_items, -1)
        pipe.expire(key, ttl_seconds)
        await pipe.execute()
    except Exception:  # noqa: BLE001
        logger.debug("Failed to append session messages", exc_info=True)


async def get_session_history(session_id: str, limit: int = 50) -> List[Dict[str, str]]:
    client = _client()
    if not client:
        return []
    key = f"sess:{session_id}:msgs"
    try:
        items = await client.lrange(key, -limit, -1)
        out: List[Dict[str, str]] = []
        for raw in items:
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, dict) and parsed.get("content"):
                    out.append(parsed)
            except Exception:  # noqa: BLE001
                continue
        return out
    except Exception:  # noqa: BLE001
        return []


# New: replace entire session history (CRUD: Update)
async def set_session_history(
    session_id: str,
    messages: List[Dict[str, str]],
    ttl_seconds: int = 3 * 86400,
) -> None:
    client = _client()
    if not client:
        return
    key = f"sess:{session_id}:msgs"
    try:
        # Overwrite list atomically via delete + rpush pipeline
        pipe = client.pipeline(transaction=False)
        pipe.delete(key)
        for m in messages:
            pipe.rpush(key, json.dumps({"role": m.get("role"), "content": m.get("content", "")}))
        pipe.expire(key, ttl_seconds)
        await pipe.execute()
    except Exception:  # noqa: BLE001
        logger.debug("Failed to set session history", exc_info=True)


# New: delete session history and related keys (CRUD: Delete)
async def delete_session(session_id: str) -> None:
    client = _client()
    if not client:
        return
    try:
        keys = [
            f"sess:{session_id}:msgs",
            f"sess:{session_id}:flags",
        ]
        await client.delete(*keys)
        # do not delete state here; use delete_session_state for explicitness
    except Exception:  # noqa: BLE001
        logger.debug("Failed to delete session keys", exc_info=True)


# New: explicit delete for session state
async def delete_session_state(session_id: str) -> None:
    client = _client()
    if not client:
        return
    try:
        await client.delete(f"session:state:{session_id}")
    except Exception:  # noqa: BLE001
        logger.debug("Failed to delete session state", exc_info=True)

# -----------------------------
# User Profile Cache
# -----------------------------
async def cache_user_profile(user_id: str, profile: Dict, ttl_seconds: int = 600) -> None:
    client = _client()
    if not client:
        return
    try:
        await client.set(f"user:{user_id}:profile", json.dumps(profile), ex=ttl_seconds)
    except Exception:  # noqa: BLE001
        logger.debug("Failed to cache user profile", exc_info=True)


async def get_cached_user_profile(user_id: str) -> Optional[Dict]:
    client = _client()
    if not client:
        return None
    try:
        raw = await client.get(f"user:{user_id}:profile")
        if raw:
            return json.loads(raw)
        return None
    except Exception:  # noqa: BLE001
        return None


# -----------------------------
# Facts Cache (wrapper for compatibility)
# -----------------------------
async def get_cached_facts(user_id: str) -> Optional[str]:
    client = _client()
    if not client:
        return None
    try:
        return await client.get(f"facts_cache:{user_id}")
    except Exception:  # noqa: BLE001
        return None


async def set_cached_facts(user_id: str, facts: str, ttl_seconds: int = 60) -> None:
    client = _client()
    if not client:
        return
    try:
        await client.set(f"facts_cache:{user_id}", facts, ex=ttl_seconds)
    except Exception:  # noqa: BLE001
        logger.debug("Failed to set facts cache", exc_info=True)


async def invalidate_facts_cache(user_id: str) -> None:
    client = _client()
    if not client:
        return
    try:
        await client.delete(f"facts_cache:{user_id}")
    except Exception:  # noqa: BLE001
        logger.debug("Failed to invalidate facts cache", exc_info=True)

# -----------------------------
# User Message Counter (for gating expensive tasks)
# -----------------------------
async def increment_user_message_counter(user_id: str, ttl_seconds: int = 86400) -> int:
    """Increment and return the per-user message counter.

    Used to gate periodic fact extraction (e.g., every 3rd message). Counter
    automatically expires after a day to avoid unbounded growth.
    """
    client = _client()
    if not client:
        return 0
    key = f"user:{user_id}:msg_counter"
    try:
        val = await client.incr(key)
        if val == 1:
            # First creation, set TTL
            await client.expire(key, ttl_seconds)
        return int(val)
    except Exception:  # noqa: BLE001
        logger.debug("Failed to increment user message counter", exc_info=True)
        return 0


# -----------------------------
# Session Flags / Prefetched Context
# -----------------------------
async def set_session_flag(session_id: str, flag: str, value: str, ttl_seconds: int = 7200) -> None:
    client = _client()
    if not client:
        return
    try:
        await client.hset(f"sess:{session_id}:flags", flag, value)
        await client.expire(f"sess:{session_id}:flags", ttl_seconds)
    except Exception:  # noqa: BLE001
        logger.debug("Failed to set session flag", exc_info=True)


async def get_session_flags(session_id: str) -> Dict[str, str]:
    client = _client()
    if not client:
        return {}
    try:
        data = await client.hgetall(f"sess:{session_id}:flags")
        return {k: v for k, v in data.items()} if data else {}
    except Exception:  # noqa: BLE001
        return {}


async def set_prefetched_context(session_id: str, key: str, payload: Any, ttl_seconds: int = 3600) -> None:
    client = _client()
    if not client:
        return
    try:
        await client.set(f"sess:{session_id}:prefetch:{key}", json.dumps(payload), ex=ttl_seconds)
    except Exception:  # noqa: BLE001
        logger.debug("Failed to set prefetched context", exc_info=True)


async def get_prefetched_context(session_id: str, key: str) -> Optional[Any]:
    client = _client()
    if not client:
        return None
    try:
        raw = await client.get(f"sess:{session_id}:prefetch:{key}")
        return json.loads(raw) if raw else None
    except Exception:  # noqa: BLE001
        return None


# -----------------------------
# Embedding Queue (skeleton for next step / already used by batch worker)
# -----------------------------
EMBED_QUEUE_KEY = "embed:queue"


async def enqueue_embedding_job(payload: Dict) -> None:
    client = _client()
    if not client:
        return
    try:
        await client.rpush(EMBED_QUEUE_KEY, json.dumps(payload))
    except Exception:  # noqa: BLE001
        logger.debug("Failed to enqueue embedding job", exc_info=True)


async def dequeue_embedding_batch(max_items: int = 50) -> List[Dict]:
    client = _client()
    if not client:
        return []
    batch: List[Dict] = []
    try:
        # Use pipeline to minimize round trips
        for _ in range(max_items):
            raw = await client.lpop(EMBED_QUEUE_KEY)
            if raw is None:
                break
            try:
                batch.append(json.loads(raw))
            except Exception:  # noqa: BLE001
                continue
    except Exception:  # noqa: BLE001
        logger.debug("Failed to dequeue embedding batch", exc_info=True)
    return batch


async def embedding_queue_length() -> int:
    """Return current length of the embedding job queue.

    Defensive: returns 0 on any error or if Redis is unavailable.
    """
    client = _client()
    if not client:
        return 0
    try:
        length = await client.llen(EMBED_QUEUE_KEY)
        return int(length or 0)
    except Exception:  # noqa: BLE001
        return 0
