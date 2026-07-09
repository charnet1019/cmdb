"""Redis-backed user event publishing for SSE consumers."""
from __future__ import annotations

import json
from typing import Any

from app.core.redis_client import get_redis


USER_EVENT_CHANNEL_PREFIX = "events:user:"


def user_event_channel(user_id: int) -> str:
    return f"{USER_EVENT_CHANNEL_PREFIX}{user_id}"


async def publish_user_event(user_id: int, event_type: str, data: dict[str, Any] | None = None) -> int:
    payload = {
        "type": event_type,
        "data": data or {},
    }
    return await get_redis().publish(
        user_event_channel(user_id),
        json.dumps(payload, ensure_ascii=False),
    )
