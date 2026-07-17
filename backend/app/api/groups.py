"""
User Group Management API
CRUD operations for user groups and group membership
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import get_db
from app.models import User, Group, UserGroup, Authorization, Asset
from app.utils.audit import log_operation
from app.utils.pagination import get_pagination_meta
from app.schemas import (
    GroupCreate, GroupUpdate, GroupResponse, GroupDetailResponse,
    GroupListResponse, ResponseBase
)
from app.api.deps import PermissionChecker
from app.api.users import _resolve_user_names

group_router = APIRouter(prefix="/groups", tags=["用户组管理"])


@group_router.get("", response_model=GroupListResponse)
async def list_groups(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("view_users")),
):
    """List all user groups"""
    query = select(Group)

    if search:
        query = query.where(Group.name.ilike(f"%{search}%"))

    meta = await get_pagination_meta(db, query, page, limit)

    # Apply pagination
    query = query.offset((page - 1) * limit).limit(limit)
    query = query.order_by(Group.created_at.desc())

    result = await db.execute(query)
    groups = result.scalars().all()

    # Batch fetch member counts
    group_ids = [g.id for g in groups]
    member_counts: dict[int, int] = {}
    if group_ids:
        counts_result = await db.execute(
            select(UserGroup.group_id, func.count()).where(UserGroup.group_id.in_(group_ids)).group_by(UserGroup.group_id)
        )
        member_counts = dict(counts_result.all())

    group_responses = [
        {
            "id": group.id,
            "name": group.name,
            "description": group.description,
            "is_default": group.is_default,
            "created_at": group.created_at,
            "member_count": member_counts.get(group.id, 0),
        }
        for group in groups
    ]

    return GroupListResponse(
        data=group_responses,
        meta=meta,
    )


@group_router.post("", response_model=GroupDetailResponse, status_code=status.HTTP_201_CREATED)
async def create_group(
    data: GroupCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("user_mgmt")),
):
    """Create a new user group"""
    ip = request.client.host if request.client else None
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

    initial_member_ids = list(data.initial_member_ids or [])

    # Add initial members
    if initial_member_ids:
        for user_id in initial_member_ids:
            user_group = UserGroup(user_id=user_id, group_id=group.id)
            db.add(user_group)

    await db.commit()
    await db.refresh(group)

    await log_operation(
        db, current_user.id, "create", "group", group.id,
        details={
            "name": group.name,
            "initial_member_ids": initial_member_ids,
            "initial_member_count": len(initial_member_ids),
        },
        ip_address=ip,
    )

    return GroupDetailResponse(
        data=GroupResponse(
            id=group.id,
            name=group.name,
            description=group.description,
            created_at=group.created_at,
            member_count=len(data.initial_member_ids or []),
        )
    )


@group_router.delete("/{group_id}", response_model=ResponseBase)
async def delete_group(
    group_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("user_mgmt")),
):
    """Delete a user group"""
    ip = request.client.host if request.client else None
    result = await db.execute(
        select(Group).where(Group.id == group_id)
    )
    group = result.scalar_one_or_none()

    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户组不存在"
        )

    if group.is_default:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="默认用户组无法被删除"
        )

    # Check if group has members — require empty before deletion
    member_count_result = await db.execute(
        select(func.count()).select_from(UserGroup).where(UserGroup.group_id == group_id)
    )
    member_count = member_count_result.scalar_one()
    if member_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"用户组下还有 {member_count} 名成员，请先移除所有成员后再删除"
        )

    auth_count_result = await db.execute(
        select(func.count()).select_from(Authorization).where(
            Authorization.entity_type == "group",
            Authorization.entity_id == group_id,
        )
    )
    auth_count = auth_count_result.scalar_one()
    if auth_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"用户组还有 {auth_count} 条授权，请先删除授权后再删除用户组"
        )

    group_name = group.name
    await db.delete(group)
    await db.commit()

    await log_operation(
        db, current_user.id, "delete", "group", group_id,
        details={"name": group_name},
        ip_address=ip,
    )

    return ResponseBase(message="用户组已删除")


@group_router.get("/{group_id}/authorizations")
async def get_group_authorizations(
    group_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("view_users")),
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
    asset_ids = set()
    for auth in auths:
        if auth.target_type == "asset":
            asset_ids.update(auth.target_ids)

    # Batch fetch assets
    assets_map = {}
    if asset_ids:
        assets_result = await db.execute(select(Asset).where(Asset.id.in_(asset_ids)))
        for asset in assets_result.scalars().all():
            assets_map[asset.id] = asset

    # Build response — one entry per (auth, asset) pair
    auth_list = []
    for auth in auths:
        for target_id in auth.target_ids:
            asset = assets_map.get(target_id)
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


@group_router.put("/{group_id}", response_model=GroupDetailResponse)
async def update_group(
    group_id: int,
    request: Request,
    data: GroupUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("user_mgmt")),
):
    """Update a user group"""
    ip = request.client.host if request.client else None
    result = await db.execute(select(Group).where(Group.id == group_id))
    group = result.scalar_one_or_none()

    if not group:
        raise HTTPException(status_code=404, detail="用户组不存在")

    changes = {}
    if data.name is not None and data.name != group.name:
        # Check name uniqueness
        existing = await db.execute(
            select(Group).where(Group.name == data.name, Group.id != group_id)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="用户组名称已存在")
        changes["name"] = [group.name, data.name]
        group.name = data.name

    if data.description is not None and data.description != group.description:
        changes["description"] = [group.description, data.description]
        group.description = data.description

    await db.commit()
    await db.refresh(group)

    if changes:
        await log_operation(
            db, current_user.id, "update", "group", group_id,
            details={"changes": changes, "name": group.name},
            ip_address=ip,
        )

    # Get member count
    member_count_result = await db.execute(
        select(func.count()).select_from(UserGroup).where(UserGroup.group_id == group.id)
    )
    member_count = member_count_result.scalar() or 0

    return GroupDetailResponse(
        data=GroupResponse(
            id=group.id,
            name=group.name,
            description=group.description,
            created_at=group.created_at,
            member_count=member_count,
        )
    )


@group_router.get("/{group_id}/members")
async def get_group_members(
    group_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("view_users")),
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
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("user_mgmt")),
):
    """Add members to a group"""
    ip = request.client.host if request.client else None
    result = await db.execute(select(Group).where(Group.id == group_id))
    group = result.scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="用户组不存在")

    added_user_ids = []
    skipped_user_ids = []
    for user_id in user_ids:
        # Check user exists
        user_result = await db.execute(select(User).where(User.id == user_id))
        if not user_result.scalar_one_or_none():
            skipped_user_ids.append(user_id)
            continue

        # Check if already member
        existing = await db.execute(
            select(UserGroup).where(
                UserGroup.group_id == group_id,
                UserGroup.user_id == user_id
            )
        )
        if existing.scalar_one_or_none():
            skipped_user_ids.append(user_id)
            continue

        user_group = UserGroup(user_id=user_id, group_id=group_id)
        db.add(user_group)
        added_user_ids.append(user_id)

    await db.commit()

    added = len(added_user_ids)
    if added > 0:
        name_map = await _resolve_user_names(db, list(user_ids))
        await log_operation(
            db, current_user.id, "add_group_members", "group", group_id,
            details={
                "name": group.name,
                "requested_user_ids": list(user_ids),
                "requested_user_names": [name_map.get(user_id, str(user_id)) for user_id in user_ids],
                "added_user_ids": added_user_ids,
                "added_user_names": [name_map.get(user_id, str(user_id)) for user_id in added_user_ids],
                "skipped_user_ids": skipped_user_ids,
                "skipped_user_names": [name_map.get(user_id, str(user_id)) for user_id in skipped_user_ids],
                "added": added,
            },
            ip_address=ip,
        )

    return {"code": 0, "message": f"已添加 {added} 名成员"}


@group_router.delete("/{group_id}/members/{user_id}")
async def remove_group_member(
    group_id: int,
    user_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("user_mgmt")),
):
    """Remove a member from a group"""
    ip = request.client.host if request.client else None
    result = await db.execute(
        select(UserGroup).where(
            UserGroup.group_id == group_id,
            UserGroup.user_id == user_id
        )
    )
    user_group = result.scalar_one_or_none()

    if not user_group:
        raise HTTPException(status_code=404, detail="成员不存在")

    # Get user and group names for logging
    user_result = await db.execute(select(User).where(User.id == user_id))
    user_obj = user_result.scalar_one_or_none()
    user_name = user_obj.username if user_obj else str(user_id)
    group_result = await db.execute(select(Group).where(Group.id == group_id))
    group_obj = group_result.scalar_one_or_none()
    group_name = group_obj.name if group_obj else str(group_id)

    await db.delete(user_group)
    await db.commit()

    await log_operation(
        db, current_user.id, "remove_group_member", "group", group_id,
        details={
            "user_id": user_id,
            "username": user_name,
            "group_id": group_id,
            "group_name": group_name,
        },
        ip_address=ip,
    )

    return ResponseBase(message="成员已移除")
