"""
Authentication API
Login, logout, token management
"""
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import User, LoginLog
from app.schemas import (
    LoginRequest, LoginResponse, TokenResponse, UserSimple, CurrentUserResponse,
    PasswordChangeRequest, ResponseBase
)
from app.core.security import verify_password, create_access_token, get_password_hash, validate_password_strength
from app.api.deps import get_current_user, get_user_permissions
from app.config import settings


router = APIRouter(prefix="/auth", tags=["认证"])


@router.post("/login", response_model=LoginResponse)
async def login(
    request: Request,
    data: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    User login endpoint
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

    # Update last login
    user.last_login_at = datetime.utcnow()
    user.last_login_ip = request.client.host if request.client else None

    # Mark login success
    login_log.status = "success"
    db.add(login_log)

    await db.commit()
    await db.refresh(user)

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
                is_superuser=user.is_superuser,
                permissions=user_permissions,
            )
        )
    )


@router.post("/logout", response_model=ResponseBase)
async def logout():
    """
    User logout endpoint
    Client should remove the token locally
    """
    return ResponseBase(message="登出成功")


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
            is_superuser=current_user.is_superuser,
            permissions=permissions,
        )
    )