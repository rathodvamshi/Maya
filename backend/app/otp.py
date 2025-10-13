# backend/app/otp.py

import redis.asyncio as redis
from app.config import settings

redis_client = redis.from_url(
    f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}",
    decode_responses=True
)

async def is_otp_verified_for_email(email: str) -> bool:
    return await redis_client.get(f"verified:{email}") == "1"
