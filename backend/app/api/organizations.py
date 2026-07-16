"""
Organization Tree API
CRUD operations for the organization/asset-tree hierarchy.
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import get_db
from app.models import Asset, Organization, User
from app.api.deps import PermissionChecker, check_resource_permission, get_authorized_asset_ids
from app.utils.audit import log_operation
from app.utils.authorization_cleanup import cleanup_authorization_targets
from app.api.assets import _client_ip


org_router = APIRouter(prefix="/organizations", tags=["组织架构"])


@org_router.get("")
async def list_organizations(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("view")),
):
    """List all organizations as tree structure"""
    result = await db.execute(
        select(Organization).order_by(Organization.path)
    )
    organizations = result.scalars().all()

    # Resource-level authorization filter
    authorized_ids = await get_authorized_asset_ids(current_user, db, "view")

    # Get asset count for each organization (filtered by authorization)
    count_query = select(Asset.organization_id, func.count().label('count')).where(
        Asset.organization_id.isnot(None)
    )
    if authorized_ids is not None:
        count_query = count_query.where(Asset.id.in_(authorized_ids))
    org_asset_counts_result = await db.execute(count_query.group_by(Asset.organization_id))
    org_asset_counts = {row.organization_id: row.count for row in org_asset_counts_result}

    # Get asset count for root (organization_id is null)
    root_query = select(func.count()).select_from(Asset).where(Asset.organization_id.is_(None))
    if authorized_ids is not None:
        root_query = root_query.where(Asset.id.in_(authorized_ids))
    root_asset_count = await db.scalar(root_query) or 0

    # Build tree structure and calculate total counts (including children)
    org_map = {}
    for org in organizations:
        org_map[org.id] = {
            "id": org.id,
            "name": org.name,
            "parent_id": org.parent_id,
            "path": org.path,
            "level": org.level,
            "count": org_asset_counts.get(org.id, 0),  # Direct asset count
            "total_count": org_asset_counts.get(org.id, 0),  # Will be updated to include children
            "children": [],
        }

    # Build tree and calculate total counts (assets in node + all descendants)
    # First, build the tree structure
    root_nodes = []
    for org_id, org_data in org_map.items():
        parent_id = org_data["parent_id"]
        if parent_id and parent_id in org_map:
            org_map[parent_id]["children"].append(org_data)
        else:
            root_nodes.append(org_data)

    # Calculate total counts bottom-up (children first, then parents)
    def calculate_total_count(org_data: dict) -> int:
        total = org_data["count"]
        for child in org_data["children"]:
            total += calculate_total_count(child)
        org_data["total_count"] = total
        return total

    for org_data in root_nodes:
        calculate_total_count(org_data)

    # Calculate grand total for root (all assets in the system)
    total_assets = root_asset_count + sum(org_data["total_count"] for org_data in root_nodes)

    return {
        "code": 0,
        "data": root_nodes,
        "root_asset_count": root_asset_count,  # Assets directly under root (no organization)
        "total_assets": total_assets  # Total assets in the system
    }


@org_router.post("")
async def create_organization(
    name: str,
    parent_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("manage")),
    request: Request = None,
):
    """Create a new organization node"""
    parent_path = ""
    parent_level = -1

    if parent_id:
        result = await db.execute(
            select(Organization).where(Organization.id == parent_id)
        )
        parent = result.scalar_one_or_none()
        if not parent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="父节点不存在"
            )

        # Check resource-level permission on parent
        await check_resource_permission(
            current_user, "manage", "organization", str(parent_id), db,
        )

        parent_path = parent.path or ""
        parent_level = parent.level

    org = Organization(
        name=name,
        parent_id=parent_id,
        level=parent_level + 1,
    )

    db.add(org)
    await db.flush()

    # Set path
    org.path = f"{parent_path}/{org.id}".strip("/")
    await db.commit()
    await db.refresh(org)

    await log_operation(
        db, current_user.id, "create", "organization", org.id,
        details={
            "name": org.name,
            "action": "create_organization",
            "parent_id": parent_id,
            "path": org.path,
        },
        ip_address=_client_ip(request),
    )

    return {"code": 0, "data": {"id": org.id, "name": org.name, "path": org.path}}


@org_router.put("/{org_id}")
async def update_organization(
    org_id: int,
    name: str = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("manage")),
    request: Request = None,
):
    """Update organization node (rename)"""
    result = await db.execute(
        select(Organization).where(Organization.id == org_id)
    )
    org = result.scalar_one_or_none()

    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="节点不存在"
        )

    # Check resource-level permission
    await check_resource_permission(
        current_user, "manage", "organization", str(org_id), db,
    )

    before_name = org.name
    if name:
        org.name = name

    await db.commit()
    await db.refresh(org)

    if name and before_name != org.name:
        await log_operation(
            db, current_user.id, "update", "organization", org.id,
            details={
                "name": org.name,
                "action": "rename_organization",
                "path": org.path,
                "changes": {"name": [before_name, org.name]},
            },
            ip_address=_client_ip(request),
        )

    return {"code": 0, "data": {"id": org.id, "name": org.name}}


@org_router.delete("/{org_id}")
async def delete_organization(
    org_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("manage")),
    request: Request = None,
):
    """Delete organization node"""
    result = await db.execute(
        select(Organization).where(Organization.id == org_id)
    )
    org = result.scalar_one_or_none()

    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="节点不存在"
        )

    # Check resource-level permission
    await check_resource_permission(
        current_user, "manage", "organization", str(org_id), db,
    )

    # Check if has children
    child_result = await db.execute(
        select(Organization).where(Organization.parent_id == org_id)
    )
    if child_result.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该节点下有子节点，无法删除"
        )

    # Check if has assets
    asset_result = await db.execute(
        select(Asset).where(Asset.organization_id == org_id).limit(1)
    )
    if asset_result.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该节点下有资产，无法删除"
        )

    org_name = org.name
    org_parent_id = org.parent_id
    org_path = org.path

    # Remove dangling references from authorizations that target this organization
    await cleanup_authorization_targets(db, "organization", [str(org_id)])

    await db.delete(org)
    await db.commit()

    await log_operation(
        db, current_user.id, "delete", "organization", org_id,
        details={
            "name": org_name,
            "action": "delete_organization",
            "parent_id": org_parent_id,
            "path": org_path,
        },
        ip_address=_client_ip(request),
    )

    return {"code": 0, "message": "节点已删除"}
