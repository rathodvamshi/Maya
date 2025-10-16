# backend/app/routers/health.py
"""
Health check endpoints for Redis, MongoDB, and Celery as specified in requirements.
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any
import logging

from app.database import db_client
from app.services.redis_service import get_client as get_redis_client, ping as redis_ping
from app.celery_worker import celery_app
from app.services import metrics as _metrics
from app.services.telemetry import aggregate_average_latency, aggregate_provider_success

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/health",
    tags=["Health Checks"],
)


@router.get("/redis")
async def health_redis() -> Dict[str, Any]:
    """
    Health check for Redis connection.
    """
    try:
        is_healthy = await redis_ping()
        if is_healthy:
            return {"status": "healthy", "service": "redis"}
        else:
            raise HTTPException(status_code=503, detail="Redis ping failed")
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        raise HTTPException(status_code=503, detail=f"Redis unavailable: {str(e)}")


@router.get("/mongo")
async def health_mongo() -> Dict[str, Any]:
    """
    Health check for MongoDB connection.
    """
    try:
        if not db_client.healthy():
            raise HTTPException(status_code=503, detail="MongoDB client not healthy")
        
        # Try to ping the database
        if not db_client.ping():
            raise HTTPException(status_code=503, detail="MongoDB ping failed")
        
        return {"status": "healthy", "service": "mongodb"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"MongoDB health check failed: {e}")
        raise HTTPException(status_code=503, detail=f"MongoDB unavailable: {str(e)}")


@router.get("/celery")
async def health_celery() -> Dict[str, Any]:
    """
    Health check for Celery workers.
    """
    try:
        # Try to inspect active workers
        inspect = celery_app.control.inspect()
        stats = inspect.stats()
        
        if not stats:
            raise HTTPException(status_code=503, detail="No Celery workers available")
        
        # Check if we have at least one active worker
        active_workers = list(stats.keys())
        if not active_workers:
            raise HTTPException(status_code=503, detail="No active Celery workers")
        
        return {
            "status": "healthy", 
            "service": "celery",
            "active_workers": len(active_workers),
            "workers": active_workers
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Celery health check failed: {e}")
        raise HTTPException(status_code=503, detail=f"Celery unavailable: {str(e)}")


@router.get("/")
async def health_overall() -> Dict[str, Any]:
    """
    Overall health check for all services.
    """
    services = {}
    overall_healthy = True
    
    # Check Redis
    try:
        redis_healthy = await redis_ping()
        services["redis"] = {"status": "healthy" if redis_healthy else "unhealthy"}
        if not redis_healthy:
            overall_healthy = False
    except Exception as e:
        services["redis"] = {"status": "unhealthy", "error": str(e)}
        overall_healthy = False
    
    # Check MongoDB
    try:
        mongo_healthy = db_client.healthy() and db_client.ping()
        services["mongodb"] = {"status": "healthy" if mongo_healthy else "unhealthy"}
        if not mongo_healthy:
            overall_healthy = False
    except Exception as e:
        services["mongodb"] = {"status": "unhealthy", "error": str(e)}
        overall_healthy = False
    
    # Check Celery
    try:
        inspect = celery_app.control.inspect()
        stats = inspect.stats()
        celery_healthy = bool(stats and list(stats.keys()))
        services["celery"] = {
            "status": "healthy" if celery_healthy else "unhealthy",
            "active_workers": len(list(stats.keys())) if stats else 0
        }
        if not celery_healthy:
            overall_healthy = False
    except Exception as e:
        services["celery"] = {"status": "unhealthy", "error": str(e)}
        overall_healthy = False
    
    status_code = 200 if overall_healthy else 503
    return {
        "status": "healthy" if overall_healthy else "unhealthy",
        "services": services,
        "overall_healthy": overall_healthy
    }


@router.get("/telemetry")
async def health_telemetry() -> Dict[str, Any]:
    """Lightweight telemetry snapshot for dashboards and probes."""
    try:
        snap = _metrics.snapshot()
    except Exception:
        snap = {}
    try:
        avg_lat = await aggregate_average_latency(50)
    except Exception:
        avg_lat = {}
    try:
        prov = await aggregate_provider_success(200)
    except Exception:
        prov = {}
    return {
        "metrics": snap,
        "avg_latency_ms": avg_lat,
        "provider_success": prov,
    }