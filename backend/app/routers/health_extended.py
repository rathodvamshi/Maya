# backend/app/routers/health_extended.py
"""Extended health & connectivity diagnostics.

Exposes /health/full with detailed status for frontend/backend & memory layers.
"""
from fastapi import APIRouter
import time
from typing import Dict, Any

from app.services import pinecone_service, memory_store, redis_service
from app.services.neo4j_service import neo4j_service

router = APIRouter(prefix="/health", tags=["Health"])
BOOT_TIME = time.time()

async def _neo4j_status() -> Dict[str, Any]:
    # Attempt a lightweight connectivity check if driver exists
    connected = False
    try:
        if getattr(neo4j_service, "_driver", None) is not None:
            # Run a trivial query; swallow errors to avoid crashing endpoint
            rows = await neo4j_service.run_query("RETURN 1 AS ok")
            if rows and rows[0].get("ok") == 1:
                connected = True
    except Exception:  # noqa: BLE001
        connected = False
    return {"connected": connected}

async def _redis_status() -> Dict[str, Any]:
    ok = False
    try:
        if redis_service.redis_client:
            pong = await redis_service.redis_client.ping()
            ok = bool(pong)
    except Exception:  # noqa: BLE001
        ok = False
    return {"connected": ok}

async def _pinecone_status() -> Dict[str, Any]:
    ready = False
    try:
        ready = pinecone_service.pinecone_service.is_ready()
    except Exception:  # noqa: BLE001
        ready = False
    return {"ready": ready, "index_name": getattr(pinecone_service, "PINECONE_INDEX_NAME", None)}

@router.get("/full")
async def full_health():
    """Return comprehensive system health and memory pipeline status."""
    neo4j = await _neo4j_status()
    redis = await _redis_status()
    pine = await _pinecone_status()
    embed_len = await memory_store.embedding_queue_length()
    uptime = int(time.time() - BOOT_TIME)

    overall = all([
        neo4j.get("connected"),
        redis.get("connected"),
        pine.get("ready"),
    ])

    return {
        "status": "ok" if overall else "degraded",
        "uptime_seconds": uptime,
        "neo4j": neo4j,
        "redis": redis,
        "pinecone": pine,
        "embedding_queue_length": embed_len,
    }
