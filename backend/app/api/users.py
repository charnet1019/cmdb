"""
User Management API
CRUD operations for users and user groups
"""
from typing import Optional, List
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_

from app.database import get_db
from app.models import User, Group, UserGroup, Authorization, Asset
from app.schemas import (
    UserCreate, UserUpdate, UserResponse, UserSimple,
    UserListResponse, PaginationMeta,
    GroupCreate, GroupUpdate, GroupResponse, GroupSimple,
    GroupListResponse, PasswordResetRequest, ResponseBase
)
from app.api.deps import get_current_user, get_current_superuser
from app.core.security import get_password_hash, verify_password, validate_password_strength


router = APIRouter(prefix="/users", tags=["用户管理"])


# ============== User APIs ==============
@router.get("", response_model=UserListResponse)
async def list_users(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all users with pagination and search"""
    query = select(User)

    # Apply filters
    if search:
        query = query.where(
            or_(
                User.username.ilike(f"%{search}%"),
                User.email.ilike(f"%{search}%"),
                User.full_name.ilike(f"%{search}%"),
            )
        )

    if is_active is not None:
        query = query.where(User.is_active == is_active)

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # Apply pagination
    query = query.offset((page - 1) * limit).limit(limit)
    query = query.order_by(User.created_at.desc())

    result = await db.execute(query)
    users = result.scalars().all()

    # Get groups for each user
    user_responses = []
    for user in users:
        groups_result = await db.execute(
            select(Group).join(UserGroup).where(UserGroup.user_id == user.id)
        )
        groups = groups_result.scalars().all()
        user_dict = {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "full_name": user.full_name,
            "phone": user.phone,
            "is_active": user.is_active,
            "mfa_enabled": user.mfa_enabled,
            "last_login_at": user.last_login_at,
            "created_at": user.created_at,
            "groups": [{"id": g.id, "name": g.name} for g in groups],
        }
        user_responses.append(user_dict)

    return UserListResponse(
        data=user_responses,
        meta=PaginationMeta(
            total=total,
            page=page,
            limit=limit,
            pages=(total + limit - 1) // limit,
        )
    )


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    data: UserCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
):
    """Create a new user (admin only)"""
    # Check if username exists
    existing = await db.execute(
        select(User).where(User.username == data.username)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户名已存在"
        )

    # Check if email exists
    existing = await db.execute(
        select(User).where(User.email == data.email)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="邮箱已被使用"
        )

    # Validate password
    is_valid, errors = validate_password_strength(data.password)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="; ".join(errors)
        )

    # Create user
    user = User(
        username=data.username,
        email=data.email,
        full_name=data.full_name,
        phone=data.phone,
        password_hash=get_password_hash(data.password),
        is_active=data.is_active,
        mfa_enabled=data.mfa_enabled,
    )

    db.add(user)
    await db.flush()

    # Add user to groups
    if data.group_ids:
        for group_id in data.group_ids:
            user_group = UserGroup(user_id=user.id, group_id=group_id)
            db.add(user_group)

    await db.commit()
    await db.refresh(user)

    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        phone=user.phone,
        is_active=user.is_active,
        mfa_enabled=user.mfa_enabled,
        last_login_at=user.last_login_at,
        created_at=user.created_at,
        groups=[],
    )


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get user by ID"""
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )

    # Get user groups
    groups_result = await db.execute(
        select(Group).join(UserGroup).where(UserGroup.user_id == user.id)
    )
    groups = groups_result.scalars().all()

    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        phone=user.phone,
        is_active=user.is_active,
        mfa_enabled=user.mfa_enabled,
        last_login_at=user.last_login_at,
        created_at=user.created_at,
        groups=[{"id": g.id, "name": g.name} for g in groups],
    )


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    data: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update user information"""
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )

    # Update fields
    if data.email is not None:
        # Check email uniqueness
        existing = await db.execute(
            select(User).where(User.email == data.email, User.id != user_id)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="邮箱已被使用"
            )
        user.email = data.email

    if data.full_name is not None:
        user.full_name = data.full_name

    if data.phone is not None:
        user.phone = data.phone

    if data.is_active is not None:
        user.is_active = data.is_active

    if data.mfa_enabled is not None:
        user.mfa_enabled = data.mfa_enabled

    # Update groups
    if data.group_ids is not None:
        # Remove existing groups
        await db.execute(
            select(UserGroup).where(UserGroup.user_id == user_id)
        )
        # Delete would be done with delete statement
        for ug in (await db.execute(select(UserGroup).where(UserGroup.user_id == user_id))).scalars().all():
            await db.delete(ug)

        # Add new groups
        for group_id in data.group_ids:
            user_group = UserGroup(user_id=user.id, group_id=group_id)
            db.add(user_group)

    await db.commit()
    await db.refresh(user)

    # Get updated groups
    groups_result = await db.execute(
        select(Group).join(UserGroup).where(UserGroup.user_id == user.id)
    )
    groups = groups_result.scalars().all()

    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        phone=user.phone,
        is_active=user.is_active,
        mfa_enabled=user.mfa_enabled,
        last_login_at=user.last_login_at,
        created_at=user.created_at,
        groups=[{"id": g.id, "name": g.name} for g in groups],
    )


@router.delete("/{user_id}", response_model=ResponseBase)
async def delete_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
):
    """Delete user (admin only)"""
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )

    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能删除自己"
        )

    await db.delete(user)
    await db.commit()

    return ResponseBase(message="用户已删除")


@router.post("/{user_id}/reset-password", response_model=ResponseBase)
async def reset_user_password(
    user_id: int,
    data: PasswordResetRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
):
    """Reset user password (admin only)"""
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )

    if data.method == "manual" and data.new_password:
        # Validate password
        is_valid, errors = validate_password_strength(data.new_password)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="; ".join(errors)
            )
        user.password_hash = get_password_hash(data.new_password)
        temp_password = None
    else:
        # Auto-generate password
        import secrets
        import string
        chars = string.ascii_letters + string.digits + "!@#$%^&*"
        temp_password = ''.join(secrets.choice(chars) for _ in range(16))
        user.password_hash = get_password_hash(temp_password)
        # Note: In production, send email to user with temp password
        # For now, return it in response for admin to communicate

    await db.commit()

    response_data = {"message": "密码重置成功"}
    if temp_password and data.method == "auto":
        response_data["temp_password"] = temp_password

    return {"code": 0, "message": "密码重置成功", "data": response_data}


@router.get("/{user_id}/authorizations")
async def get_user_authorizations(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get user's asset authorizations (direct and inherited through groups)"""
    # Check user exists
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    # Get user's groups
    groups_result = await db.execute(
        select(Group).join(UserGroup).where(UserGroup.user_id == user_id)
    )
    user_groups = groups_result.scalars().all()
    group_ids = [g.id for g in user_groups]

    # Get direct authorizations (entity_type='user')
    direct_auths_result = await db.execute(
        select(Authorization).where(
            Authorization.entity_type == "user",
            Authorization.entity_id == user_id,
            Authorization.is_active == True,
        )
    )
    direct_auths = direct_auths_result.scalars().all()

    # Get inherited authorizations (entity_type='group')
    inherited_auths = []
    if group_ids:
        inherited_auths_result = await db.execute(
            select(Authorization).where(
                Authorization.entity_type == "group",
                Authorization.entity_id.in_(group_ids),
                Authorization.is_active == True,
            )
        )
        inherited_auths = inherited_auths_result.scalars().all()

    # Collect all asset IDs
    asset_ids = set()
    for auth in direct_auths + inherited_auths:
        if auth.target_type == "asset":
            asset_ids.add(auth.target_id)

    # Batch fetch assets
    assets_map = {}
    if asset_ids:
        assets_result = await db.execute(select(Asset).where(Asset.id.in_(asset_ids)))
        for asset in assets_result.scalars().all():
            assets_map[asset.id] = asset

    # Build response
    direct_list = []
    for auth in direct_auths:
        asset = assets_map.get(auth.target_id)
        if asset:
            direct_list.append({
                "id": auth.id,
                "asset_id": asset.id,
                "asset_name": asset.name,
                "asset_category": asset.category,
                "permissions": auth.permissions,
                "valid_until": auth.valid_until.isoformat() if auth.valid_until else None,
                "status": "active" if auth.is_active else "inactive",
                "source_type": "direct",
            })

    inherited_list = []
    for auth in inherited_auths:
        asset = assets_map.get(auth.target_id)
        if asset:
            # Find group name
            group_name = next((g.name for g in user_groups if g.id == auth.entity_id), "Unknown")
            inherited_list.append({
                "id": auth.id,
                "asset_id": asset.id,
                "asset_name": asset.name,
                "asset_category": asset.category,
                "permissions": auth.permissions,
                "valid_until": auth.valid_until.isoformat() if auth.valid_until else None,
                "status": "active" if auth.is_active else "inactive",
                "source_type": "group",
                "group_id": auth.entity_id,
                "group_name": group_name,
            })

    return {
        "code": 0,
        "data": {
            "direct": direct_list,
            "inherited": inherited_list,
            "total": len(direct_list) + len(inherited_list),
        }
    }


# ============== Group APIs ==============
group_router = APIRouter(prefix="/groups", tags=["用户组管理"])


@group_router.get("", response_model=GroupListResponse)
async def list_groups(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all user groups"""
    query = select(Group)

    if search:
        query = query.where(Group.name.ilike(f"%{search}%"))

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # Apply pagination
    query = query.offset((page - 1) * limit).limit(limit)
    query = query.order_by(Group.created_at.desc())

    result = await db.execute(query)
    groups = result.scalars().all()

    # Get member count for each group
    group_responses = []
    for group in groups:
        member_count_result = await db.execute(
            select(func.count()).select_from(UserGroup).where(UserGroup.group_id == group.id)
        )
        member_count = member_count_result.scalar() or 0

        group_responses.append({
            "id": group.id,
            "name": group.name,
            "description": group.description,
            "created_at": group.created_at,
            "member_count": member_count,
        })

    return GroupListResponse(
        data=group_responses,
        meta=PaginationMeta(
            total=total,
            page=page,
            limit=limit,
            pages=(total + limit - 1) // limit,
        )
    )


@group_router.post("", response_model=GroupResponse, status_code=status.HTTP_201_CREATED)
async def create_group(
    data: GroupCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
):
    """Create a new user group"""
    # Check if name exists
    existing = await db.execute(
        select(Group).where(Group.name == data.name)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户组名称已存在"
        )

    group = Group(
        name=data.name,
        description=data.description,
    )

    db.add(group)
    await db.flush()

    # Add initial members
    if data.initial_member_ids:
        for user_id in data.initial_member_ids:
            user_group = UserGroup(user_id=user_id, group_id=group.id)
            db.add(user_group)

    await db.commit()
    await db.refresh(group)

    return GroupResponse(
        id=group.id,
        name=group.name,
        description=group.description,
        created_at=group.created_at,
        member_count=len(data.initial_member_ids or []),
    )


@group_router.delete("/{group_id}", response_model=ResponseBase)
async def delete_group(
    group_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
):
    """Delete a user group"""
    result = await db.execute(
        select(Group).where(Group.id == group_id)
    )
    group = result.scalar_one_or_none()

    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户组不存在"
        )

    await db.delete(group)
    await db.commit()

    return ResponseBase(message="用户组已删除")


@group_router.get("/{group_id}/authorizations")
async def get_group_authorizations(
    group_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get group's asset authorizations"""
    # Check group exists
    result = await db.execute(select(Group).where(Group.id == group_id))
    group = result.scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="用户组不存在")

    # Get group authorizations
    auths_result = await db.execute(
        select(Authorization).where(
            Authorization.entity_type == "group",
            Authorization.entity_id == group_id,
            Authorization.is_active == True,
        )
    )
    auths = auths_result.scalars().all()

    # Collect asset IDs
    asset_ids = [auth.target_id for auth in auths if auth.target_type == "asset"]

    # Batch fetch assets
    assets_map = {}
    if asset_ids:
        assets_result = await db.execute(select(Asset).where(Asset.id.in_(asset_ids)))
        for asset in assets_result.scalars().all():
            assets_map[asset.id] = asset

    # Build response
    auth_list = []
    for auth in auths:
        asset = assets_map.get(auth.target_id)
        if asset:
            auth_list.append({
                "id": auth.id,
                "asset_id": asset.id,
                "asset_name": asset.name,
                "asset_category": asset.category,
                "permissions": auth.permissions,
                "valid_until": auth.valid_until.isoformat() if auth.valid_until else None,
                "status": "active" if auth.is_active else "inactive",
            })

    return {
        "code": 0,
        "data": auth_list,
        "total": len(auth_list),
    }


@group_router.put("/{group_id}", response_model=GroupResponse)
async def update_group(
    group_id: int,
    name: Optional[str] = Query(None),
    description: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
):
    """Update a user group"""
    result = await db.execute(select(Group).where(Group.id == group_id))
    group = result.scalar_one_or_none()

    if not group:
        raise HTTPException(status_code=404, detail="用户组不存在")

    if name:
        # Check name uniqueness
        existing = await db.execute(
            select(Group).where(Group.name == name, Group.id != group_id)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="用户组名称已存在")
        group.name = name

    if description is not None:
        group.description = description

    await db.commit()
    await db.refresh(group)

    # Get member count
    member_count_result = await db.execute(
        select(func.count()).select_from(UserGroup).where(UserGroup.group_id == group.id)
    )
    member_count = member_count_result.scalar() or 0

    return GroupResponse(
        id=group.id,
        name=group.name,
        description=group.description,
        created_at=group.created_at,
        member_count=member_count,
    )


@group_router.get("/{group_id}/members")
async def get_group_members(
    group_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get members of a group"""
    result = await db.execute(select(Group).where(Group.id == group_id))
    group = result.scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="用户组不存在")

    # Get members
    members_result = await db.execute(
        select(User).join(UserGroup).where(UserGroup.group_id == group_id)
    )
    members = members_result.scalars().all()

    return {
        "code": 0,
        "data": [
            {
                "id": u.id,
                "username": u.username,
                "full_name": u.full_name,
                "email": u.email,
                "is_active": u.is_active,
            }
            for u in members
        ]
    }


@group_router.post("/{group_id}/members")
async def add_group_members(
    group_id: int,
    user_ids: List[int],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
):
    """Add members to a group"""
    result = await db.execute(select(Group).where(Group.id == group_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="用户组不存在")

    added = 0
    for user_id in user_ids:
        # Check user exists
        user_result = await db.execute(select(User).where(User.id == user_id))
        if not user_result.scalar_one_or_none():
            continue

        # Check if already member
        existing = await db.execute(
            select(UserGroup).where(
                UserGroup.group_id == group_id,
                UserGroup.user_id == user_id
            )
        )
        if existing.scalar_one_or_none():
            continue

        user_group = UserGroup(user_id=user_id, group_id=group_id)
        db.add(user_group)
        added += 1

    await db.commit()

    return {"code": 0, "message": f"已添加 {added} 名成员"}


@group_router.delete("/{group_id}/members/{user_id}")
async def remove_group_member(
    group_id: int,
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
):
    """Remove a member from a group"""
    result = await db.execute(
        select(UserGroup).where(
            UserGroup.group_id == group_id,
            UserGroup.user_id == user_id
        )
    )
    user_group = result.scalar_one_or_none()

    if not user_group:
        raise HTTPException(status_code=404, detail="成员不存在")

    await db.delete(user_group)
    await db.commit()

    return ResponseBase(message="成员已移除")