# backend/app/services/redis_service.py

import redis.asyncio as redis
import json
import logging
from typing import Optional, Dict, Any
from app.config import settings

logger = logging.getLogger(__name__)

# =====================================================
# 🔹 Redis Client Initialization
# =====================================================
redis_client = None
try:
    # Using a connection pool for efficiency
    redis_pool = redis.ConnectionPool(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        db=settings.REDIS_DB,
        password=settings.REDIS_PASSWORD or None,
        decode_responses=True  # Automatically decode responses to strings
    )
    redis_client = redis.Redis(connection_pool=redis_pool)
    logger.info("✅ Redis connection pool created.")
except Exception as e:
    logger.error(f"❌ Failed to create Redis connection pool: {e}")

# =====================================================
# 🔹 Session State Management
# =====================================================
async def get_session_state(session_id: str) -> str:
    """
    Retrieve the current state of a conversation session.
    Returns 'initial_greeting' if no state is found or Redis is unavailable.
    """
    if not redis_client:
        return "general_conversation"

    state_key = f"session:state:{session_id}"
    try:
        state = await redis_client.get(state_key)
        return state if state else "initial_greeting"
    except Exception as e:
        logger.error(f"Failed to get session state for {session_id}: {e}")
        return "initial_greeting"


async def set_session_state(session_id: str, state: str, ttl_seconds: int = 86400):
    """
    Set or update the state of a conversation session in Redis.
    """
    if not redis_client:
        return

    state_key = f"session:state:{session_id}"
    try:
        await redis_client.set(state_key, state, ex=ttl_seconds)
    except Exception as e:
        logger.error(f"Failed to set session state for {session_id}: {e}")


# =====================================================
# 🔹 Prefetched Data Caching
# =====================================================
async def set_prefetched_data(cache_key: str, data: Dict[str, Any], ttl_seconds: int = 900):
    """
    Store prefetched or frequently accessed data in Redis with a TTL.
    """
    if not redis_client:
        return

    try:
        json_data = json.dumps(data)
        await redis_client.set(cache_key, json_data, ex=ttl_seconds)
        logger.info(f"✅ Prefetched data cached under key: {cache_key}")
    except Exception as e:
        logger.error(f"Failed to set prefetched data for key {cache_key}: {e}")


async def get_prefetched_data(cache_key: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve prefetched data from Redis and decode it from JSON.
    """
    if not redis_client:
        return None

    try:
        json_data = await redis_client.get(cache_key)
        if json_data:
            return json.loads(json_data)
        return None
    except Exception as e:
        logger.error(f"Failed to get prefetched data for key {cache_key}: {e}")
        return None


# =====================================================
# 🔹 Utility: Delete cached data (optional helper)
# =====================================================
def delete_cache_key(cache_key: str):
    """
    Delete a specific key from Redis cache.
    """
    if not redis_client:
        return
    try:
        redis_client.delete(cache_key)
        logger.info(f"✅ Deleted cache key: {cache_key}")
    except Exception as e:
        logger.error(f"Failed to delete cache key {cache_key}: {e}")
