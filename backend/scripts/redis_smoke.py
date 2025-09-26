"""Simple Redis connectivity smoke test.

Run inside the backend container:
    python scripts/redis_smoke.py
"""
import os
import redis

host = os.getenv("REDIS_HOST", "redis")
port = int(os.getenv("REDIS_PORT", "6379"))
db = int(os.getenv("REDIS_DB", "0"))
password = os.getenv("REDIS_PASSWORD") or None

print(f"Connecting to redis://{host}:{port}/{db} ...")
r = redis.Redis(host=host, port=port, db=db, password=password, decode_responses=True)
print("PING:", r.ping())
r.set("smoke:key", "ok", ex=60)
print("GET smoke:key:", r.get("smoke:key"))
print("Done.")
