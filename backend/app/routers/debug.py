from fastapi import APIRouter, Depends, HTTPException, Request
from app.security import get_current_active_user
from app.services.behavior_tracker import get_inferred_preferences
from app.services import redis_service
from app.services import metrics as _metrics

router = APIRouter(prefix="/api/debug", tags=["Debug"], dependencies=[Depends(get_current_active_user)])


@router.get("/preferences/{user_id}")
async def debug_preferences(user_id: str):
    prefs = await get_inferred_preferences(user_id)
    raw = {}
    complexity_summary = {}
    try:
        if redis_service.redis_client:
            raw = await redis_service.redis_client.hgetall(f"user:{user_id}:behav") or {}
            # Extract complexity counts
            complexity_summary = {k.split('.',1)[1]: int(v) for k,v in raw.items() if k.startswith("complexity_counts.")}
    except Exception:
        raw = {}
    return {"inferred": prefs, "raw": raw, "complexity_summary": complexity_summary}


@router.get("/metrics")
def debug_metrics():
    return _metrics.snapshot()

@router.get("/echo")
async def echo(request: Request):
    """Return request method, path, headers (sanitized) for CORS/debug inspection."""
    redacted = {}
    for k, v in request.headers.items():
        if k.lower() == "authorization":
            redacted[k] = "***redacted***"
        else:
            redacted[k] = v
    return {
        "method": request.method,
        "path": request.url.path,
        "headers": redacted,
    }