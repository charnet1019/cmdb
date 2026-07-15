"""
Authentication API
Login, logout, token management, MFA
"""
from datetime import datetime, timedelta
from typing import Optional
import asyncio
import json
import logging
import os
import secrets
import uuid
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, status, Request, Response, UploadFile, File
from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import User, LoginLog, Setting
from app.schemas import (
    LoginRequest, LoginResponse, TokenResponse, UserSimple, CurrentUserResponse,
    PasswordChangeRequest, ForcePasswordChangeRequest, ResponseBase,
    MFARequiredResponse, MFARequiredData, MFAVerifyRequest, MFASetupQRData, MFASetupQRRequest,
    MustChangePasswordResponse, MustChangePasswordData,
)
from app.core.security import (
    verify_password, get_password_hash, get_dummy_password_hash,
    generate_totp_secret, verify_totp, generate_totp_qr
)
from app.core.redis_client import get_redis
from app.core.session import create_user_session, delete_user_session, refresh_user_session, extend_user_session, set_user_session_timeout
from app.core.password_policy import validate_password_strength_from_settings, check_password_not_reused, record_password_history
from app.core.encryption import encrypt_value, decrypt_value
from app.core.settings_helper import get_int_setting
from app.api.deps import get_current_user, get_user_permissions, PermissionChecker, set_auth_cookie, clear_auth_cookie
from app.config import settings
from app.utils.audit import log_operation
from app.utils.image_upload import MAX_IMAGE_FILE_SIZE, validate_image_extension, validate_image_size, normalize_image
from app.utils.rate_limit import check_mfa_verify_rate_limit, check_security_notification_email_rate_limit
from app.utils.smtp import load_smtp_config, build_mfa_security_email, send_smtp_message


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["认证"])

LOGIN_CHALLENGE_KEY_PREFIX = "login:challenge:"
LOGIN_CHALLENGE_TTL_SECONDS = 600  # 10 minutes
LOGIN_FAILURE_KEY_PREFIX = "login:fail:"
LOGIN_LOCK_KEY_PREFIX = "login:lock:"


def _decrypt_mfa_secret(value: str | None) -> str | None:
    """mfa_secret is stored Fernet-encrypted."""
    if not value:
        return None
    return decrypt_value(value)


def _request_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _request_user_agent(request: Request) -> str | None:
    return request.headers.get("user-agent")


def _login_guard_key(username: str, request: Request) -> str:
    ip = _request_ip(request) or "unknown"
    return f"{username.strip().lower()}:{ip}"


def _login_guard_username_key(username: str) -> str:
    # Username-only guard: catches an attacker rotating IPs, which the
    # username+ip guard above cannot detect on its own.
    return username.strip().lower()


async def _is_login_locked(username: str, request: Request) -> bool:
    redis_client = get_redis()
    guard_key = _login_guard_key(username, request)
    username_key = _login_guard_username_key(username)
    locked_ip, locked_username = await redis_client.mget(
        f"{LOGIN_LOCK_KEY_PREFIX}{guard_key}",
        f"{LOGIN_LOCK_KEY_PREFIX}{username_key}",
    )
    return bool(locked_ip or locked_username)


async def _record_failed_login(username: str, request: Request, db: AsyncSession) -> None:
    max_attempts = await get_int_setting(db, "max_login_attempts", 5, 1, 50)
    lockout_minutes = await get_int_setting(db, "lockout_duration", 30, 1, 1440)
    redis_client = get_redis()
    lockout_seconds = lockout_minutes * 60

    for guard_key in (_login_guard_key(username, request), _login_guard_username_key(username)):
        fail_key = f"{LOGIN_FAILURE_KEY_PREFIX}{guard_key}"
        attempts = await redis_client.incr(fail_key)
        await redis_client.expire(fail_key, lockout_seconds)
        if attempts >= max_attempts:
            await redis_client.setex(f"{LOGIN_LOCK_KEY_PREFIX}{guard_key}", lockout_seconds, "1")
            await redis_client.delete(fail_key)


async def _clear_failed_login(username: str, request: Request) -> None:
    redis_client = get_redis()
    for guard_key in (_login_guard_key(username, request), _login_guard_username_key(username)):
        await redis_client.delete(f"{LOGIN_FAILURE_KEY_PREFIX}{guard_key}")
        await redis_client.delete(f"{LOGIN_LOCK_KEY_PREFIX}{guard_key}")


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


@router.post("/login")
async def login(
    request: Request,
    response: Response,
    data: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    User login endpoint — two phase: password check, then MFA if enabled
    """
    try:
        return await _login_impl(request, response, data, db)
    except RedisError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="会话服务暂不可用，请检查 Redis 连接后重试",
        ) from exc


async def _login_impl(
    request: Request,
    response: Response,
    data: LoginRequest,
    db: AsyncSession,
):
    if await _is_login_locked(data.username, request):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="登录失败次数过多，请稍后再试",
        )

    # Find user by username or email
    result = await db.execute(
        select(User).where(
            (User.username == data.username) | (User.email == data.username)
        )
    )
    user = result.scalar_one_or_none()

    # Log login attempt
    login_log = LoginLog(
        user_id=user.id if user else None,
        username=data.username,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        status="failed",
    )

    if not user:
        # Run a bcrypt comparison against a dummy hash so the response time
        # for an unknown username matches a wrong-password attempt — otherwise
        # the timing difference reveals whether the username exists.
        verify_password(data.password, get_dummy_password_hash())
        login_log.failure_reason = "用户不存在"
        db.add(login_log)
        await _record_failed_login(data.username, request, db)
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误"
        )

    if not user.is_active:
        login_log.failure_reason = "用户已被禁用"
        db.add(login_log)
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户已被禁用"
        )

    if not verify_password(data.password, user.password_hash):
        login_log.failure_reason = "密码错误"
        db.add(login_log)
        await _record_failed_login(data.username, request, db)
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误"
        )

    await _clear_failed_login(data.username, request)

    if user.must_change_password or user.mfa_enabled:
        challenge_token = await _create_login_challenge(user, request, data.remember)
        await db.commit()
        if user.must_change_password:
            return MustChangePasswordResponse(
                data=MustChangePasswordData(
                    must_change_password=True,
                    challenge_token=challenge_token,
                )
            )
        return MFARequiredResponse(
            data=MFARequiredData(
                requires_mfa=True,
                challenge_token=challenge_token,
                setup=not bool(user.mfa_secret),
            )
        )

    return await _complete_login(request, response, user, db, remember=data.remember)


@router.post("/logout", response_model=ResponseBase)
async def logout(
    response: Response,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    request: Request = None,
):
    """
    User logout endpoint — remove online presence
    """
    ip = request.client.host if request and request.client else None
    await delete_user_session(getattr(request.state, "session_id", None), current_user.id)
    clear_auth_cookie(response)

    # Audit log
    await log_operation(
        db, current_user.id, "update", "auth", 0,
        details={
            "name": "logout",
            "action": "logout",
        },
        ip_address=ip,
    )

    return ResponseBase(message="登出成功")


@router.post("/heartbeat", response_model=ResponseBase)
async def heartbeat(
    request: Request,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Heartbeat — refresh online presence, and extend idle expiry only when
    the browser reports real user activity since the previous heartbeat.
    """
    session_id = getattr(request.state, "session_id", None)
    user_active = request.headers.get("x-cmdb-user-active") == "1"
    session_payload = await (extend_user_session(session_id) if user_active else refresh_user_session(session_id))
    if not session_payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="会话已失效")

    if not isinstance(session_payload, dict):
        session_payload = getattr(request.state, "session", {}) or {}

    remember = bool(session_payload.get("remember"))
    session_minutes = await get_int_setting(db, "session_timeout", 30, 1, 10080)
    configured_timeout_seconds = session_minutes * 60
    try:
        timeout_seconds = int(session_payload.get("timeout_seconds") or 0)
    except (TypeError, ValueError):
        timeout_seconds = 0

    if not remember and timeout_seconds != configured_timeout_seconds:
        updated_payload = await set_user_session_timeout(session_id, timedelta(seconds=configured_timeout_seconds))
        if updated_payload:
            session_payload = updated_payload
            timeout_seconds = configured_timeout_seconds

    expires_at = session_payload.get("expires_at")
    cookie_seconds = timeout_seconds if remember and timeout_seconds > 0 else configured_timeout_seconds
    if user_active or not remember:
        set_auth_cookie(response, request, session_id, cookie_seconds)

    return ResponseBase(message="ok", data={"expires_at": expires_at})


@router.post("/change-password", response_model=ResponseBase)
async def change_password(
    request: Request,
    data: PasswordChangeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Change user password
    """
    # Verify old password
    if not verify_password(data.old_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="原密码错误"
        )

    # Verify new password matches confirmation
    if data.new_password != data.confirm_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="新密码与确认密码不一致"
        )

    if verify_password(data.new_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="新密码不能与当前密码相同"
        )

    # Validate password strength
    is_valid, errors = await validate_password_strength_from_settings(data.new_password, db)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="; ".join(errors)
        )

    await check_password_not_reused(data.new_password, current_user.id, db)

    # Update password
    new_password_hash = get_password_hash(data.new_password)
    current_user.password_hash = new_password_hash
    await record_password_history(new_password_hash, current_user.id, db)

    # Log password change
    from app.models import PasswordChangeLog
    password_log = PasswordChangeLog(
        user_id=current_user.id,
        change_type="user_password",
        changed_by=current_user.id,
        ip_address=request.client.host if request.client else None,
    )
    db.add(password_log)

    await db.commit()

    return ResponseBase(message="密码修改成功")


@router.post("/force-change-password")
async def force_change_password(
    request: Request,
    response: Response,
    data: "ForcePasswordChangeRequest",
    db: AsyncSession = Depends(get_db),
):
    """Force password change after the account password has been verified."""
    payload = await _load_login_challenge(data.challenge_token, request)
    user = await _get_challenge_user(payload, db)

    if not user.must_change_password:
        await _delete_login_challenge(data.challenge_token)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权执行此操作",
        )

    if data.new_password != data.confirm_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="两次输入的密码不一致",
        )

    if verify_password(data.new_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="新密码不能与当前密码相同",
        )

    is_valid, errors = await validate_password_strength_from_settings(data.new_password, db)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="; ".join(errors),
        )

    await check_password_not_reused(data.new_password, user.id, db)

    new_password_hash = get_password_hash(data.new_password)
    user.password_hash = new_password_hash
    user.must_change_password = False
    await record_password_history(new_password_hash, user.id, db)

    from app.models import PasswordChangeLog
    password_log = PasswordChangeLog(
        user_id=user.id,
        change_type="user_password",
        changed_by=user.id,
        ip_address=_request_ip(request),
    )
    db.add(password_log)

    await db.commit()
    await db.refresh(user)

    if user.mfa_enabled:
        await _save_login_challenge(data.challenge_token, payload)
        return MFARequiredResponse(
            data=MFARequiredData(
                requires_mfa=True,
                challenge_token=data.challenge_token,
                setup=not bool(user.mfa_secret),
            )
        )

    await _delete_login_challenge(data.challenge_token)
    return await _complete_login(request, response, user, db, remember=bool(payload.get("remember")))


@router.get("/me", response_model=CurrentUserResponse)
async def get_current_user_info(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get current user info with permissions
    """
    permissions = await get_user_permissions(current_user, db)
    session_payload = getattr(request.state, "session", {}) or {}

    return CurrentUserResponse(
        data=UserSimple(
            id=current_user.id,
            username=current_user.username,
            full_name=current_user.full_name,
            email=current_user.email,
            avatar_url=current_user.avatar_url,
            is_superuser=current_user.is_superuser,
            permissions=permissions,
            session_expires_at=session_payload.get("expires_at"),
        )
    )


@router.post("/avatar", response_model=ResponseBase)
async def upload_avatar(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload or update user avatar — any authenticated user can update their own."""
    ext = os.path.splitext(file.filename or "")[1].lower()
    validate_image_extension(ext, f"不支持的文件类型: {ext}")

    content = await file.read()
    validate_image_size(content, f"文件过大，最大 {MAX_IMAGE_FILE_SIZE // (1024 * 1024)}MB")

    content = normalize_image(content, ext)

    upload_dir = Path(settings.UPLOAD_DIR) / "avatars"
    upload_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{current_user.id}_{uuid.uuid4().hex}{ext}"
    file_path = upload_dir / filename

    # Delete old avatar if exists
    if current_user.avatar_url:
        old_filename = current_user.avatar_url.split("/")[-1]
        old_path = upload_dir / old_filename
        if old_path.exists():
            old_path.unlink()

    file_path.write_bytes(content)
    avatar_url = f"/uploads/avatars/{filename}"
    current_user.avatar_url = avatar_url
    await db.commit()

    return ResponseBase(message="头像上传成功", data={"avatar_url": avatar_url})


@router.delete("/avatar", response_model=ResponseBase)
async def delete_avatar(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete user avatar — any authenticated user can delete their own."""
    if not current_user.avatar_url:
        return ResponseBase(message="没有头像可删除")

    upload_dir = Path(settings.UPLOAD_DIR) / "avatars"
    filename = current_user.avatar_url.split("/")[-1]
    file_path = upload_dir / filename
    if file_path.exists():
        file_path.unlink()

    current_user.avatar_url = None
    await db.commit()

    return ResponseBase(message="头像已删除")


# ============== MFA Endpoints ==============

MFA_SETUP_KEY_PREFIX = "mfa:setup:"
MFA_SETUP_TTL = 300  # 5 minutes


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