"""Simple per-user rate-limiting using Redis with a sliding window."""
import time
from typing import Optional
from fastapi import Request, HTTPException, status
from app.services.redis_service import redis_client


class RateLimiter:
    def __init__(self, max_requests: int = 60, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window = window_seconds

    async def __call__(self, request: Request, call_next):
        # Skip rate limiting for health checks and preflight
        if request.url.path.startswith("/health") or request.method == "OPTIONS":
            return await call_next(request)
        if not redis_client:
            return await call_next(request)  # No Redis, skip limit
        # Identify user via Authorization or IP
        auth = request.headers.get("authorization", "")
        user_key: Optional[str] = None
        if auth.startswith("Bearer "):
            # Token hash is sufficient; we don't decode here to avoid coupling
            user_key = auth[7:15]
        if not user_key:
            user_key = request.client.host if request.client else "anon"

        key = f"rate:{user_key}:{int(time.time() // self.window)}"
        try:
            count = await redis_client.incr(key)
            if count == 1:
                await redis_client.expire(key, self.window)
            if count > self.max_requests:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Rate limit exceeded. Please try again shortly.",
                )
        except HTTPException:
            raise
        except Exception:
            # If Redis fails, don't block the request
            return await call_next(request)
        return await call_next(request)
