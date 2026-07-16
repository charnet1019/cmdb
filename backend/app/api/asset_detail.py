"""
Single-asset detail API: get/update/delete by ID.

Registered on the shared `router` from app.api.assets, but split into its
own module and imported LAST (see app/api/__init__.py) so its wildcard
`/{asset_id}` routes are added to the router after every fixed-path route
(/stats, /bulk, /export, /import/..., /{asset_id}/config, /{asset_id}/decrypt-oob).
Starlette matches routes in registration order, so a fixed path like
/assets/export must be registered before /assets/{asset_id} — otherwise
"export" gets captured as asset_id and the request 404s as a missing asset.
"""
from typing import Dict, Any
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import Asset, Organization, User, AssetHostRelation, StorageLocation
from app.schemas import AssetUpdate, ResponseBase
from app.api.deps import PermissionChecker, check_resource_permission
from app.api.assets import (
    router,
    build_asset_response,
    _validate_category_fields,
    _encrypt_oob_password,
    _sync_host_relations,
    _sync_storage_locations,
    _storage_location_items,
)
from app.utils.audit import log_operation
from app.utils.authorization_cleanup import cleanup_authorization_targets


@router.get("/{asset_id}")
async def get_asset(
    asset_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("view")),
) -> Dict[str, Any]:
    """Get asset by ID"""
    # Build query with eager loading of all relations needed by build_asset_response
    query = select(Asset).options(
        selectinload(Asset.credentials),
        selectinload(Asset.config_file),
        selectinload(Asset.database_hosts).selectinload(AssetHostRelation.host_asset),
        selectinload(Asset.storage_locations),
    )

    result = await db.execute(query.where(Asset.id == asset_id))
    asset = result.scalar_one_or_none()

    if not asset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="资产不存在"
        )

    # Check resource-level permission
    await check_resource_permission(
        current_user, "view", "asset", asset_id, db,
        organization_id=asset.organization_id,
    )

    # Get organization name if exists
    organization_name = None
    if asset.organization_id:
        org_result = await db.execute(select(Organization.name).where(Organization.id == asset.organization_id))
        org_row = org_result.scalar_one_or_none()
        if org_row:
            organization_name = org_row

    credentials = [
        {
            "id": c.id,
            "username": c.username,
            "credential_type": c.credential_type,
        }
        for c in asset.credentials
    ]

    return build_asset_response(
        asset,
        org_name=organization_name,
        include_credentials=True,
        credentials_data=credentials
    )


@router.put("/{asset_id}")
async def update_asset(
    asset_id: str,
    data: AssetUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("manage")),
    request: Request = None,
) -> Dict[str, Any]:
    """Update asset information"""
    ip = request.client.host if request and request.client else None
    result = await db.execute(
        select(Asset).where(Asset.id == asset_id)
    )
    asset = result.scalar_one_or_none()

    if not asset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="资产不存在"
        )

    # Check resource-level permission
    await check_resource_permission(
        current_user, "manage", "asset", asset_id, db,
        organization_id=asset.organization_id,
    )

    # Update fields
    update_data = data.model_dump(exclude_unset=True)
    _validate_category_fields(asset.category, update_data)
    changes = {}

    def record_change(field: str, before, after) -> None:
        if before != after:
            changes[field] = [before, after]

    # Handle owner validation. owner_id/owner_name are extracted and applied
    # together (one "负责人" audit entry) instead of going through the
    # generic per-field loop below — otherwise they'd each log their own
    # before/after diff under the same "负责人" label, producing two
    # confusing "将负责人从空修改为X" lines for a single owner change.
    if "owner_id" in update_data or "owner_name" in update_data:
        owner_id = update_data.pop("owner_id", None)
        owner_name = update_data.pop("owner_name", None)

        if owner_id is not None and owner_name is None:
            # Fetch owner name from database
            result = await db.execute(select(User.username).where(User.id == owner_id))
            owner_result = result.scalar_one_or_none()
            if owner_result:
                owner_name = owner_result
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="负责人 ID 不存在"
                )
        elif owner_name is not None and owner_id is None:
            # Try to find user by username
            result = await db.execute(select(User.id).where(User.username == owner_name))
            owner_result = result.scalar_one_or_none()
            if owner_result:
                owner_id = owner_result
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="负责人不存在"
                )

        record_change("owner", asset.owner_name, owner_name)
        asset.owner_id = owner_id
        asset.owner_name = owner_name

    # Handle OOB password encryption. Never write the password value into audit logs.
    if "oob_password" in update_data and update_data["oob_password"] is not None:
        before_password_state = "已设置" if asset.oob_password_encrypted else "未设置"
        after_password_state = "已设置" if update_data["oob_password"] else "未设置"
        record_change("oob_password", before_password_state, after_password_state)
        asset.oob_password_encrypted = _encrypt_oob_password(update_data["oob_password"])
        del update_data["oob_password"]

    # Extract database-specific fields before generic update
    host_ids = update_data.pop("host_ids", None)
    storage_locations_data = update_data.pop("storage_locations", None)

    if host_ids is not None and asset.category == "database":
        host_result = await db.execute(
            select(AssetHostRelation.host_id).where(AssetHostRelation.asset_id == asset_id)
        )
        before_host_ids = sorted(str(row[0]) for row in host_result.all())
        after_host_ids = sorted(str(host_id) for host_id in (host_ids or []))
        record_change("host_ids", before_host_ids, after_host_ids)

    if storage_locations_data is not None and asset.category == "database":
        storage_result = await db.execute(
            select(StorageLocation).where(StorageLocation.asset_id == asset_id)
        )
        before_storage_locations = _storage_location_items(storage_result.scalars().all())
        after_storage_locations = _storage_location_items(storage_locations_data)
        record_change("storage_locations", before_storage_locations, after_storage_locations)

    for field, value in update_data.items():
        # Map schema 'extra_data' to model 'extra_data'
        model_field = "extra_data" if field == "extra_data" else field
        record_change(field, getattr(asset, model_field, None), value)
        setattr(asset, model_field, value)

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="资产编号已存在")

    # Handle database asset relations (runs_on hosts) and storage locations.
    # host_ids/storage_locations_data being present-but-empty means "clear all".
    if host_ids is not None and asset.category == "database":
        await _sync_host_relations(db, asset_id, host_ids, replace=True)

    if storage_locations_data is not None and asset.category == "database":
        await _sync_storage_locations(db, asset_id, storage_locations_data, replace=True)

    # Audit log
    if changes:
        await log_operation(
            db, current_user.id, "update", "asset", 0,
            details={
                "name": asset.name,
                "category": asset.category,
                "asset_code": asset.asset_code,
                "changes": changes,
            },
            ip_address=ip,
        )

    await db.refresh(asset)

    # Reload asset with eagerly loaded relations to avoid lazy-load in async context
    reload_result = await db.execute(
        select(Asset).options(
            selectinload(Asset.credentials),
            selectinload(Asset.database_hosts).selectinload(AssetHostRelation.host_asset),
            selectinload(Asset.storage_locations),
        ).where(Asset.id == asset_id)
    )
    asset = reload_result.scalar_one()

    credentials = [
        {"id": c.id, "username": c.username, "credential_type": c.credential_type}
        for c in asset.credentials
    ]

    return build_asset_response(
        asset,
        org_name=None,
        include_credentials=True,
        credentials_data=credentials
    )


@router.delete("/{asset_id}", response_model=ResponseBase)
async def delete_asset(
    asset_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("manage")),
    request: Request = None,
):
    """Delete an asset"""
    ip = request.client.host if request and request.client else None
    result = await db.execute(
        select(Asset).where(Asset.id == asset_id)
    )
    asset = result.scalar_one_or_none()

    if not asset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="资产不存在"
        )

    # Check resource-level permission
    await check_resource_permission(
        current_user, "manage", "asset", asset_id, db,
        organization_id=asset.organization_id,
    )

    # Capture asset info before deletion
    asset_name = asset.name
    asset_category = asset.category
    asset_code = asset.asset_code

    # Remove dangling references from authorizations that target this asset
    await cleanup_authorization_targets(db, "asset", [asset_id])

    await db.delete(asset)
    await db.commit()

    # Audit log
    await log_operation(
        db, current_user.id, "delete", "asset", 0,
        details={
            "name": asset_name,
            "category": asset_category,
            "asset_code": asset_code,
        },
        ip_address=ip,
    )

    return ResponseBase(message="资产已删除")
