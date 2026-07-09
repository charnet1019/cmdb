"""Server-sent events stream for user-scoped realtime events."""
from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.api.deps import get_current_user
from app.core.events import user_event_channel
from app.core.redis_client import get_redis
from app.models import User


router = APIRouter(prefix="/events", tags=["实时事件"])


def _sse(event: str, data: dict[str, Any] | None = None) -> str:
    return f"event: {event}\ndata: {json.dumps(data or {}, ensure_ascii=False)}\n\n"


@router.get("/stream")
async def stream_user_events(current_user: User = Depends(get_current_user)):
    channel = user_event_channel(current_user.id)

    async def event_generator():
        redis_client = get_redis()
        pubsub = redis_client.pubsub()
        await pubsub.subscribe(channel)
        try:
            yield _sse("connected", {"user_id": current_user.id})
            while True:
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=20)
                if not message:
                    yield _sse("ping")
                    continue

                raw = message.get("data")
                try:
                    payload = json.loads(raw)
                except (TypeError, json.JSONDecodeError):
                    continue

                event_type = payload.get("type") or "message"
                event_data = payload.get("data") or {}
                yield _sse(str(event_type), event_data)
                await asyncio.sleep(0)
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.close()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
