"""
Auth Helpers
Shared login-challenge and session-completion helpers used by both
core login/password flows (auth.py) and MFA verification (auth_mfa.py).
"""
from datetime import datetime, timedelta
import json
import secrets

from fastapi import HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import User, LoginLog
from app.schemas import LoginResponse, TokenResponse, UserSimple
from app.core.redis_client import get_redis
from app.core.session import create_user_session
from app.core.settings_helper import get_int_setting
from app.api.deps import get_user_permissions, set_auth_cookie

LOGIN_CHALLENGE_KEY_PREFIX = "login:challenge:"
LOGIN_CHALLENGE_TTL_SECONDS = 600  # 10 minutes
MFA_SETUP_KEY_PREFIX = "mfa:setup:"


def _request_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _request_user_agent(request: Request) -> str | None:
    return request.headers.get("user-agent")


async def _create_login_challenge(user: User, request: Request, remember: bool) -> str:
    token = secrets.token_urlsafe(32)
    payload = {
        "user_id": user.id,
        "remember": remember,
        "ip_address": _request_ip(request),
        "user_agent": _request_user_agent(request),
        "password_verified": True,
    }
    redis_client = get_redis()
    await redis_client.setex(
        f"{LOGIN_CHALLENGE_KEY_PREFIX}{token}",
        LOGIN_CHALLENGE_TTL_SECONDS,
        json.dumps(payload),
    )
    return token


async def _load_login_challenge(token: str, request: Request) -> dict:
    if not token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="登录验证已失效，请重新登录")

    redis_client = get_redis()
    raw = await redis_client.get(f"{LOGIN_CHALLENGE_KEY_PREFIX}{token}")
    if not raw:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="登录验证已失效，请重新登录")

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        await redis_client.delete(f"{LOGIN_CHALLENGE_KEY_PREFIX}{token}")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="登录验证已失效，请重新登录")

    if payload.get("ip_address") != _request_ip(request) or payload.get("user_agent") != _request_user_agent(request):
        await redis_client.delete(f"{LOGIN_CHALLENGE_KEY_PREFIX}{token}")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="登录验证已失效，请重新登录")

    if not payload.get("password_verified") or not payload.get("user_id"):
        await redis_client.delete(f"{LOGIN_CHALLENGE_KEY_PREFIX}{token}")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="登录验证已失效，请重新登录")

    return payload


async def _save_login_challenge(token: str, payload: dict) -> None:
    redis_client = get_redis()
    await redis_client.setex(
        f"{LOGIN_CHALLENGE_KEY_PREFIX}{token}",
        LOGIN_CHALLENGE_TTL_SECONDS,
        json.dumps(payload),
    )


async def _delete_login_challenge(token: str) -> None:
    redis_client = get_redis()
    await redis_client.delete(f"{LOGIN_CHALLENGE_KEY_PREFIX}{token}")
    await redis_client.delete(f"{MFA_SETUP_KEY_PREFIX}{token}")


async def _get_challenge_user(payload: dict, db: AsyncSession) -> User:
    result = await db.execute(select(User).where(User.id == payload.get("user_id")))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="登录验证已失效，请重新登录")
    return user


async def _complete_login(
    request: Request,
    response: Response,
    user: User,
    db: AsyncSession,
    remember: bool = False,
) -> LoginResponse:
    user.last_login_at = datetime.utcnow()
    user.last_login_ip = _request_ip(request)

    login_log = LoginLog(
        user_id=user.id,
        username=user.username,
        ip_address=_request_ip(request),
        user_agent=_request_user_agent(request),
        status="success",
    )
    db.add(login_log)

    await db.commit()
    await db.refresh(user)

    session_minutes = await get_int_setting(db, "session_timeout", 30, 1, 10080)
    expires_delta = timedelta(days=7) if remember else timedelta(minutes=session_minutes)
    session_id, expires_at = await create_user_session(user.id, request, expires_delta, remember=remember)
    set_auth_cookie(response, request, session_id, int(expires_delta.total_seconds()))
    user_permissions = await get_user_permissions(user, db)

    return LoginResponse(
        data=TokenResponse(
            access_token=None,
            expires_at=expires_at,
            user=UserSimple(
                id=user.id,
                username=user.username,
                full_name=user.full_name,
                email=user.email,
                avatar_url=user.avatar_url,
                is_superuser=user.is_superuser,
                permissions=user_permissions,
            )
        )
    )
