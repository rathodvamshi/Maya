"""
Simple Redis-backed conversation memory helpers used by the sessions router.
Exposes get_conversation_context and set_conversation_context on top of the
singleton redis_service instance.
"""

import redis
from app.config import settings
import logging

logger = logging.getLogger(__name__)

# =====================================================
# 🔹 Redis Service Class
# =====================================================
class RedisService:
    def __init__(self, host, port, db=0, password=None):
        try:
            # Use a connection pool for efficiency
            self.redis_pool = redis.ConnectionPool(
                host=host,
                port=port,
                db=db,
                password=password,
                decode_responses=True  # Automatically decode bytes to strings
            )
            self.client = redis.Redis(connection_pool=self.redis_pool)
            self.client.ping()
            logger.info("✅ Successfully connected to Redis.")
        except Exception as e:
            logger.error(f"❌ Failed to connect to Redis: {e}")
            self.client = None

    # -----------------------------
    # Session State Management
    # -----------------------------
    def get_session_state(self, session_id: str, default: str = "initial_greeting") -> str:
        if not self.client:
            logger.warning("Redis client unavailable. Returning default state.")
            return default

        try:
            state_key = f"session:state:{session_id}"
            state = self.client.get(state_key)
            return state if state else default
        except Exception as e:
            logger.error(f"Error retrieving session state from Redis: {e}")
            return default

    def set_session_state(self, session_id: str, state: str, expire_seconds: int = 86400):
        if not self.client:
            logger.warning("Redis client unavailable. Cannot set session state.")
            return

        try:
            state_key = f"session:state:{session_id}"
            self.client.set(state_key, state, ex=expire_seconds)
            logger.debug(f"Session state set: {state_key} -> {state}")
        except Exception as e:
            logger.error(f"Error setting session state in Redis: {e}")


# =====================================================
# 🔹 Singleton Redis Service Instance
# =====================================================
redis_service = RedisService(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    db=settings.REDIS_DB,
    password=settings.REDIS_PASSWORD or None
)


# High-level conversation history helpers (list semantics)
def get_conversation_context(user_key: str) -> list[dict]:
    if not redis_service.client:
        return []
    try:
        key = f"conv:history:{user_key}"
        items = redis_service.client.lrange(key, 0, -1) or []
        # Items are stored as JSON strings; parse lazily
        import json
        return [json.loads(i) for i in items]
    except Exception:
        return []


def set_conversation_context(user_key: str, message: dict, max_items: int = 50):
    if not redis_service.client:
        return
    try:
        key = f"conv:history:{user_key}"
        import json
        redis_service.client.rpush(key, json.dumps(message))
        # Trim to last max_items
        redis_service.client.ltrim(key, -max_items, -1)
    except Exception:
        pass
