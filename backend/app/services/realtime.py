from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass
from typing import AsyncIterator, Dict, Optional

from app.config import settings
from app.metrics import REALTIME_EVENTS_EMITTED, REALTIME_EVENTS_DROPPED, REALTIME_SSE_CONNECTIONS
from app.services.redis_service import get_client as get_redis_client


REALTIME_TRANSPORT = (getattr(settings, "REALTIME_TRANSPORT", None) or 
                      __import__("os").getenv("REALTIME_TRANSPORT", "off")).lower()
REALTIME_BACKEND = (__import__("os").getenv("REALTIME_BACKEND", "memory")).lower()


@dataclass
class RTEvent:
    type: str
    user_id: str
    payload: dict
    ts: float = time.time()

    def to_json(self) -> str:
        return json.dumps({
            "type": self.type,
            "userId": self.user_id,
            "payload": self.payload,
            "ts": self.ts,
        })


class _UserChannel:
    def __init__(self) -> None:
        self._q: asyncio.Queue[RTEvent] = asyncio.Queue(maxsize=256)
        self._closed = False

    async def put(self, ev: RTEvent) -> None:
        if self._closed:
            return
        try:
            self._q.put_nowait(ev)
        except asyncio.QueueFull:
            # drop oldest to keep stream fresh
            try:
                _ = self._q.get_nowait()
            except Exception:
                pass
            try:
                self._q.put_nowait(ev)
            except Exception:
                try:
                    REALTIME_EVENTS_DROPPED.labels(reason="queue_full").inc()
                except Exception:
                    pass

    async def stream(self) -> AsyncIterator[RTEvent]:
        try:
            while not self._closed:
                ev = await self._q.get()
                yield ev
        except asyncio.CancelledError:
            self._closed = True
            raise

    def close(self) -> None:
        self._closed = True


class RealTimeBus:
    """Realtime event bus supporting memory or Redis backend with SSE helpers."""

    def __init__(self) -> None:
        self._users: Dict[str, _UserChannel] = {}
        self.enabled = REALTIME_TRANSPORT in {"sse", "ws"}
        self.backend = REALTIME_BACKEND
        self._redis_task: Optional[asyncio.Task] = None

    def channel(self, user_id: str) -> _UserChannel:
        ch = self._users.get(user_id)
        if not ch:
            ch = _UserChannel()
            self._users[user_id] = ch
        return ch

    async def _emit_memory(self, ev: RTEvent) -> None:
        await self.channel(ev.user_id).put(ev)

    async def _emit_redis(self, ev: RTEvent) -> None:
        try:
            client = get_redis_client()
            if not client:
                return
            channel = f"rt:{ev.user_id}"
            # aioredis compatible: publish serialized event
            await client.publish(channel, ev.to_json())
        except Exception:
            pass

    async def emit(self, ev: RTEvent) -> None:
        if not self.enabled:
            return
        try:
            REALTIME_EVENTS_EMITTED.labels(type=ev.type).inc()
        except Exception:
            pass
        if self.backend == "redis":
            await self._emit_redis(ev)
        else:
            await self._emit_memory(ev)

    async def _subscribe_redis(self, user_id: str) -> AsyncIterator[RTEvent]:
        client = get_redis_client()
        if not client:
            # Fallback to memory channel
            async for ev in self.channel(user_id).stream():
                yield ev
            return
        try:
            pubsub = client.pubsub()
            await pubsub.subscribe(f"rt:{user_id}")
            try:
                while True:
                    msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                    if msg and msg.get("type") == "message":
                        try:
                            data = json.loads(msg.get("data"))
                            ev = RTEvent(type=data.get("type"), user_id=data.get("userId"), payload=data.get("payload"), ts=data.get("ts") or time.time())
                            yield ev
                        except Exception:
                            pass
                    else:
                        # idle
                        await asyncio.sleep(0.01)
            finally:
                try:
                    await pubsub.unsubscribe(f"rt:{user_id}")
                    await pubsub.close()
                except Exception:
                    pass
        except asyncio.CancelledError:
            raise
        except Exception:
            # Fallback to memory stream on error
            async for ev in self.channel(user_id).stream():
                yield ev

    async def sse_iter(self, user_id: str) -> AsyncIterator[str]:
        """Yield SSE formatted lines for the given user."""
        if not self.enabled:
            yield "event: disabled\n" "data: {}\n\n"
            return
        # Track connection count
        try:
            REALTIME_SSE_CONNECTIONS.inc()
        except Exception:
            pass
        # Send an initial ping
        try:
            ping_payload = json.dumps({"ok": True})
        except Exception:
            ping_payload = "{}"
        yield "event: ping\n" f"data: {ping_payload}\n\n"
        stream = None
        try:
            if self.backend == "redis":
                stream = self._subscribe_redis(user_id)
            else:
                stream = self.channel(user_id).stream()
            async for ev in stream:
                payload = ev.to_json()
                yield f"event: {ev.type}\n" f"data: {payload}\n\n"
        finally:
            try:
                REALTIME_SSE_CONNECTIONS.dec()
            except Exception:
                pass


realtime_bus = RealTimeBus()
