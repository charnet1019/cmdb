"""
Authorization API
Asset authorization management
"""
from datetime import datetime, timezone
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, and_
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import User, Group, Asset, Organization, Authorization
from app.api.deps import PermissionChecker
from app.utils.audit import log_operation
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
    keyword: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("authorize")),
):
    """List authorizations with pagination, filters and keyword search"""
    query = select(Authorization)

    # Apply filters
    if entity_type:
        query = query.where(Authorization.entity_type == entity_type)

    if target_type:
        query = query.where(Authorization.target_type == target_type)

    if is_active is not None:
        query = query.where(Authorization.is_active == is_active)

    # Keyword search: match entity name (user/group) or target asset name
    if keyword:
        search_pattern = f"%{keyword}%"

        # Two-step asset search: first get matching asset IDs, then check JSONB containment
        asset_ids = []
        if target_type != "organization":  # Don't restrict asset search when filtering orgs
            asset_result = await db.execute(
                select(Asset.id).where(Asset.name.ilike(search_pattern))
            )
            asset_ids = [aid for (aid,) in asset_result.all()]

        conditions = []

        # Search user by username or full_name
        conditions.append(and_(
            Authorization.entity_type == "user",
            Authorization.entity_id.in_(
                select(User.id).where(
                    or_(
                        User.username.ilike(search_pattern),
                        User.full_name.ilike(search_pattern),
                    )
                )
            ),
        ))

        # Search group by name
        conditions.append(and_(
            Authorization.entity_type == "group",
            Authorization.entity_id.in_(
                select(Group.id).where(Group.name.ilike(search_pattern))
            ),
        ))

        # Search asset by name (check if any target_id matches)
        if asset_ids:
            conditions.append(and_(
                Authorization.target_type == "asset",
                or_(
                    *[Authorization.target_ids.contains([aid]) for aid in asset_ids]
                ),
            ))

        query = query.where(or_(*conditions))

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
        # Build id→name map for name_path computation
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
        target_names.update({str(o.id): get_name_path(o) for o in orgs})

    def format_target_names(auth: Authorization) -> str:
        if auth.target_type == "asset":
            names = [target_names.get(tid, f"Asset {tid}") for tid in auth.target_ids]
        else:
            names = [target_names.get(tid, "Default" if tid == "__all__" else f"Org {tid}") for tid in auth.target_ids]
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


async def _resolve_entity_name(db: AsyncSession, entity_type: str, entity_id: int) -> str:
    """Resolve entity name for audit logging"""
    if entity_type == "user":
        user = await db.execute(select(User).where(User.id == entity_id))
        user = user.scalar_one_or_none()
        return user.username if user else str(entity_id)
    else:
        group = await db.execute(select(Group).where(Group.id == entity_id))
        group = group.scalar_one_or_none()
        return group.name if group else str(entity_id)

async def _resolve_target_names(db: AsyncSession, target_type: str, target_ids: list[str]) -> str:
    """Resolve target names for audit logging"""
    if target_type == "asset":
        assets = await db.execute(select(Asset).where(Asset.id.in_(target_ids)))
        assets = assets.scalars().all()
        names = [a.name for a in assets]
        if len(names) <= 3:
            return ", ".join(names)
        return ", ".join(names[:3]) + f" 等{len(names)}个"
    else:
        org_ids = [int(tid) for tid in target_ids if tid != "__all__" and tid.isdigit()]
        names = []
        if "__all__" in target_ids:
            names.append("Default")
        if org_ids:
            orgs = await db.execute(select(Organization).where(Organization.id.in_(org_ids)))
            orgs = orgs.scalars().all()
            names.extend([o.name for o in orgs])
        return ", ".join(names) if names else str(target_ids)

@router.post("", status_code=status.HTTP_201_CREATED)
async def create_authorization(
    data: AuthorizationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("authorize")),
    request: Request = None,
):
    """Create a new authorization (authorize permission required)"""
    ip = request.client.host if request and request.client else None
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
            if target_id == "__all__":
                continue  # Root org sentinel — valid
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

    # Resolve names for audit log
    entity_name = await _resolve_entity_name(db, data.entity_type, data.entity_id)
    target_names = await _resolve_target_names(db, data.target_type, data.target_ids)

    await log_operation(
        db, current_user.id, "create", "authorization", auth.id,
        details={
            "name": f"{entity_name} -> {target_names}",
            "entity_type": auth.entity_type,
            "entity_id": auth.entity_id,
            "entity_name": entity_name,
            "target_type": auth.target_type,
            "target_ids": auth.target_ids,
            "target_names": target_names,
            "permissions": auth.permissions,
        },
        ip_address=ip,
    )

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
    current_user: User = Depends(PermissionChecker("authorize")),
    request: Request = None,
):
    """Update an authorization (authorize permission required)"""
    ip = request.client.host if request and request.client else None
    result = await db.execute(select(Authorization).where(Authorization.id == auth_id))
    auth = result.scalar_one_or_none()

    if not auth:
        raise HTTPException(status_code=404, detail="授权不存在")

    changes = {}

    def audit_datetime(value):
        return value.isoformat() if value else None

    def record_change(field: str, before, after) -> None:
        if before != after:
            changes[field] = [before, after]

    if data.permissions is not None:
        record_change("permissions", list(auth.permissions or []), data.permissions)
        auth.permissions = data.permissions

    if data.target_ids is not None and len(data.target_ids) > 0:
        record_change("target_ids", list(auth.target_ids or []), data.target_ids)
        auth.target_ids = data.target_ids

    if data.valid_from is not None:
        record_change("valid_from", audit_datetime(auth.valid_from), audit_datetime(data.valid_from))
        auth.valid_from = data.valid_from

    if data.valid_until is not None:
        record_change("valid_until", audit_datetime(auth.valid_until), audit_datetime(data.valid_until))
        auth.valid_until = data.valid_until

    if data.is_active is not None:
        record_change("is_active", auth.is_active, data.is_active)
        auth.is_active = data.is_active

    await db.commit()
    await db.refresh(auth)

    if changes:
        await log_operation(
            db, current_user.id, "update", "authorization", auth.id,
            details={
                "name": f"{await _resolve_entity_name(db, auth.entity_type, auth.entity_id)} -> {await _resolve_target_names(db, auth.target_type, auth.target_ids)}",
                "entity_type": auth.entity_type,
                "entity_id": auth.entity_id,
                "target_type": auth.target_type,
                "permissions": auth.permissions,
                "is_active": auth.is_active,
                "changes": changes,
            },
            ip_address=ip,
        )

    return {
        "code": 0,
        "message": "授权更新成功",
        "data": {
            "id": auth.id,
            "permissions": auth.permissions,
            "target_ids": auth.target_ids,
            "is_active": auth.is_active,
        }
    }


@router.delete("/{auth_id}", response_model=ResponseBase)
async def delete_authorization(
    auth_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("authorize")),
    request: Request = None,
):
    """Delete an authorization (authorize permission required)"""
    ip = request.client.host if request and request.client else None
    result = await db.execute(select(Authorization).where(Authorization.id == auth_id))
    auth = result.scalar_one_or_none()

    if not auth:
        raise HTTPException(status_code=404, detail="授权不存在")

    await db.delete(auth)
    await db.commit()

    await log_operation(
        db, current_user.id, "delete", "authorization", auth.id,
        details={
            "name": f"{await _resolve_entity_name(db, auth.entity_type, auth.entity_id)} -> {await _resolve_target_names(db, auth.target_type, auth.target_ids)}",
            "entity_type": auth.entity_type,
            "entity_id": auth.entity_id,
            "target_type": auth.target_type,
            "target_ids": auth.target_ids,
            "permissions": auth.permissions,
        },
        ip_address=ip,
    )

    return ResponseBase(message="授权已删除")


@router.get("/users")
async def list_users_for_auth(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("authorize")),
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
    current_user: User = Depends(PermissionChecker("authorize")),
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
    current_user: User = Depends(PermissionChecker("authorize")),
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
    current_user: User = Depends(PermissionChecker("authorize")),
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
        "data": [
            {"id": None, "name": "Default", "path": None, "name_path": "Default"},
        ] + [
            {"id": o.id, "name": o.name, "path": o.path, "name_path": "Default/" + get_name_path(o)} for o in orgs
        ]
    }