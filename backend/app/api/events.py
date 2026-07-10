"""Server-sent events stream for user-scoped realtime events."""
from __future__ import annotations

import asyncio
import json
import time
from contextlib import suppress
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from redis.exceptions import RedisError

from app.api.deps import get_current_user
from app.core.events import user_event_channel
from app.core.redis_client import get_redis
from app.models import User


router = APIRouter(prefix="/events", tags=["实时事件"])


def _sse(event: str, data: dict[str, Any] | None = None) -> str:
    return f"event: {event}\ndata: {json.dumps(data or {}, ensure_ascii=False)}\n\n"


@router.get("/stream")
async def stream_user_events(request: Request, current_user: User = Depends(get_current_user)):
    channel = user_event_channel(current_user.id)

    async def event_generator():
        redis_client = get_redis()
        pubsub = redis_client.pubsub()
        subscribed = False
        last_ping_at = time.monotonic()
        yield _sse("connected", {"user_id": current_user.id})
        try:
            try:
                await asyncio.wait_for(pubsub.subscribe(channel), timeout=2)
                subscribed = True
            except (asyncio.TimeoutError, RedisError):
                yield _sse("error", {"message": "实时事件服务暂不可用"})
                return

            while not await request.is_disconnected():
                try:
                    message = await asyncio.wait_for(
                        pubsub.get_message(ignore_subscribe_messages=True, timeout=1),
                        timeout=2,
                    )
                except (asyncio.TimeoutError, RedisError):
                    yield _sse("error", {"message": "实时事件服务暂不可用"})
                    break

                if message:
                    raw = message.get("data")
                    try:
                        payload = json.loads(raw)
                    except (TypeError, json.JSONDecodeError):
                        continue

                    event_type = payload.get("type") or "message"
                    event_data = payload.get("data") or {}
                    yield _sse(str(event_type), event_data)
                    await asyncio.sleep(0)
                    continue

                if time.monotonic() - last_ping_at >= 15:
                    yield _sse("ping")
                    last_ping_at = time.monotonic()
        except asyncio.CancelledError:
            raise
        finally:
            if subscribed:
                with suppress(Exception):
                    await pubsub.unsubscribe(channel)
            with suppress(Exception):
                await pubsub.close()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
