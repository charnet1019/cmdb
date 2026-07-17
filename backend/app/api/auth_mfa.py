"""
MFA (Multi-Factor Authentication) API
TOTP setup, login verification, and admin reset/disable
"""
import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import User, LoginLog, Setting
from app.schemas import (
    LoginResponse, ResponseBase,
    MFAVerifyRequest, MFASetupQRData, MFASetupQRRequest,
)
from app.core.security import generate_totp_secret, verify_totp, generate_totp_qr
from app.core.redis_client import get_redis
from app.core.encryption import encrypt_value, decrypt_value
from app.api.deps import PermissionChecker
from app.api.auth_helpers import (
    MFA_SETUP_KEY_PREFIX,
    _request_ip,
    _load_login_challenge,
    _delete_login_challenge,
    _save_login_challenge,
    _get_challenge_user,
    _complete_login,
)
from app.config import settings
from app.utils.audit import log_operation
from app.utils.rate_limit import check_mfa_verify_rate_limit, check_security_notification_email_rate_limit
from app.utils.smtp import load_smtp_config, build_mfa_security_email, send_smtp_message


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["认证"])

MFA_SETUP_TTL = 300  # 5 minutes


def _decrypt_mfa_secret(value: str | None) -> str | None:
    """mfa_secret is stored Fernet-encrypted."""
    if not value:
        return None
    return decrypt_value(value)


def _send_mfa_security_email_sync(config: dict, recipient_email: str, username: str, action: str) -> None:
    msg = build_mfa_security_email(config, recipient_email, username, action)
    send_smtp_message(config, msg)


async def _notify_mfa_security_change(db: AsyncSession, user: User, action: str) -> None:
    """Best-effort email to the affected user when an admin resets/disables
    their MFA — an attacker who compromises an admin account and strips a
    target's MFA should not be able to do so silently."""
    try:
        config = await load_smtp_config(db)
        if not config["host"] or not config["from_email"]:
            return
        await check_security_notification_email_rate_limit(user.id)
        await asyncio.to_thread(_send_mfa_security_email_sync, config, user.email, user.username, action)
    except HTTPException:
        pass
    except Exception as exc:
        logger.warning("MFA security notification email failed for user_id=%s action=%s: %s", user.id, action, exc)


@router.post("/mfa/setup-qr")
async def mfa_setup_qr(
    request: Request,
    data: MFASetupQRRequest,
    db: AsyncSession = Depends(get_db),
):
    """Generate temporary TOTP secret for a password-verified login challenge."""
    challenge_token = data.challenge_token
    await check_mfa_verify_rate_limit(challenge_token)
    payload = await _load_login_challenge(challenge_token, request)
    user = await _get_challenge_user(payload, db)

    if user.must_change_password:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="请先修改密码")

    if not user.mfa_enabled or user.mfa_secret:
        raise HTTPException(status_code=400, detail="MFA 未启用或已绑定")

    secret = generate_totp_secret()

    redis_client = get_redis()
    await redis_client.setex(f"{MFA_SETUP_KEY_PREFIX}{challenge_token}", MFA_SETUP_TTL, secret)

    issuer_result = await db.execute(select(Setting).where(Setting.key == "otp_issuer_name"))
    issuer_setting = issuer_result.scalar_one_or_none()
    issuer = issuer_setting.value.get("value") if issuer_setting else settings.OTP_ISSUER_NAME
    qr_code = generate_totp_qr(secret, user.username, issuer)

    return ResponseBase(data=MFASetupQRData(qr_code=qr_code).model_dump(exclude_none=True))


@router.post("/mfa/login-verify", response_model=LoginResponse)
async def login_mfa_verify(
    request: Request,
    response: Response,
    data: MFAVerifyRequest,
    db: AsyncSession = Depends(get_db),
):
    """Second phase of login: verify TOTP code and issue token.

    If setup=True, the secret was stored temporarily in Redis during the binding flow.
    If setup=False, the secret is already persisted in the database.
    """
    await check_mfa_verify_rate_limit(data.challenge_token)
    payload = await _load_login_challenge(data.challenge_token, request)
    user = await _get_challenge_user(payload, db)

    if user.must_change_password:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="请先修改密码")

    if not user.mfa_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户未启用 MFA",
        )

    secret: Optional[str] = None
    if data.setup:
        redis_client = get_redis()
        secret = await redis_client.get(f"{MFA_SETUP_KEY_PREFIX}{data.challenge_token}")
        if not secret:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="MFA 绑定已过期，请重试",
            )
    else:
        secret = _decrypt_mfa_secret(user.mfa_secret)

    if not secret or not verify_totp(secret, data.code):
        login_log = LoginLog(
            user_id=user.id,
            username=user.username,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            status="failed",
            failure_reason="MFA 验证码错误",
        )
        db.add(login_log)
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="MFA 验证码错误",
        )

    mfa_bound_before = bool(user.mfa_secret)
    if data.setup:
        user.mfa_secret = encrypt_value(secret)
        redis_client = get_redis()
        await redis_client.delete(f"{MFA_SETUP_KEY_PREFIX}{data.challenge_token}")

    await _delete_login_challenge(data.challenge_token)
    if data.setup:
        await log_operation(
            db, user.id, "update", "user", user.id,
            details={
                "name": "bind_mfa",
                "action": "mfa_bind",
                "username": user.username,
                "changes": {
                    "mfa_bound": [mfa_bound_before, bool(user.mfa_secret)],
                },
            },
            ip_address=_request_ip(request),
        )
    return await _complete_login(request, response, user, db, remember=bool(payload.get("remember")))


@router.post("/mfa/reset", response_model=ResponseBase)
async def reset_mfa(
    request: Request,
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("user_mgmt")),
):
    """Admin: reset MFA binding — clear secret, keep mfa_enabled=True."""
    ip = request.client.host if request.client else None
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    if not user.mfa_enabled:
        return ResponseBase(message="该用户未启用 MFA")

    mfa_bound_before = bool(user.mfa_secret)
    user.mfa_secret = None
    await db.commit()

    await log_operation(
        db, current_user.id, "update", "user", user.id,
        details={
            "name": "reset_mfa",
            "action": "mfa_reset",
            "username": user.username,
            "changes": {
                "mfa_bound": [mfa_bound_before, False],
                "mfa_enabled": [True, True],
            },
        },
        ip_address=ip,
    )

    await _notify_mfa_security_change(db, user, "reset")

    return ResponseBase(message="MFA 已重置，用户下次登录需重新绑定")


@router.post("/mfa/disable", response_model=ResponseBase)
async def disable_mfa(
    request: Request,
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("user_mgmt")),
):
    """Admin: disable MFA for a user."""
    ip = request.client.host if request.client else None
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    if not user.mfa_enabled:
        return ResponseBase(message="该用户未启用 MFA")

    mfa_bound_before = bool(user.mfa_secret)
    mfa_enabled_before = user.mfa_enabled
    user.mfa_secret = None
    user.mfa_enabled = False
    await db.commit()

    await log_operation(
        db, current_user.id, "update", "user", user.id,
        details={
            "name": "disable_mfa",
            "action": "mfa_disable",
            "username": user.username,
            "changes": {
                "mfa_enabled": [mfa_enabled_before, False],
                "mfa_bound": [mfa_bound_before, False],
            },
        },
        ip_address=ip,
    )

    await _notify_mfa_security_change(db, user, "disable")

    return ResponseBase(message="MFA 已禁用")
