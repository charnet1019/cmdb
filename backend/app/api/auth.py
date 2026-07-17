"""
Authentication API
Login, logout, token management, session, password change
"""
from datetime import timedelta
import os
import uuid
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, status, Request, Response, UploadFile, File
from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import User, LoginLog
from app.schemas import (
    LoginRequest, LoginResponse, TokenResponse, UserSimple, CurrentUserResponse,
    PasswordChangeRequest, ForcePasswordChangeRequest, ResponseBase,
    MFARequiredResponse, MFARequiredData,
    MustChangePasswordResponse, MustChangePasswordData,
)
from app.core.security import verify_password, get_password_hash, get_dummy_password_hash
from app.core.redis_client import get_redis
from app.core.session import delete_user_session, refresh_user_session, extend_user_session, set_user_session_timeout
from app.core.password_policy import validate_password_strength_from_settings, check_password_not_reused, record_password_history
from app.core.settings_helper import get_int_setting
from app.api.deps import get_current_user, get_user_permissions, set_auth_cookie, clear_auth_cookie
from app.api.auth_helpers import (
    _request_ip,
    _create_login_challenge,
    _load_login_challenge,
    _save_login_challenge,
    _delete_login_challenge,
    _get_challenge_user,
    _complete_login,
)
from app.config import settings
from app.utils.audit import log_operation
from app.utils.image_upload import MAX_IMAGE_FILE_SIZE, validate_image_extension, validate_image_size, normalize_image


router = APIRouter(prefix="/auth", tags=["认证"])

LOGIN_FAILURE_KEY_PREFIX = "login:fail:"
LOGIN_LOCK_KEY_PREFIX = "login:lock:"


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
