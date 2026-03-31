"""
API Dependencies
Dependency injection for FastAPI routes
"""
from typing import Optional, List
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.core.security import decode_access_token
from app.models import User, Authorization


# HTTP Bearer security scheme
security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Get current authenticated user from JWT token
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无法验证凭据",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token = credentials.credentials
    payload = decode_access_token(token)

    if payload is None:
        raise credentials_exception

    user_id: Optional[int] = payload.get("sub")
    if user_id is None:
        raise credentials_exception

    # Query user from database
    result = await db.execute(
        select(User).where(User.id == int(user_id))
    )
    user = result.scalar_one_or_none()

    if user is None:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="用户已被禁用"
        )

    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Verify user is active
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="用户已被禁用"
        )
    return current_user


async def get_current_superuser(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Verify user is superuser
    """
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )
    return current_user


async def get_user_permissions(
    user: User,
    db: AsyncSession,
) -> List[str]:
    """
    Get all permissions for a user (direct + group permissions)
    """
    if user.is_superuser:
        # Superuser has all permissions
        return [
            "view", "manage", "user_mgmt", "sys_config",
            "audit_log", "view_pwd", "manage_pwd"
        ]

    # Get direct user authorizations
    from app.models import Group
    from datetime import datetime

    now = datetime.utcnow()

    # Direct user permissions
    user_auths_result = await db.execute(
        select(Authorization)
        .where(Authorization.entity_type == "user")
        .where(Authorization.entity_id == user.id)
        .where(Authorization.is_active == True)
        .where(
            (Authorization.valid_from == None) | (Authorization.valid_from <= now)
        )
        .where(
            (Authorization.valid_until == None) | (Authorization.valid_until >= now)
        )
    )
    user_auths = user_auths_result.scalars().all()

    # Get user groups
    from app.models import UserGroup
    groups_result = await db.execute(
        select(Group.id)
        .join(UserGroup, Group.id == UserGroup.group_id)
        .where(UserGroup.user_id == user.id)
    )
    group_ids = [g[0] for g in groups_result.all()]

    # Group permissions
    permissions = set()
    for auth in user_auths:
        if auth.permissions:
            permissions.update(auth.permissions)

    if group_ids:
        group_auths_result = await db.execute(
            select(Authorization)
            .where(Authorization.entity_type == "group")
            .where(Authorization.entity_id.in_(group_ids))
            .where(Authorization.is_active == True)
            .where(
                (Authorization.valid_from == None) | (Authorization.valid_from <= now)
            )
            .where(
                (Authorization.valid_until == None) | (Authorization.valid_until >= now)
            )
        )
        group_auths = group_auths_result.scalars().all()
        for auth in group_auths:
            if auth.permissions:
                permissions.update(auth.permissions)

    return list(permissions)


class PermissionChecker:
    """
    Permission checker dependency
    Usage: @Depends(PermissionChecker("view"))
    """

    def __init__(self, permission: str):
        self.permission = permission

    async def __call__(
        self,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> User:
        # Superuser has all permissions
        if current_user.is_superuser:
            return current_user

        # Check user permissions from authorizations
        permissions = await get_user_permissions(current_user, db)

        if self.permission not in permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"缺少 '{self.permission}' 权限"
            )

        return current_user