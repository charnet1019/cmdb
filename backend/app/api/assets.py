"""
Asset Management API
CRUD operations for assets, credentials, and organizations
"""
from typing import Optional, List
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import Asset, Credential, Organization, User
from app.schemas import (
    AssetCreate, AssetUpdate, AssetResponse, AssetSimple,
    AssetListResponse, PaginationMeta,
    CredentialCreate, CredentialUpdate, CredentialResponse, CredentialDecryptResponse,
    ResponseBase, BulkUpdateRequest, BulkDeleteRequest
)
from app.api.deps import get_current_user, PermissionChecker
from app.core.encryption import encrypt_value, decrypt_value


router = APIRouter(prefix="/assets", tags=["资产管理"])


# ============== Asset Statistics API ==============
@router.get("/stats")
async def get_asset_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get asset statistics by category and subcategory"""
    # Get total count
    total_result = await db.execute(select(func.count()).select_from(Asset))
    total = total_result.scalar() or 0

    # Get count by category
    category_result = await db.execute(
        select(Asset.category, func.count().label('count'))
        .group_by(Asset.category)
    )
    category_counts = {row.category: row.count for row in category_result}

    # Get count by platform (for host, database, cloud, web, gpt)
    platform_result = await db.execute(
        select(Asset.category, Asset.platform, func.count().label('count'))
        .where(Asset.platform.isnot(None))
        .group_by(Asset.category, Asset.platform)
    )
    platform_counts = {}
    for row in platform_result:
        key = f"{row.category}:{row.platform}"
        platform_counts[key] = row.count

    # Get count by device_type (for network)
    device_type_result = await db.execute(
        select(Asset.device_type, func.count().label('count'))
        .where(Asset.device_type.isnot(None))
        .group_by(Asset.device_type)
    )
    device_type_counts = {row.device_type: row.count for row in device_type_result}

    return {
        "code": 0,
        "data": {
            "total": total,
            "by_category": category_counts,
            "by_platform": platform_counts,
            "by_device_type": device_type_counts
        }
    }


# ============== Asset APIs ==============
@router.get("", response_model=AssetListResponse)
async def list_assets(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    category: Optional[str] = Query(None),
    organization_id: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all assets with pagination and filters"""
    query = select(Asset).options(selectinload(Asset.credentials))

    # Apply filters
    if category:
        query = query.where(Asset.category == category)

    if organization_id:
        query = query.where(Asset.organization_id == organization_id)

    if search:
        query = query.where(
            or_(
                Asset.name.ilike(f"%{search}%"),
                Asset.address.ilike(f"%{search}%"),
                Asset.notes.ilike(f"%{search}%"),
            )
        )

    if is_active is not None:
        query = query.where(Asset.is_active == is_active)

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # Apply pagination
    query = query.offset((page - 1) * limit).limit(limit)
    query = query.order_by(Asset.created_at.desc())

    result = await db.execute(query)
    assets = result.scalars().all()

    # Build response
    asset_responses = []
    for asset in assets:
        credentials = [
            {
                "id": c.id,
                "username": c.username,
                "credential_type": c.credential_type,
            }
            for c in asset.credentials
        ]

        asset_responses.append({
            "id": asset.id,
            "name": asset.name,
            "asset_code": asset.asset_code,
            "category": asset.category,
            "address": asset.address,
            "platform": asset.platform,
            "organization_id": asset.organization_id,
            "device_type": asset.device_type,
            "vendor": asset.vendor,
            "model": asset.model,
            "serial_number": asset.serial_number,
            "url": asset.url,
            "notes": asset.notes,
            "metadata": asset.extra_data,
            "is_active": asset.is_active,
            "created_at": asset.created_at,
            "credentials": credentials,
        })

    return AssetListResponse(
        data=asset_responses,
        meta=PaginationMeta(
            total=total,
            page=page,
            limit=limit,
            pages=(total + limit - 1) // limit,
        )
    )


@router.post("", response_model=AssetResponse, status_code=status.HTTP_201_CREATED)
async def create_asset(
    data: AssetCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new asset"""
    # Validate category
    valid_categories = ["host", "network", "database", "cloud", "web", "gpt"]
    if data.category not in valid_categories:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"无效的资产类型: {data.category}"
        )

    asset = Asset(
        name=data.name,
        asset_code=data.asset_code,
        category=data.category,
        address=data.address,
        platform=data.platform,
        organization_id=data.organization_id,
        device_type=data.device_type,
        vendor=data.vendor,
        model=data.model,
        serial_number=data.serial_number,
        url=data.url,
        notes=data.notes,
        extra_data=data.metadata,
    )

    db.add(asset)
    await db.commit()
    await db.refresh(asset)

    return AssetResponse(
        id=asset.id,
        name=asset.name,
        asset_code=asset.asset_code,
        category=asset.category,
        address=asset.address,
        platform=asset.platform,
        organization_id=asset.organization_id,
        device_type=asset.device_type,
        vendor=asset.vendor,
        model=asset.model,
        serial_number=asset.serial_number,
        url=asset.url,
        notes=asset.notes,
        metadata=asset.extra_data,
        is_active=asset.is_active,
        created_at=asset.created_at,
        credentials=[],
    )


@router.get("/{asset_id}", response_model=AssetResponse)
async def get_asset(
    asset_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get asset by ID"""
    result = await db.execute(
        select(Asset)
        .options(selectinload(Asset.credentials))
        .where(Asset.id == asset_id)
    )
    asset = result.scalar_one_or_none()

    if not asset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="资产不存在"
        )

    credentials = [
        {
            "id": c.id,
            "username": c.username,
            "credential_type": c.credential_type,
        }
        for c in asset.credentials
    ]

    return AssetResponse(
        id=asset.id,
        name=asset.name,
        asset_code=asset.asset_code,
        category=asset.category,
        address=asset.address,
        platform=asset.platform,
        organization_id=asset.organization_id,
        device_type=asset.device_type,
        vendor=asset.vendor,
        model=asset.model,
        serial_number=asset.serial_number,
        url=asset.url,
        notes=asset.notes,
        metadata=asset.extra_data,
        is_active=asset.is_active,
        created_at=asset.created_at,
        credentials=credentials,
    )


@router.put("/{asset_id}", response_model=AssetResponse)
async def update_asset(
    asset_id: int,
    data: AssetUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update asset information"""
    result = await db.execute(
        select(Asset).where(Asset.id == asset_id)
    )
    asset = result.scalar_one_or_none()

    if not asset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="资产不存在"
        )

    # Update fields
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        # Map schema 'metadata' to model 'extra_data'
        if field == "metadata":
            setattr(asset, "extra_data", value)
        else:
            setattr(asset, field, value)

    await db.commit()
    await db.refresh(asset)

    # Get credentials
    cred_result = await db.execute(
        select(Credential).where(Credential.asset_id == asset.id)
    )
    credentials = cred_result.scalars().all()

    return AssetResponse(
        id=asset.id,
        name=asset.name,
        asset_code=asset.asset_code,
        category=asset.category,
        address=asset.address,
        platform=asset.platform,
        organization_id=asset.organization_id,
        device_type=asset.device_type,
        vendor=asset.vendor,
        model=asset.model,
        serial_number=asset.serial_number,
        url=asset.url,
        notes=asset.notes,
        metadata=asset.extra_data,
        is_active=asset.is_active,
        created_at=asset.created_at,
        credentials=[
            {"id": c.id, "username": c.username, "credential_type": c.credential_type}
            for c in credentials
        ],
    )


@router.delete("/{asset_id}", response_model=ResponseBase)
async def delete_asset(
    asset_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete an asset"""
    result = await db.execute(
        select(Asset).where(Asset.id == asset_id)
    )
    asset = result.scalar_one_or_none()

    if not asset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="资产不存在"
        )

    await db.delete(asset)
    await db.commit()

    return ResponseBase(message="资产已删除")


# ============== Bulk Operations APIs ==============
@router.put("/bulk", response_model=ResponseBase)
async def bulk_update_assets(
    request: BulkUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Bulk update assets (activate/deactivate)"""
    if not request.ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请选择要操作的资产"
        )

    result = await db.execute(
        select(Asset).where(Asset.id.in_(request.ids))
    )
    assets = result.scalars().all()

    if not assets:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="未找到任何资产"
        )

    # Update each asset
    for asset in assets:
        if "is_active" in request.data:
            asset.is_active = request.data["is_active"]

    await db.commit()

    return ResponseBase(message=f"已更新 {len(assets)} 个资产")


@router.delete("/bulk", response_model=ResponseBase)
async def bulk_delete_assets(
    request: BulkDeleteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Bulk delete assets"""
    if not request.ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请选择要删除的资产"
        )

    result = await db.execute(
        select(Asset).where(Asset.id.in_(request.ids))
    )
    assets = result.scalars().all()

    if not assets:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="未找到任何资产"
        )

    # Delete each asset
    for asset in assets:
        await db.delete(asset)

    await db.commit()

    return ResponseBase(message=f"已删除 {len(assets)} 个资产")


# ============== Organization/Asset Tree APIs ==============
org_router = APIRouter(prefix="/organizations", tags=["组织架构"])


@org_router.get("")
async def list_organizations(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all organizations as tree structure"""
    result = await db.execute(
        select(Organization).order_by(Organization.path)
    )
    organizations = result.scalars().all()

    # Build tree structure
    org_map = {}
    for org in organizations:
        # Get asset count
        count_result = await db.execute(
            select(func.count()).select_from(Asset).where(Asset.organization_id == org.id)
        )
        asset_count = count_result.scalar() or 0

        org_map[org.id] = {
            "id": org.id,
            "name": org.name,
            "parent_id": org.parent_id,
            "path": org.path,
            "level": org.level,
            "count": asset_count,
            "children": [],
        }

    # Build tree
    root_nodes = []
    for org_id, org_data in org_map.items():
        parent_id = org_data["parent_id"]
        if parent_id and parent_id in org_map:
            org_map[parent_id]["children"].append(org_data)
        else:
            root_nodes.append(org_data)

    return {"code": 0, "data": root_nodes}


@org_router.post("")
async def create_organization(
    name: str,
    parent_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
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

    return {"code": 0, "data": {"id": org.id, "name": org.name, "path": org.path}}


# ============== Credential APIs ==============
cred_router = APIRouter(prefix="/credentials", tags=["凭证管理"])


@cred_router.get("")
async def list_credentials(
    asset_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List credentials for an asset"""
    query = select(Credential)

    if asset_id:
        query = query.where(Credential.asset_id == asset_id)

    result = await db.execute(query)
    credentials = result.scalars().all()

    return {
        "code": 0,
        "data": [
            {
                "id": c.id,
                "asset_id": c.asset_id,
                "username": c.username,
                "credential_type": c.credential_type,
                "created_at": c.created_at,
            }
            for c in credentials
        ]
    }


@cred_router.post("", response_model=CredentialResponse, status_code=status.HTTP_201_CREATED)
async def create_credential(
    data: CredentialCreate,
    asset_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new credential for an asset"""
    # Verify asset exists
    result = await db.execute(
        select(Asset).where(Asset.id == asset_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="资产不存在"
        )

    credential = Credential(
        asset_id=asset_id,
        username=data.username,
        password_encrypted=encrypt_value(data.password),
        credential_type=data.credential_type,
        extra_data=data.metadata,
    )

    db.add(credential)
    await db.commit()
    await db.refresh(credential)

    return CredentialResponse(
        id=credential.id,
        asset_id=credential.asset_id,
        username=credential.username,
        credential_type=credential.credential_type,
        created_at=credential.created_at,
    )


@cred_router.post("/{credential_id}/decrypt", response_model=CredentialDecryptResponse)
async def decrypt_credential(
    credential_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("view_pwd")),
):
    """Decrypt credential password (requires view_pwd permission)"""
    result = await db.execute(
        select(Credential).where(Credential.id == credential_id)
    )
    credential = result.scalar_one_or_none()

    if not credential:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="凭证不存在"
        )

    try:
        decrypted_password = decrypt_value(credential.password_encrypted)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="解密失败"
        )

    return CredentialDecryptResponse(
        id=credential.id,
        username=credential.username,
        password=decrypted_password,
    )


@cred_router.put("/{credential_id}", response_model=CredentialResponse)
async def update_credential(
    credential_id: int,
    data: CredentialUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a credential"""
    result = await db.execute(
        select(Credential).where(Credential.id == credential_id)
    )
    credential = result.scalar_one_or_none()

    if not credential:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="凭证不存在"
        )

    # Update fields
    if data.username is not None:
        credential.username = data.username
    if data.password is not None:
        credential.password_encrypted = encrypt_value(data.password)
    if data.metadata is not None:
        credential.extra_data = data.metadata

    await db.commit()
    await db.refresh(credential)

    return CredentialResponse(
        id=credential.id,
        asset_id=credential.asset_id,
        username=credential.username,
        credential_type=credential.credential_type,
        created_at=credential.created_at,
    )


@cred_router.delete("/{credential_id}", response_model=ResponseBase)
async def delete_credential(
    credential_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a credential"""
    result = await db.execute(
        select(Credential).where(Credential.id == credential_id)
    )
    credential = result.scalar_one_or_none()

    if not credential:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="凭证不存在"
        )

    await db.delete(credential)
    await db.commit()

    return ResponseBase(message="凭证已删除")