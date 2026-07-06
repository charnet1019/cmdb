"""
Authentication API
Login, logout, token management, MFA
"""
from datetime import datetime, timedelta
from typing import Optional
import os
import uuid
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, status, Request, UploadFile, File
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
    verify_password, create_access_token, get_password_hash, validate_password_strength,
    generate_totp_secret, verify_totp, generate_totp_qr
)
from app.core.redis_client import get_redis, ONLINE_KEY_PREFIX, ONLINE_TTL_SECONDS
from app.api.deps import get_current_user, get_user_permissions, PermissionChecker
from app.config import settings
from app.utils.audit import log_operation


router = APIRouter(prefix="/auth", tags=["认证"])


@router.post("/login")
async def login(
    request: Request,
    data: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    User login endpoint — two phase: password check, then MFA if enabled
    """
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
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误"
        )

    # Must change password — block normal login
    if user.must_change_password:
        await db.commit()
        return MustChangePasswordResponse(
            data=MustChangePasswordData(
                must_change_password=True,
                user_id=user.id,
            )
        )

    # MFA enabled — return requires_mfa instead of token
    if user.mfa_enabled:
        await db.commit()
        setup = not bool(user.mfa_secret)  # No secret = first-time binding
        return MFARequiredResponse(
            data=MFARequiredData(
                requires_mfa=True,
                user_id=user.id,
                setup=setup,
            )
        )

    # No MFA — complete login
    user.last_login_at = datetime.utcnow()
    user.last_login_ip = request.client.host if request.client else None

    # Mark login success
    login_log.status = "success"
    db.add(login_log)

    await db.commit()
    await db.refresh(user)

    # Mark user as online in Redis
    redis_client = get_redis()
    await redis_client.setex(
        f"{ONLINE_KEY_PREFIX}{user.id}",
        ONLINE_TTL_SECONDS,
        "1",
    )

    # Create access token
    expires_delta = timedelta(hours=settings.JWT_ACCESS_TOKEN_EXPIRE_HOURS)
    if data.remember:
        expires_delta = timedelta(days=7)

    access_token = create_access_token(
        subject=user.id,
        expires_delta=expires_delta,
    )

    expires_at = datetime.utcnow() + expires_delta

    # Get user permissions
    user_permissions = await get_user_permissions(user, db)

    return LoginResponse(
        data=TokenResponse(
            access_token=access_token,
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


@router.post("/logout", response_model=ResponseBase)
async def logout(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    request: Request = None,
):
    """
    User logout endpoint — remove online presence
    """
    ip = request.client.host if request and request.client else None
    redis_client = get_redis()
    await redis_client.delete(f"{ONLINE_KEY_PREFIX}{current_user.id}")

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
    current_user: User = Depends(get_current_user),
):
    """
    Heartbeat — refresh online presence TTL (creates key if missing)
    """
    redis_client = get_redis()
    await redis_client.setex(
        f"{ONLINE_KEY_PREFIX}{current_user.id}",
        ONLINE_TTL_SECONDS,
        "1",
    )
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

    # Validate password strength
    is_valid, errors = validate_password_strength(data.new_password)
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


@router.post("/force-change-password", response_model=LoginResponse)
async def force_change_password(
    request: Request,
    data: "ForcePasswordChangeRequest",
    db: AsyncSession = Depends(get_db),
):
    """Force password change for users with must_change_password flag.

    No current password required — the must_change_password flag gates access.
    After changing, returns a new access token to complete the login.
    """
    result = await db.execute(select(User).where(User.id == data.user_id))
    user = result.scalar_one_or_none()

    if not user or not user.must_change_password:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权执行此操作",
        )

    if data.new_password != data.confirm_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="两次输入的密码不一致",
        )

    # Validate password strength
    is_valid, errors = validate_password_strength(data.new_password)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="; ".join(errors),
        )

    # Update password and clear flag
    user.password_hash = get_password_hash(data.new_password)
    user.must_change_password = False

    # Log
    from app.models import PasswordChangeLog
    password_log = PasswordChangeLog(
        user_id=user.id,
        change_type="user_password",
        changed_by=user.id,
        ip_address=request.client.host if request.client else None,
    )
    db.add(password_log)

    await db.commit()
    await db.refresh(user)

    # Issue token — complete the login
    expires_delta = timedelta(hours=settings.JWT_ACCESS_TOKEN_EXPIRE_HOURS)
    access_token = create_access_token(subject=user.id, expires_delta=expires_delta)
    expires_at = datetime.utcnow() + expires_delta

    user_permissions = await get_user_permissions(user, db)

    return LoginResponse(
        data=TokenResponse(
            access_token=access_token,
            expires_at=expires_at,
            user=UserSimple(
                id=user.id,
                username=user.username,
                full_name=user.full_name,
                email=user.email,
                avatar_url=user.avatar_url,
                is_superuser=user.is_superuser,
                permissions=user_permissions,
            ),
        )
    )


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

def _issue_login_response(
    user: User,
    expires_delta: timedelta,
    db: AsyncSession,
) -> LoginResponse:
    """Build LoginResponse after successful MFA verification."""
    access_token = create_access_token(subject=user.id, expires_delta=expires_delta)
    expires_at = datetime.utcnow() + expires_delta
    return LoginResponse(
        data=TokenResponse(
            access_token=access_token,
            expires_at=expires_at,
            user=UserSimple(
                id=user.id,
                username=user.username,
                full_name=user.full_name,
                email=user.email,
                avatar_url=user.avatar_url,
                is_superuser=user.is_superuser,
                permissions=[],  # filled by caller
            ),
        )
    )


@router.post("/mfa/setup-qr")
async def mfa_setup_qr(
    user_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Generate temporary TOTP secret for MFA binding (no auth required — called during login flow)."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    if not user.mfa_enabled or user.mfa_secret:
        raise HTTPException(status_code=400, detail="MFA 未启用或已绑定")

    # Generate temporary secret
    secret = generate_totp_secret()

    # Store in Redis with TTL
    redis_client = get_redis()
    await redis_client.setex(f"{MFA_SETUP_KEY_PREFIX}{user_id}", MFA_SETUP_TTL, secret)

    # Generate QR code with configured issuer name
    # Read otp_issuer_name from DB settings, fall back to config default
    issuer_result = await db.execute(select(Setting).where(Setting.key == "otp_issuer_name"))
    issuer_setting = issuer_result.scalar_one_or_none()
    issuer = issuer_setting.value.get("value") if issuer_setting else settings.OTP_ISSUER_NAME
    qr_code = generate_totp_qr(secret, user.username, issuer)

    return ResponseBase(data=MFASetupQRData(qr_code=qr_code, mfa_secret=secret).model_dump())


@router.post("/mfa/login-verify", response_model=LoginResponse)
async def login_mfa_verify(
    request: Request,
    data: MFAVerifyRequest,
    db: AsyncSession = Depends(get_db),
):
    """Second phase of login: verify TOTP code and issue token.

    If setup=True, the secret was stored temporarily in Redis during the binding flow.
    If setup=False, the secret is already persisted in the database.
    """
    result = await db.execute(select(User).where(User.id == data.user_id))
    user = result.scalar_one_or_none()

    if not user or not user.mfa_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户未启用 MFA",
        )

    # Get the secret (from DB or Redis)
    secret: Optional[str] = None
    if data.setup:
        redis_client = get_redis()
        secret = await redis_client.get(f"{MFA_SETUP_KEY_PREFIX}{user.id}")
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

    # If setup mode, persist the secret
    if data.setup:
        user.mfa_secret = secret

    # Complete login
    user.last_login_at = datetime.utcnow()
    user.last_login_ip = request.client.host if request.client else None

    login_log = LoginLog(
        user_id=user.id,
        username=user.username,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        status="success",
    )
    db.add(login_log)

    await db.commit()
    await db.refresh(user)

    # Mark user as online in Redis
    redis_client = get_redis()
    await redis_client.setex(
        f"{ONLINE_KEY_PREFIX}{user.id}",
        ONLINE_TTL_SECONDS,
        "1",
    )

    # Create access token
    expires_delta = timedelta(hours=settings.JWT_ACCESS_TOKEN_EXPIRE_HOURS)
    access_token = create_access_token(
        subject=user.id,
        expires_delta=expires_delta,
    )
    expires_at = datetime.utcnow() + expires_delta

    # Get user permissions
    user_permissions = await get_user_permissions(user, db)

    return LoginResponse(
        data=TokenResponse(
            access_token=access_token,
            expires_at=expires_at,
            user=UserSimple(
                id=user.id,
                username=user.username,
                full_name=user.full_name,
                email=user.email,
                avatar_url=user.avatar_url,
                is_superuser=user.is_superuser,
                permissions=user_permissions,
            ),
        )
    )


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