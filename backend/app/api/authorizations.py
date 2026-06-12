"""
Authorization API
Asset authorization management
"""
from datetime import datetime, timezone
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import User, Group, Asset, Organization, Authorization
from app.api.deps import get_current_user, get_current_superuser
from app.schemas import (
    AuthorizationCreate, AuthorizationUpdate, AuthorizationResponse,
    PaginationMeta, ResponseBase
)


def format_datetime_utc(dt: datetime | None) -> str | None:
    """Format datetime as ISO 8601 with Z suffix for UTC"""
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc).isoformat().replace('+00:00', 'Z')


router = APIRouter(prefix="/authorizations", tags=["授权管理"])


@router.get("")
async def list_authorizations(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    entity_type: Optional[str] = Query(None),
    target_type: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List authorizations with pagination and filters"""
    query = select(Authorization)

    # Apply filters
    if entity_type:
        query = query.where(Authorization.entity_type == entity_type)

    if target_type:
        query = query.where(Authorization.target_type == target_type)

    if is_active is not None:
        query = query.where(Authorization.is_active == is_active)

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # Apply pagination
    query = query.offset((page - 1) * limit).limit(limit)
    query = query.order_by(Authorization.created_at.desc())

    result = await db.execute(query)
    auths = result.scalars().all()

    # Batch fetch entity names - collect all IDs first
    user_ids = [auth.entity_id for auth in auths if auth.entity_type == "user"]
    group_ids = [auth.entity_id for auth in auths if auth.entity_type == "group"]
    asset_ids = list(set(tid for auth in auths if auth.target_type == "asset" for tid in auth.target_ids))
    org_ids = list(set(tid for auth in auths if auth.target_type == "organization" for tid in auth.target_ids))

    # Batch fetch entities
    entity_names = {}
    if user_ids:
        users_result = await db.execute(select(User).where(User.id.in_(user_ids)))
        users = users_result.scalars().all()
        entity_names.update({f"user_{u.id}": u.username for u in users})
    if group_ids:
        groups_result = await db.execute(select(Group).where(Group.id.in_(group_ids)))
        groups = groups_result.scalars().all()
        entity_names.update({f"group_{g.id}": g.name for g in groups})

    # Batch fetch targets
    target_names = {}
    if asset_ids:
        assets_result = await db.execute(select(Asset).where(Asset.id.in_(asset_ids)))
        assets = assets_result.scalars().all()
        target_names.update({a.id: a.name for a in assets})
    if org_ids:
        org_ids_int = [int(oid) for oid in org_ids if oid.isdigit()]
        orgs_result = await db.execute(select(Organization).where(Organization.id.in_(org_ids_int)))
        orgs = orgs_result.scalars().all()
        target_names.update({str(o.id): o.name for o in orgs})

    def format_target_names(auth: Authorization) -> str:
        if auth.target_type == "asset":
            names = [target_names.get(tid, f"Asset {tid}") for tid in auth.target_ids]
        else:
            names = [target_names.get(tid, f"Org {tid}") for tid in auth.target_ids]
        if len(names) <= 3:
            return ", ".join(names)
        return ", ".join(names[:3]) + f" 等{len(names)}个"

    return {
        "code": 0,
        "message": "success",
        "data": [
            {
                "id": auth.id,
                "entity_type": auth.entity_type,
                "entity_id": auth.entity_id,
                "entity_name": entity_names.get(f"{auth.entity_type}_{auth.entity_id}", f"{auth.entity_type.capitalize()} {auth.entity_id}"),
                "target_type": auth.target_type,
                "target_ids": auth.target_ids,
                "target_name": format_target_names(auth),
                "permissions": auth.permissions,
                "valid_from": format_datetime_utc(auth.valid_from),
                "valid_until": format_datetime_utc(auth.valid_until),
                "is_active": auth.is_active,
                "created_by": auth.created_by,
                "created_at": format_datetime_utc(auth.created_at),
            }
            for auth in auths
        ],
        "meta": PaginationMeta(
            total=total,
            page=page,
            limit=limit,
            pages=(total + limit - 1) // limit,
        )
    }


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_authorization(
    data: AuthorizationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
):
    """Create a new authorization (admin only)"""
    # Validate entity exists
    if data.entity_type == "user":
        entity_result = await db.execute(select(User).where(User.id == data.entity_id))
        if not entity_result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="用户不存在")
    else:
        entity_result = await db.execute(select(Group).where(Group.id == data.entity_id))
        if not entity_result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="用户组不存在")

    # Validate targets exist
    if data.target_type == "asset":
        for target_id in data.target_ids:
            target_result = await db.execute(select(Asset).where(Asset.id == target_id))
            if not target_result.scalar_one_or_none():
                raise HTTPException(status_code=400, detail=f"资产 {target_id} 不存在")
    else:
        for target_id in data.target_ids:
            target_result = await db.execute(select(Organization).where(Organization.id == int(target_id)))
            if not target_result.scalar_one_or_none():
                raise HTTPException(status_code=400, detail=f"组织 {target_id} 不存在")

    # Check for existing authorization with same entity + target_type + identical target_ids set
    existing_result = await db.execute(
        select(Authorization).where(
            Authorization.entity_type == data.entity_type,
            Authorization.entity_id == data.entity_id,
            Authorization.target_type == data.target_type,
            Authorization.target_ids == data.target_ids,
        )
    )
    if existing_result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="授权已存在")

    auth = Authorization(
        entity_type=data.entity_type,
        entity_id=data.entity_id,
        target_type=data.target_type,
        target_ids=data.target_ids,
        permissions=data.permissions,
        valid_from=data.valid_from,
        valid_until=data.valid_until,
        created_by=current_user.id,
    )

    db.add(auth)
    await db.commit()
    await db.refresh(auth)

    return {
        "code": 0,
        "message": "授权创建成功",
        "data": {
            "id": auth.id,
            "entity_type": auth.entity_type,
            "entity_id": auth.entity_id,
            "target_type": auth.target_type,
            "target_ids": auth.target_ids,
            "permissions": auth.permissions,
        }
    }


@router.put("/{auth_id}")
async def update_authorization(
    auth_id: int,
    data: AuthorizationUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
):
    """Update an authorization (admin only)"""
    result = await db.execute(select(Authorization).where(Authorization.id == auth_id))
    auth = result.scalar_one_or_none()

    if not auth:
        raise HTTPException(status_code=404, detail="授权不存在")

    if data.permissions is not None:
        auth.permissions = data.permissions

    if data.valid_from is not None:
        auth.valid_from = data.valid_from

    if data.valid_until is not None:
        auth.valid_until = data.valid_until

    if data.is_active is not None:
        auth.is_active = data.is_active

    await db.commit()
    await db.refresh(auth)

    return {
        "code": 0,
        "message": "授权更新成功",
        "data": {
            "id": auth.id,
            "permissions": auth.permissions,
            "is_active": auth.is_active,
        }
    }


@router.delete("/{auth_id}", response_model=ResponseBase)
async def delete_authorization(
    auth_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
):
    """Delete an authorization (admin only)"""
    result = await db.execute(select(Authorization).where(Authorization.id == auth_id))
    auth = result.scalar_one_or_none()

    if not auth:
        raise HTTPException(status_code=404, detail="授权不存在")

    await db.delete(auth)
    await db.commit()

    return ResponseBase(message="授权已删除")


@router.get("/users")
async def list_users_for_auth(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List users for authorization selection"""
    result = await db.execute(
        select(User).where(User.is_active.is_(True)).order_by(User.username)
    )
    users = result.scalars().all()

    return {
        "code": 0,
        "data": [{"id": u.id, "name": u.username, "full_name": u.full_name} for u in users]
    }


@router.get("/groups")
async def list_groups_for_auth(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List groups for authorization selection"""
    result = await db.execute(select(Group).order_by(Group.name))
    groups = result.scalars().all()

    return {
        "code": 0,
        "data": [{"id": g.id, "name": g.name} for g in groups]
    }


@router.get("/assets")
async def list_assets_for_auth(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List assets for authorization selection"""
    result = await db.execute(
        select(Asset).order_by(Asset.name)
    )
    assets = result.scalars().all()

    return {
        "code": 0,
        "data": [{"id": a.id, "name": a.name, "category": a.category, "internal_address": a.internal_address, "external_address": a.external_address, "organization_id": a.organization_id} for a in assets]
    }


@router.get("/organizations")
async def list_organizations_for_auth(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List organizations for authorization selection"""
    result = await db.execute(select(Organization).order_by(Organization.path))
    orgs = result.scalars().all()

    # Build id→name map from ID path (e.g. "7/12/13" → "Default/开发部/数据库")
    id_to_name = {o.id: o.name for o in orgs}

    def get_name_path(org: Organization) -> str:
        path_ids = org.path.split("/") if org.path else []
        names = []
        for pid in path_ids:
            try:
                names.append(id_to_name[int(pid)])
            except (KeyError, ValueError):
                break
        return "/".join(names) if names else org.name

    return {
        "code": 0,
        "data": [{"id": o.id, "name": o.name, "path": o.path, "name_path": get_name_path(o)} for o in orgs]
    }