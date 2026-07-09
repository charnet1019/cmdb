"""Server-side Redis session management."""
from __future__ import annotations

import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import Request

from app.core.redis_client import get_redis, ONLINE_KEY_PREFIX, ONLINE_TTL_SECONDS


SESSION_KEY_PREFIX = "session:"
USER_SESSIONS_KEY_PREFIX = "user:sessions:"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _format_utc(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds") + "Z"


def _parse_utc(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _request_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _request_user_agent(request: Request) -> str | None:
    return request.headers.get("user-agent")


def _session_key(session_id: str) -> str:
    return f"{SESSION_KEY_PREFIX}{session_id}"


def _user_sessions_key(user_id: int) -> str:
    return f"{USER_SESSIONS_KEY_PREFIX}{user_id}"


async def _expire_user_session_set(user_id: int, ttl_seconds: int) -> None:
    redis_client = get_redis()
    key = _user_sessions_key(user_id)
    current_ttl = await redis_client.ttl(key)
    if current_ttl is None or current_ttl < ttl_seconds:
        await redis_client.expire(key, ttl_seconds)


async def create_user_session(
    user_id: int,
    request: Request,
    expires_delta: timedelta,
) -> tuple[str, datetime]:
    """Create a Redis-backed login session and return (session_id, expires_at)."""
    redis_client = get_redis()
    session_id = secrets.token_urlsafe(32)
    now = _utc_now()
    expires_at = now + expires_delta
    ttl_seconds = max(1, int(expires_delta.total_seconds()))
    payload: dict[str, Any] = {
        "session_id": session_id,
        "user_id": user_id,
        "ip_address": _request_ip(request),
        "user_agent": _request_user_agent(request),
        "created_at": _format_utc(now),
        "last_seen_at": _format_utc(now),
        "expires_at": _format_utc(expires_at),
    }

    await redis_client.setex(_session_key(session_id), ttl_seconds, json.dumps(payload))
    await redis_client.sadd(_user_sessions_key(user_id), session_id)
    await _expire_user_session_set(user_id, ttl_seconds)
    await redis_client.setex(f"{ONLINE_KEY_PREFIX}{user_id}", ONLINE_TTL_SECONDS, "1")
    return session_id, expires_at


async def load_user_session(session_id: str | None) -> dict[str, Any] | None:
    """Load a session payload, returning None for missing or expired sessions."""
    if not session_id:
        return None

    redis_client = get_redis()
    raw = await redis_client.get(_session_key(session_id))
    if not raw:
        return None

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        await redis_client.delete(_session_key(session_id))
        return None

    expires_at = _parse_utc(payload.get("expires_at"))
    user_id = payload.get("user_id")
    if not expires_at or expires_at <= _utc_now():
        await delete_user_session(session_id, int(user_id) if user_id is not None else None)
        return None

    return payload


async def refresh_user_session(session_id: str | None) -> bool:
    """Refresh presence and session TTL without extending absolute expiry."""
    payload = await load_user_session(session_id)
    if not payload:
        return False

    user_id = int(payload["user_id"])
    expires_at = _parse_utc(payload.get("expires_at"))
    if not expires_at:
        return False

    remaining_seconds = max(1, int((expires_at - _utc_now()).total_seconds()))
    payload["last_seen_at"] = _format_utc(_utc_now())

    redis_client = get_redis()
    await redis_client.setex(_session_key(session_id), remaining_seconds, json.dumps(payload))
    await redis_client.sadd(_user_sessions_key(user_id), session_id)
    await _expire_user_session_set(user_id, remaining_seconds)
    await redis_client.setex(f"{ONLINE_KEY_PREFIX}{user_id}", ONLINE_TTL_SECONDS, "1")
    return True


async def get_active_user_session_ids(user_id: int) -> list[str]:
    """Return active session IDs for a user and prune stale set members."""
    redis_client = get_redis()
    key = _user_sessions_key(user_id)
    session_ids = list(await redis_client.smembers(key))
    active: list[str] = []
    for session_id in session_ids:
        if await redis_client.exists(_session_key(session_id)):
            active.append(session_id)
        else:
            await redis_client.srem(key, session_id)
    return active


async def delete_user_session(session_id: str | None, user_id: int | None = None) -> bool:
    """Delete one session. Online presence is kept if other sessions remain."""
    if not session_id:
        return False

    redis_client = get_redis()
    payload = None
    if user_id is None:
        raw = await redis_client.get(_session_key(session_id))
        if raw:
            try:
                payload = json.loads(raw)
                user_id = int(payload["user_id"])
            except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                user_id = None

    deleted = bool(await redis_client.delete(_session_key(session_id)))
    if user_id is not None:
        await redis_client.srem(_user_sessions_key(user_id), session_id)
        if not await get_active_user_session_ids(user_id):
            await redis_client.delete(f"{ONLINE_KEY_PREFIX}{user_id}")
            await redis_client.delete(_user_sessions_key(user_id))
    return deleted


async def force_logout_user(user_id: int) -> int:
    """Delete all sessions and online presence for a user."""
    redis_client = get_redis()
    session_ids = list(await redis_client.smembers(_user_sessions_key(user_id)))
    if session_ids:
        await redis_client.delete(*[_session_key(session_id) for session_id in session_ids])
    await redis_client.delete(_user_sessions_key(user_id))
    await redis_client.delete(f"{ONLINE_KEY_PREFIX}{user_id}")
    return len(session_ids)
