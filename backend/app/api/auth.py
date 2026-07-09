"""
Authentication API
Login, logout, token management, MFA
"""
from datetime import datetime, timedelta
from typing import Optional
import json
import os
import secrets
import uuid
from io import BytesIO
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, status, Request, Response, UploadFile, File
from PIL import Image, UnidentifiedImageError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import User, LoginLog, Setting
from app.schemas import (
    LoginRequest, LoginResponse, TokenResponse, UserSimple, CurrentUserResponse,
    PasswordChangeRequest, ForcePasswordChangeRequest, ResponseBase,
    MFARequiredResponse, MFARequiredData, MFAVerifyRequest, MFASetupQRData,
    MustChangePasswordResponse, MustChangePasswordData,
)
from app.core.security import (
    verify_password, get_password_hash,
    generate_totp_secret, verify_totp, generate_totp_qr
)
from app.core.redis_client import get_redis
from app.core.session import create_user_session, delete_user_session, refresh_user_session
from app.core.password_policy import validate_password_strength_from_settings
from app.api.deps import AUTH_COOKIE_NAME, get_current_user, get_user_permissions, PermissionChecker
from app.config import settings
from app.utils.audit import log_operation


router = APIRouter(prefix="/auth", tags=["认证"])

LOGIN_CHALLENGE_KEY_PREFIX = "login:challenge:"
LOGIN_CHALLENGE_TTL_SECONDS = 600  # 10 minutes
LOGIN_FAILURE_KEY_PREFIX = "login:fail:"
LOGIN_LOCK_KEY_PREFIX = "login:lock:"


def _request_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _request_user_agent(request: Request) -> str | None:
    return request.headers.get("user-agent")


def _login_guard_key(username: str, request: Request) -> str:
    ip = _request_ip(request) or "unknown"
    return f"{username.strip().lower()}:{ip}"


async def _get_setting_value(db: AsyncSession, key: str, default):
    result = await db.execute(select(Setting).where(Setting.key == key))
    setting = result.scalar_one_or_none()
    if not setting or not isinstance(setting.value, dict):
        return default
    return setting.value.get("value", default)


async def _get_int_setting(db: AsyncSession, key: str, default: int, min_value: int, max_value: int) -> int:
    value = await _get_setting_value(db, key, default)
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(min_value, min(parsed, max_value))


async def _is_login_locked(username: str, request: Request) -> bool:
    redis_client = get_redis()
    return bool(await redis_client.get(f"{LOGIN_LOCK_KEY_PREFIX}{_login_guard_key(username, request)}"))


async def _record_failed_login(username: str, request: Request, db: AsyncSession) -> None:
    max_attempts = await _get_int_setting(db, "max_login_attempts", 5, 1, 50)
    lockout_minutes = await _get_int_setting(db, "lockout_duration", 30, 1, 1440)
    redis_client = get_redis()
    guard_key = _login_guard_key(username, request)
    fail_key = f"{LOGIN_FAILURE_KEY_PREFIX}{guard_key}"
    attempts = await redis_client.incr(fail_key)
    await redis_client.expire(fail_key, lockout_minutes * 60)
    if attempts >= max_attempts:
        await redis_client.setex(f"{LOGIN_LOCK_KEY_PREFIX}{guard_key}", lockout_minutes * 60, "1")
        await redis_client.delete(fail_key)


async def _clear_failed_login(username: str, request: Request) -> None:
    redis_client = get_redis()
    guard_key = _login_guard_key(username, request)
    await redis_client.delete(f"{LOGIN_FAILURE_KEY_PREFIX}{guard_key}")
    await redis_client.delete(f"{LOGIN_LOCK_KEY_PREFIX}{guard_key}")


def _set_auth_cookie(response: Response, request: Request, token: str, expires_delta: timedelta) -> None:
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=token,
        max_age=int(expires_delta.total_seconds()),
        httponly=True,
        secure=request.url.scheme == "https",
        samesite="lax",
        path="/",
    )


def _clear_auth_cookie(response: Response) -> None:
    response.delete_cookie(key=AUTH_COOKIE_NAME, path="/")


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

    session_minutes = await _get_int_setting(db, "session_timeout", 30, 1, 10080)
    expires_delta = timedelta(days=7) if remember else timedelta(minutes=session_minutes)
    session_id, expires_at = await create_user_session(user.id, request, expires_delta)
    _set_auth_cookie(response, request, session_id, expires_delta)
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
    _clear_auth_cookie(response)

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
    current_user: User = Depends(get_current_user),
):
    """
    Heartbeat — refresh online presence TTL (creates key if missing)
    """
    refreshed = await refresh_user_session(getattr(request.state, "session_id", None))
    if not refreshed:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="会话已失效")
    return ResponseBase(message="ok")


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

    # Update password
    current_user.password_hash = get_password_hash(data.new_password)

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

    user.password_hash = get_password_hash(data.new_password)
    user.must_change_password = False

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
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get current user info with permissions
    """
    permissions = await get_user_permissions(current_user, db)

    return CurrentUserResponse(
        data=UserSimple(
            id=current_user.id,
            username=current_user.username,
            full_name=current_user.full_name,
            email=current_user.email,
            avatar_url=current_user.avatar_url,
            is_superuser=current_user.is_superuser,
            permissions=permissions,
        )
    )


ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB


def _normalize_avatar_image(content: bytes, ext: str) -> bytes:
    format_map = {".png": "PNG", ".jpg": "JPEG", ".jpeg": "JPEG", ".gif": "GIF", ".webp": "WEBP"}
    try:
        with Image.open(BytesIO(content)) as image:
            image.load()
            output = BytesIO()
            save_format = format_map[ext]
            if save_format == "JPEG" and image.mode not in ("RGB", "L"):
                image = image.convert("RGB")
            image.save(output, format=save_format)
            return output.getvalue()
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="文件内容不是有效图片",
        ) from exc


@router.post("/avatar", response_model=ResponseBase)
async def upload_avatar(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload or update user avatar — any authenticated user can update their own."""
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的文件类型: {ext}",
        )

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"文件过大，最大 {MAX_FILE_SIZE // (1024 * 1024)}MB",
        )

    content = _normalize_avatar_image(content, ext)

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
    challenge_token: str,
    db: AsyncSession = Depends(get_db),
):
    """Generate temporary TOTP secret for a password-verified login challenge."""
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
        secret = user.mfa_secret

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

    if data.setup:
        user.mfa_secret = secret
        redis_client = get_redis()
        await redis_client.delete(f"{MFA_SETUP_KEY_PREFIX}{data.challenge_token}")

    await _delete_login_challenge(data.challenge_token)
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

    user.mfa_secret = None
    await db.commit()

    await log_operation(
        db, current_user.id, "update", "user", user.id,
        details={"name": "reset_mfa", "action": "mfa_reset"},
        ip_address=ip,
    )

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

    user.mfa_secret = None
    user.mfa_enabled = False
    await db.commit()

    await log_operation(
        db, current_user.id, "update", "user", user.id,
        details={"name": "disable_mfa", "action": "mfa_disable"},
        ip_address=ip,
    )

    return ResponseBase(message="MFA 已禁用")