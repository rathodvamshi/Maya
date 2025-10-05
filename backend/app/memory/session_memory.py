"""Rolling conversational memory for persona layer.

Stores last N user+assistant message pairs per user to help produce warmer,
contextually aware persona responses. Uses Redis if available; otherwise
falls back to in-process dict (non-persistent, fine for dev/tests).
"""
from __future__ import annotations

from typing import List, Dict, Tuple, Optional
import json
import logging

from app.services import redis_service
from app.config import settings

logger = logging.getLogger(__name__)

redis_client = getattr(redis_service, "redis_client", None)

_MAX_TURNS = max(3, min(40, settings.PERSONA_MEMORY_TURNS))  # safety clamp
_FALLBACK_STORE: Dict[str, List[Tuple[str, str, Optional[str]]]] = {}

_key = lambda user_id: f"persona:ctx:{user_id}"  # noqa: E731


async def add_to_context(user_id: str, user_text: str, ai_text: str, emotion: Optional[str] = None) -> None:
    if not user_id:
        return
    try:
        if redis_client:
            key = _key(user_id)
            entry = json.dumps([user_text, ai_text, emotion])
            pipe = redis_client.pipeline(transaction=False)
            pipe.rpush(key, entry)
            pipe.ltrim(key, -_MAX_TURNS, -1)
            pipe.expire(key, 7200)
            await pipe.execute()
        else:
            buf = _FALLBACK_STORE.setdefault(user_id, [])
            buf.append((user_text, ai_text, emotion))
            if len(buf) > _MAX_TURNS:
                del buf[0: len(buf) - _MAX_TURNS]
    except Exception:  # noqa: BLE001
        logger.debug("persona add_to_context failed", exc_info=True)


async def get_context(user_id: str) -> List[Dict[str, str]]:
    if not user_id:
        return []
    try:
        if redis_client:
            key = _key(user_id)
            raw_items = await redis_client.lrange(key, -_MAX_TURNS, -1)
            out = []
            for r in raw_items:
                try:
                    pair = json.loads(r)
                    if isinstance(pair, list) and len(pair) >= 2:
                        emo = pair[2] if len(pair) > 2 else None
                        out.append({"user": pair[0], "ai": pair[1], "emotion": emo})
                except Exception:
                    continue
            return out
        else:
            return [
                {"user": u, "ai": a, "emotion": e}
                for (u, a, e) in _FALLBACK_STORE.get(user_id, [])[-_MAX_TURNS:]
            ]
    except Exception:  # noqa: BLE001
        logger.debug("persona get_context failed", exc_info=True)
        return []


async def get_recent_emotions(user_id: str, limit: int = 8) -> List[str]:
    """Return up to last N non-null emotion labels for trend / escalation logic."""
    ctx = await get_context(user_id)
    emos = [c.get("emotion") for c in ctx if c.get("emotion")]
    return emos[-limit:]
