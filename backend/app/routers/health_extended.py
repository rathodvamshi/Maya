# backend/app/routers/health_extended.py
"""Extended health & connectivity diagnostics.

Exposes /health/full with detailed status for frontend/backend & memory layers.
"""
from fastapi import APIRouter
import time, os
from typing import Dict, Any

from app.services import pinecone_service, memory_store, redis_service
from app.services.neo4j_service import neo4j_service
from app.services.ai_service import AI_PROVIDERS  # provider ordering and availability
from app.services.ai_service import FAILED_PROVIDERS
from app.config import settings

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


@router.get("/ai-status")
async def ai_status():
    """Expose simple AI availability for frontend: online/hedged/offline.

    - online: at least one provider not in cooldown
    - hedged: multiple providers available
    - offline: none available (all failed in cooldown window)
    """
    try:
        order = list(AI_PROVIDERS)
    except Exception:
        order = []
    try:
        failed = dict(FAILED_PROVIDERS)
    except Exception:
        failed = {}
    available = [p for p in order if p not in failed]
    mode = "offline"
    if len(available) >= 2:
        mode = "hedged"
    elif len(available) == 1:
        mode = "online"
    return {
        "providers": order,
        "failed_recently": list(failed.keys()),
        "mode": mode,
        "available_count": len(available),
    }


def _mask_url(url: str | None) -> str | None:
    if not url:
        return None
    # Redact credentials if present in URL
    try:
        import re
        return re.sub(r":[^@]+@", ":***@", url)
    except Exception:
        return url


@router.get("/cloud")
async def cloud_connectivity():
    """Report masked cloud connection settings and quick ping checks.

    Helps verify production env is wired to managed services only.
    """
    # Masked settings
    cfg = {
        "mongo_uri": _mask_url(getattr(settings, "MONGO_URI", None)),
        "redis_url": _mask_url(getattr(settings, "REDIS_URL", None)),
        "neo4j_uri": _mask_url(getattr(settings, "NEO4J_URI", None)),
        "neo4j_db": getattr(settings, "NEO4J_DATABASE", None),
        "pinecone_env": getattr(settings, "PINECONE_ENVIRONMENT", None),
    }
    # Pings
    redis_ok = await redis_service.ping()
    neo4j_ok = False
    try:
        if getattr(neo4j_service, "_driver", None) is not None:
            rows = await neo4j_service.run_query("RETURN 1 AS ok")
            neo4j_ok = bool(rows and rows[0].get("ok") == 1)
    except Exception:
        neo4j_ok = False
    pine_ok = False
    try:
        pine_ok = pinecone_service.pinecone_service.is_ready()
    except Exception:
        pine_ok = False
    return {
        "config": cfg,
        "ping": {
            "redis": redis_ok,
            "neo4j": neo4j_ok,
            "pinecone": pine_ok,
        },
    }


@router.get("/version")
async def version_info():
    """Expose build metadata and uptime for monitoring/diagnostics."""
    uptime = int(time.time() - BOOT_TIME)
    return {
        "build_sha": os.getenv("BUILD_SHA", "dev"),
        "build_date": os.getenv("BUILD_DATE", "unknown"),
        "uptime_seconds": uptime,
    }
