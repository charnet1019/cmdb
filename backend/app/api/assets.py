"""
Asset Management API
CRUD operations for assets, credentials, and organizations
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
from urllib.parse import quote
from io import BytesIO
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request, File, UploadFile, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, delete, inspect, false
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import Asset, Authorization, Credential, Organization, User, AssetHostRelation, StorageLocation, PasswordChangeLog
from app.schemas import (
    AssetCreate, AssetUpdate, AssetResponse, AssetSimple,
    AssetListResponse, PaginationMeta,
    CredentialCreate, CredentialUpdate, CredentialResponse, CredentialDecryptResponse,
    ResponseBase, BulkUpdateRequest, BulkDeleteRequest
)
from app.api.deps import get_user_permissions, PermissionChecker, check_resource_permission, get_authorized_asset_ids
from app.core.encryption import encrypt_value, decrypt_value
from app.services.import_service import (
    generate_category_template,
    parse_import_file,
    batch_create_assets,
    batch_update_assets,
    CATEGORY_FIELDS,
    get_created_orgs,
)
from app.services.export_service import (
    export_assets_to_excel,
    export_assets_to_csv,
    _export_excel_stream,
    _export_csv_stream,
    CATEGORY_COLUMNS,
    DEFAULT_COLUMNS,
)
from app.utils.audit import log_operation


# Request models
class ImportResult(BaseModel):
    """Import result data"""
    total_rows: int
    success_count: int
    failed_count: int
    errors: List[Dict[str, Any]] = []


class ImportResponse(ResponseBase):
    """Import response schema"""
    data: ImportResult


router = APIRouter(prefix="/assets", tags=["资产管理"])


# Asset type specific fields mapping
# Fields that are specific to each asset category (not common fields)
ASSET_TYPE_FIELDS: Dict[str, List[str]] = {
    "host": [
        "cpu", "memory", "system_disk", "data_disk", "model",
        "serial_number", "vendor"
    ],
    "network": [
        "device_type", "vendor", "model", "serial_number"
    ],
    "database": [
        "db_type", "version", "namespace"
    ],
    "cloud": [],
    "web": [],
    "gpt": [],
}

# Common fields for all asset types
COMMON_FIELDS = [
    "id", "name", "asset_code", "category", "internal_address",
    "external_address", "platform", "organization_id", "organization_name",
    "notes", "extra_data", "created_at", "updated_at",
    "applicant", "credentials"
]


def build_asset_response(
    asset: Asset,
    org_name: Optional[str] = None,
    include_credentials: bool = True,
    credentials_data: Optional[List[Dict]] = None,
    include_decrypted_passwords: bool = False,
    creator_name: Optional[str] = None,
    owner_name: Optional[str] = None,
    oob_password: Optional[str] = None
) -> Dict[str, Any]:
    """
    Build asset response dictionary based on asset category.
    Only includes fields relevant to the asset type to reduce payload size.

    Args:
        asset: Asset instance
        org_name: Organization name (pre-fetched)
        include_credentials: Whether to include credentials in response
        credentials_data: Credentials data (pre-fetched and formatted)
        include_decrypted_passwords: Whether credentials include decrypted passwords (for export)
    """
    category = asset.category
    type_fields = ASSET_TYPE_FIELDS.get(category, [])

    # Start with common fields (only non-None values)
    data: Dict[str, Any] = {
        "id": str(asset.id),
        "name": asset.name,
        "category": category,
    }

    # Add optional common fields only if not None
    if asset.asset_code:
        data["asset_code"] = asset.asset_code
    if asset.internal_address:
        data["internal_address"] = asset.internal_address
    if asset.external_address:
        data["external_address"] = asset.external_address
    if asset.platform:
        data["platform"] = asset.platform
    if asset.db_type:  # Keep for database category filter
        data["db_type"] = asset.db_type
    if asset.organization_id:
        data["organization_id"] = asset.organization_id
    if org_name:
        data["organization_name"] = org_name
    if asset.notes:
        data["notes"] = asset.notes
    if asset.extra_data:
        # Filter out sensitive fields (oob_password) from extra_data
        filtered_extra_data = {
            k: v for k, v in asset.extra_data.items()
            if k not in ("oob_password",)
        }
        if filtered_extra_data:
            data["extra_data"] = filtered_extra_data
    if asset.created_at:
        data["created_at"] = asset.created_at.isoformat()
    if asset.updated_at:
        data["updated_at"] = asset.updated_at.isoformat()
    if asset.applicant:
        data["applicant"] = asset.applicant
    if asset.namespace:  # For database assets
        data["namespace"] = asset.namespace
    # Extract version from extra_data (metadata) for database assets
    if asset.extra_data and "version" in asset.extra_data:
        data["version"] = asset.extra_data["version"]
    if creator_name:
        data["creator_name"] = creator_name
    if asset.owner_id:
        data["owner_id"] = asset.owner_id
    if owner_name or asset.owner_name:
        data["owner_name"] = owner_name or asset.owner_name
    # OOB fields (for host category)
    if asset.oob_address:
        data["oob_address"] = asset.oob_address
    if asset.oob_username:
        data["oob_username"] = asset.oob_username
    if oob_password is not None:
        data["oob_password"] = oob_password
    if asset.status:
        data["status"] = asset.status
    # Database asset fields (runs_on hosts and storage_locations)
    # Only include if already loaded to avoid lazy-loading in async context
    if asset.category == "database":
        unloaded = inspect(asset).unloaded
        if "database_hosts" not in unloaded:
            hosts = asset.database_hosts
            if hosts:
                runs_on_list = []
                for r in hosts:
                    host = r.host_asset if r.host_asset else None
                    if host:
                        runs_on_list.append({
                            "id": str(r.host_id),
                            "name": getattr(host, 'name', ''),
                            "internal_address": getattr(host, 'internal_address', '')
                        })
                data["runs_on_hosts"] = runs_on_list
        if "storage_locations" not in unloaded:
            locs = asset.storage_locations
            if locs:
                data["storage_locations"] = [
                    {
                        "id": sl.id,
                        "path": sl.path,
                        "path_type": sl.path_type,
                        "description": sl.description,
                        "created_at": sl.created_at.isoformat() if sl.created_at else None
                    }
                    for sl in locs
                ]

    # Add type-specific fields only
    for field in type_fields:
        value = getattr(asset, field, None)
        # Only include if not None (to reduce payload)
        if value is not None:
            data[field] = value

    # Add credentials if requested
    if include_credentials:
        data["credentials"] = credentials_data or []

    return data


# Helper function to get all descendant organization IDs
async def get_descendant_org_ids(db: AsyncSession, org_id: int) -> List[int]:
    """Get all descendant organization IDs including the given org_id"""
    # Get the organization's path
    result = await db.execute(
        select(Organization).where(Organization.id == org_id)
    )
    org = result.scalar_one_or_none()
    if not org:
        return [org_id]

    # Find all descendants using path prefix match
    # Path format: "1/2/3" where 3 is the leaf, 2 is parent, 1 is root
    if org.path:
        # Match organizations whose path starts with this org's path + "/" or is exactly this path
        descendants = await db.execute(
            select(Organization.id).where(
                or_(
                    Organization.path == org.path,
                    Organization.path.like(f"{org.path}/%"),
                    Organization.path.like(f"{org.path}%")
                )
            )
        )
        ids = [row[0] for row in descendants.all()]
    else:
        # If path is null, just return the org_id itself
        ids = [org_id]

    return ids if ids else [org_id]


def apply_search_filter(query, search):
    """Apply search filter to asset query — shared by list and export endpoints"""
    if not search:
        return query
    return query.where(
        or_(
            Asset.name.ilike(f"%{search}%"),
            Asset.asset_code.ilike(f"%{search}%"),
            Asset.internal_address.ilike(f"%{search}%"),
            Asset.external_address.ilike(f"%{search}%"),
            Asset.notes.ilike(f"%{search}%"),
        )
    )


# ============== Asset Statistics API ==============
@router.get("/stats")
async def get_asset_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("view")),
):
    """Get asset statistics by category and subcategory"""
    # Resource-level authorization filter
    authorized_ids = await get_authorized_asset_ids(current_user, db, "view")
    if authorized_ids is None:
        asset_filter = None
    elif len(authorized_ids) == 0:
        asset_filter = false()
    else:
        asset_filter = Asset.id.in_(authorized_ids)

    # Get total count
    if asset_filter is not None:
        total_result = await db.execute(select(func.count()).where(asset_filter))
    else:
        total_result = await db.execute(select(func.count()).select_from(Asset))
    total = total_result.scalar() or 0

    # Get count by category
    cat_query = select(Asset.category, func.count().label('count'))
    if asset_filter is not None:
        cat_query = cat_query.where(asset_filter)
    category_result = await db.execute(cat_query.group_by(Asset.category))
    category_counts = {row.category: row.count for row in category_result}

    # Get count by platform (for host, database, cloud, web, gpt)
    plat_query = select(Asset.category, Asset.platform, func.count().label('count')).where(Asset.platform.isnot(None))
    if asset_filter is not None:
        plat_query = plat_query.where(asset_filter)
    platform_result = await db.execute(plat_query.group_by(Asset.category, Asset.platform))
    platform_counts = {}
    for row in platform_result:
        key = f"{row.category}:{row.platform}"
        platform_counts[key] = row.count

    # Get count by device_type (for network)
    dt_query = select(Asset.device_type, func.count().label('count')).where(Asset.device_type.isnot(None))
    if asset_filter is not None:
        dt_query = dt_query.where(asset_filter)
    device_type_result = await db.execute(dt_query.group_by(Asset.device_type))
    device_type_counts = {row.device_type: row.count for row in device_type_result}

    # Get count by db_type (for database)
    dbt_query = select(Asset.db_type, func.count().label('count')).where(Asset.db_type.isnot(None))
    if asset_filter is not None:
        dbt_query = dbt_query.where(asset_filter)
    db_type_result = await db.execute(dbt_query.group_by(Asset.db_type))
    db_type_counts = {row.db_type: row.count for row in db_type_result}

    return {
        "code": 0,
        "data": {
            "total": total,
            "by_category": category_counts,
            "by_platform": platform_counts,
            "by_device_type": device_type_counts,
            "by_db_type": db_type_counts
        }
    }


# ============== Asset APIs ==============
@router.get("")
async def list_assets(
    response: Response,

    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    category: Optional[str] = None,
    organization_id: Optional[int] = None,
    owner_id: Optional[int] = None,
    owner_name: Optional[str] = None,
    search: Optional[str] = None,
    status: Optional[str] = None,
    platform: Optional[str] = None,
    device_type: Optional[str] = None,
    db_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("view")),
):
    """List all assets with pagination and filters"""
    query = select(Asset).options(
        selectinload(Asset.credentials),
    )

    # Only eager-load database-specific relations when needed
    if category is None or category == "database":
        query = query.options(
            selectinload(Asset.database_hosts).selectinload(AssetHostRelation.host_asset),
            selectinload(Asset.storage_locations),
        )

    # Apply filters
    if category:
        query = query.where(Asset.category == category)

    if platform:
        query = query.where(Asset.platform == platform)

    if device_type:
        query = query.where(Asset.device_type == device_type)

    if db_type:
        query = query.where(Asset.db_type == db_type)

    if organization_id is not None:
        # Get all descendant organization IDs and filter by them
        org_ids = await get_descendant_org_ids(db, organization_id)
        query = query.where(Asset.organization_id.in_(org_ids))

    if owner_id is not None:
        query = query.where(Asset.owner_id == owner_id)

    if owner_name:
        query = query.where(Asset.owner_name.ilike(f"%{owner_name}%"))

    if search:
        query = apply_search_filter(query, search)

    if status is not None:
        query = query.where(Asset.status == status)

    # Resource-level authorization filter
    authorized_ids = await get_authorized_asset_ids(current_user, db, "view")
    if authorized_ids is not None and len(authorized_ids) == 0:
        # No authorized assets — return empty immediately
        return {
            "code": 0,
            "data": {
                "items": [],
                "total": 0,
                "page": page,
                "limit": limit,
            }
        }
    if authorized_ids is not None:
        query = query.where(Asset.id.in_(authorized_ids))

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # Apply pagination
    query = query.offset((page - 1) * limit).limit(limit)
    query = query.order_by(Asset.created_at.desc())

    result = await db.execute(query)
    assets = result.scalars().all()

    # Get all organization names
    org_ids = set(a.organization_id for a in assets if a.organization_id)
    org_names = {}
    if org_ids:
        org_result = await db.execute(select(Organization.id, Organization.name).where(Organization.id.in_(org_ids)))
        org_names = {row.id: row.name for row in org_result}

    # Get creator names
    creator_ids = set(a.created_by_id for a in assets if a.created_by_id)
    creator_names = {}
    if creator_ids:
        creator_result = await db.execute(select(User.id, User.username).where(User.id.in_(creator_ids)))
        creator_names = {row.id: row.username for row in creator_result}

    # Get owner names (for assets without owner_name cached)
    owner_ids = set(a.owner_id for a in assets if a.owner_id and not a.owner_name)
    owner_names = {}
    if owner_ids:
        owner_result = await db.execute(select(User.id, User.username).where(User.id.in_(owner_ids)))
        owner_names = {row.id: row.username for row in owner_result}

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

        # Determine owner name
        owner_name_val = asset.owner_name or owner_names.get(asset.owner_id) if asset.owner_id else None

        asset_responses.append(build_asset_response(
            asset,
            org_name=org_names.get(asset.organization_id),
            include_credentials=True,
            credentials_data=credentials,
            creator_name=creator_names.get(asset.created_by_id),
            owner_name=owner_name_val
        ))

    pages = (total + limit - 1) // limit if total > 0 else 0

    return {
        "code": 0,
        "message": "success",
        "data": asset_responses,
        "meta": {
            "total": total,
            "page": page,
            "limit": limit,
            "pages": pages
        }
    }


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_asset(
    data: AssetCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("manage")),
    request: Request = None,
) -> Dict[str, Any]:
    """Create a new asset"""
    ip = request.client.host if request and request.client else None
    # Validate category
    valid_categories = ["host", "network", "database", "cloud", "web", "gpt"]
    if data.category not in valid_categories:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"无效的资产类型: {data.category}"
        )

    # Validate and get owner info
    owner_id = data.owner_id
    owner_name = data.owner_name
    if owner_id and not owner_name:
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
    elif owner_name and not owner_id:
        # Try to find user by username
        result = await db.execute(select(User.id, User.username).where(User.username == owner_name))
        owner_result = result.first()
        if owner_result:
            owner_id = owner_result[0]
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="负责人不存在"
            )

    # Encrypt OOB password if provided
    oob_password_encrypted = None
    if data.oob_password:
        oob_password_encrypted = encrypt_value(data.oob_password)

    asset = Asset(
        name=data.name,
        asset_code=data.asset_code,
        category=data.category,
        created_by_id=current_user.id,
        internal_address=data.internal_address,
        external_address=data.external_address,
        platform=data.platform,
        db_type=data.db_type,
        organization_id=data.organization_id,
        device_type=data.device_type,
        vendor=data.vendor,
        model=data.model,
        serial_number=data.serial_number,
        cpu=data.cpu,
        memory=data.memory,
        system_disk=data.system_disk,
        data_disk=data.data_disk,
        notes=data.notes,
        extra_data=data.extra_data,
        applicant=data.applicant,
        namespace=data.namespace,
        owner_id=owner_id,
        owner_name=owner_name,
        # OOB fields
        oob_address=data.oob_address,
        oob_username=data.oob_username,
        oob_password_encrypted=oob_password_encrypted,
        status=data.status,
    )

    db.add(asset)
    await db.commit()
    await db.refresh(asset)

    # Audit log
    await log_operation(
        db, current_user.id, "create", "asset", 0,
        details={
            "name": asset.name,
            "category": asset.category,
            "asset_code": asset.asset_code,
        },
        ip_address=ip,
    )

    # Auto-authorize creator with "manage" on the new asset
    if not current_user.is_superuser:
        # Try to append to existing asset-level authorization with "manage"
        existing = await db.execute(
            select(Authorization)
            .where(Authorization.entity_type == "user")
            .where(Authorization.entity_id == current_user.id)
            .where(Authorization.target_type == "asset")
            .where(Authorization.is_active == True)
            .where(Authorization.permissions.contains(["manage"]))
            .order_by(Authorization.id.desc())
            .limit(1)
        )
        existing = existing.scalar_one_or_none()
        if existing:
            target_ids = list(existing.target_ids or [])
            if asset.id not in target_ids:
                target_ids.append(asset.id)
                existing.target_ids = target_ids
            await db.commit()
        else:
            existing = Authorization(
                entity_type="user",
                entity_id=current_user.id,
                target_type="asset",
                target_ids=[asset.id],
                permissions=["manage"],
                created_by=current_user.id,
            )
            db.add(existing)
        await db.commit()

    # Handle database asset relations (runs_on hosts)
    if data.host_ids and data.category == "database":
        for host_id in data.host_ids:
            # Validate host exists and is category='host'
            host_result = await db.execute(
                select(Asset).where(Asset.id == host_id, Asset.category == "host")
            )
            host_asset = host_result.scalar_one_or_none()
            if host_asset:
                relation = AssetHostRelation(asset_id=asset.id, host_id=host_id)
                db.add(relation)
        await db.commit()

    # Handle storage locations for database assets
    if data.storage_locations and data.category == "database":
        for loc in data.storage_locations:
            storage = StorageLocation(
                asset_id=asset.id,
                path=loc.path,
                path_type=loc.path_type,
                description=loc.description
            )
            db.add(storage)
        await db.commit()

    # Reload asset with relations
    # For database assets, load database_hosts and storage_locations to include in response
    if data.category == "database":
        reload_result = await db.execute(
            select(Asset).options(
                selectinload(Asset.credentials),
                selectinload(Asset.database_hosts).selectinload(AssetHostRelation.host_asset),
                selectinload(Asset.storage_locations),
            ).where(Asset.id == asset.id)
        )
        asset = reload_result.scalar_one()
    else:
        await db.refresh(asset)

    return build_asset_response(
        asset,
        org_name=None,
        include_credentials=True,
        credentials_data=[],
        creator_name=current_user.username,
        owner_name=owner_name
    )


# ============== Bulk Operations APIs ==============
@router.put("/bulk", response_model=ResponseBase)
async def bulk_update_assets(
    body: BulkUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("manage")),
    request: Request = None,
):
    """Bulk update assets (activate/deactivate)"""
    ip = request.client.host if request and request.client else None
    if not body.ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请选择要操作的资产"
        )

    result = await db.execute(
        select(Asset).where(Asset.id.in_(body.ids))
    )
    assets = result.scalars().all()

    if not assets:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="未找到任何资产"
        )

    # Check resource-level permission for each asset
    for asset in assets:
        await check_resource_permission(
            current_user, "manage", "asset", asset.id, db,
            organization_id=asset.organization_id,
        )

    # Update each asset
    for asset in assets:
        if "status" in body.data:
            asset.status = body.data["status"]

    await db.commit()

    # Audit log
    await log_operation(
        db, current_user.id, "update", "asset", 0,
        details={
            "action": "bulk_update",
            "count": len(assets),
            "asset_ids": [a.id for a in assets],
            "data": body.data,
        },
        ip_address=ip,
    )

    return ResponseBase(message=f"已更新 {len(assets)} 个资产")


@router.delete("/bulk", response_model=ResponseBase)
async def bulk_delete_assets(
    body: BulkDeleteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("manage")),
    request: Request = None,
):
    """Bulk delete assets"""
    ip = request.client.host if request and request.client else None
    if not body.ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请选择要删除的资产"
        )

    result = await db.execute(
        select(Asset).where(Asset.id.in_(body.ids))
    )
    assets = result.scalars().all()

    if not assets:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="未找到任何资产"
        )

    # Check resource-level permission for each asset
    for asset in assets:
        await check_resource_permission(
            current_user, "manage", "asset", asset.id, db,
            organization_id=asset.organization_id,
        )

    # Delete each asset
    for asset in assets:
        await db.delete(asset)

    await db.commit()

    # Audit log
    await log_operation(
        db, current_user.id, "delete", "asset", 0,
        details={
            "action": "bulk_delete",
            "count": len(assets),
            "asset_ids": [a.id for a in assets],
        },
        ip_address=ip,
    )

    return ResponseBase(message=f"已删除 {len(assets)} 个资产")


# ============== Import APIs ==============
@router.get("/import/template/{category}")
async def download_import_template(
    category: str,
    mode: str = Query("create", description="create or update"),
    current_user: User = Depends(PermissionChecker("manage")),
):
    """Download XLSX import template for specified category."""
    if category not in CATEGORY_FIELDS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的资产类型：{category}"
        )
    if mode not in ("create", "update"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="mode 参数必须是 create 或 update"
        )

    buffer, filename = generate_category_template(category, mode)
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{quote(filename)}"'},
    )


@router.post("/import/{category}", response_model=ImportResponse)
async def import_assets(
    category: str,
    mode: str = Query("create", description="create or update"),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("manage")),
):
    """Import assets from XLSX file."""
    # Validate category before reading file
    if category not in CATEGORY_FIELDS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的资产类型：{category}。支持的类型：{', '.join(CATEGORY_FIELDS.keys())}"
        )
    if mode not in ("create", "update"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="mode 参数必须是 create 或 update"
        )

    # Validate file type by extension and magic bytes
    if not file.filename or not file.filename.endswith(".xlsx"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请上传xlsx格式的文件"
        )

    # Read file content
    content = await file.read()

    # Validate file size (max 10MB)
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="文件大小不能超过10MB"
        )

    # Validate XLSX magic bytes (ZIP archive starting with PK)
    if not content.startswith(b'PK'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="文件格式不正确，请上传有效的 xlsx 文件"
        )

    try:
        valid_records, parse_errors = await parse_import_file(content, category, mode, db)

        # Dispatch to unified batch handler
        batch_fn = (
            batch_create_assets if mode == "create"
            else batch_update_assets
        )

        process_errors = []
        if mode == "create":
            success_count, process_errors = await batch_fn(category, valid_records, db, current_user.id)
        else:
            allowed_records = []
            for record in valid_records:
                asset_id = record.get("id")
                result = await db.execute(select(Asset).where(Asset.id == asset_id))
                asset = result.scalar_one_or_none()
                if not asset:
                    allowed_records.append(record)
                    continue
                if asset.category != category:
                    process_errors.append({"id": asset_id, "error": "资产类型不匹配"})
                    continue
                try:
                    await check_resource_permission(
                        current_user, "manage", "asset", asset.id, db,
                        organization_id=asset.organization_id,
                    )
                except HTTPException as exc:
                    process_errors.append({"id": asset_id, "error": exc.detail})
                    continue
                allowed_records.append(record)

            success_count, update_errors = await batch_fn(category, allowed_records, db)
            process_errors.extend(update_errors)

        all_errors = parse_errors + process_errors

        # Audit log
        created_orgs = get_created_orgs()
        await log_operation(
            db=db,
            user_id=current_user.id,
            action="import",
            resource_type="asset",
            resource_id=0,
            details={
                "name": f"import_{category}",
                "category": category,
                "mode": mode,
                "total_rows": len(valid_records) + len(parse_errors),
                "success_count": success_count,
                "failed_count": len(all_errors),
                "created_orgs": list(created_orgs) if created_orgs else None,
            },
        )

        return ImportResponse(
            data=ImportResult(
                total_rows=len(valid_records) + len(parse_errors),
                success_count=success_count,
                failed_count=len(all_errors),
                errors=all_errors
            )
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"导入处理失败: {str(e)}"
        )


# ============== Export APIs ==============

def build_org_full_path(org_id: int | None, org_map: Dict[int, tuple]) -> str:
    """Build full organization path from org_id, e.g. 'Default / 研发部 / 服务器组'"""
    if org_id is None:
        return "Default"
    parts = []
    current_id = org_id
    while current_id in org_map:
        name, parent_id = org_map[current_id]
        parts.append(name)
        current_id = parent_id
    parts.append("Default")
    parts.reverse()
    return " / ".join(parts)

@router.get("/export")
async def export_assets(
    format: str = Query("excel", description="excel or csv"),
    scope: str = Query("all", description="all, selected, or filtered"),
    category: Optional[str] = Query(None, description="Asset category"),
    organization_id: Optional[int] = Query(None, description="Organization ID"),
    search: Optional[str] = Query(None, description="Search query"),
    ids: Optional[str] = Query(None, description="Comma-separated asset IDs for selected scope"),
    include_passwords: bool = Query(False, description="Whether to include decrypted asset credentials"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("export")),
):
    """
    Export assets to Excel or CSV with chunked streaming.
    scope: all (all assets), selected (specific IDs), filtered (current search/filter)
    """
    CHUNK_SIZE = 500

    # Build query based on scope
    query = select(Asset)

    if scope == "selected" and ids:
        asset_ids = [id.strip() for id in ids.split(",") if id.strip()]
        if not asset_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="请选择要导出的资产"
            )
        query = query.where(Asset.id.in_(asset_ids))
    else:
        if category:
            query = query.where(Asset.category == category)
        if organization_id is not None:
            org_ids = await get_descendant_org_ids(db, organization_id)
            query = query.where(Asset.organization_id.in_(org_ids))
        if search:
            query = apply_search_filter(query, search)

    # Resource-level authorization filter
    authorized_ids = await get_authorized_asset_ids(current_user, db, "view")
    if authorized_ids is not None and len(authorized_ids) == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="未找到要导出的资产"
        )
    if authorized_ids is not None:
        query = query.where(Asset.id.in_(authorized_ids))

    can_export_passwords = False
    if include_passwords:
        permissions = await get_user_permissions(current_user, db)
        if "view_pwd" not in permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="导出密码需要 'view_pwd' 权限",
            )
        password_authorized_ids = await get_authorized_asset_ids(current_user, db, "view_pwd")
        if password_authorized_ids is not None and len(password_authorized_ids) == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="未找到允许导出密码的资产",
            )
        if password_authorized_ids is not None:
            query = query.where(Asset.id.in_(password_authorized_ids))
        can_export_passwords = True

    query = query.options(selectinload(Asset.credentials))
    if category == "database":
        query = query.options(
            selectinload(Asset.database_hosts).selectinload(AssetHostRelation.host_asset),
            selectinload(Asset.storage_locations),
        )

    # Count for 404 check and audit
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0
    if total == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="未找到要导出的资产"
        )

    # Execute with chunking
    query = query.limit(CHUNK_SIZE)

    # Column config
    export_category = category if category else None
    export_columns = (
        CATEGORY_COLUMNS.get(export_category, DEFAULT_COLUMNS)
        if export_category
        else DEFAULT_COLUMNS
    )

    # --- async generator: yields formatted asset dicts chunk by chunk ---

    org_map: Dict[int, tuple] = {}
    creator_names: Dict[int, str] = {}

    async def _asset_data_gen():
        nonlocal org_map, creator_names
        offset = 0
        while True:
            chunk_query = query.offset(offset).order_by(Asset.id)
            result = await db.execute(chunk_query)
            assets = result.scalars().all()
            if not assets:
                break

            # First chunk: load org_map for full-path building
            if not org_map:
                org_ids = set(
                    a.organization_id for a in assets if a.organization_id is not None
                )
                if org_ids:
                    all_org_ids = set(org_ids)
                    while True:
                        org_result = await db.execute(
                            select(Organization.id, Organization.name, Organization.parent_id)
                            .where(Organization.id.in_(all_org_ids))
                        )
                        rows = org_result.fetchall()
                        for row in rows:
                            org_map[row.id] = (row.name, row.parent_id)
                            if row.parent_id and row.parent_id not in all_org_ids:
                                all_org_ids.add(row.parent_id)
                        if not any(
                            row.parent_id and row.parent_id not in org_map
                            for row in rows
                        ):
                            break

            # Per-chunk: load creator names
            chunk_creator_ids = set(
                a.created_by_id for a in assets if a.created_by_id
            )
            if chunk_creator_ids:
                cr = await db.execute(
                    select(User.id, User.username).where(User.id.in_(chunk_creator_ids))
                )
                creator_names.update({row.id: row.username for row in cr})

            # For database assets, load relations per chunk
            if category == "database":
                db_query = (
                    select(Asset)
                    .options(
                        selectinload(Asset.database_hosts)
                        .selectinload(AssetHostRelation.host_asset),
                        selectinload(Asset.storage_locations),
                    )
                    .where(Asset.id.in_([a.id for a in assets]))
                )
                assets = (await db.execute(db_query)).scalars().all()

            for asset in assets:
                credentials = []
                for cred in asset.credentials:
                    if can_export_passwords:
                        try:
                            password_value = decrypt_value(cred.password_encrypted)
                        except Exception:
                            password_value = ""
                    else:
                        password_value = ""
                    credentials.append({"username": cred.username, "password": password_value})

                org_name = build_org_full_path(asset.organization_id, org_map)

                decrypted_oob_password = None
                if can_export_passwords and asset.oob_password_encrypted:
                    try:
                        decrypted_oob_password = decrypt_value(asset.oob_password_encrypted)
                    except Exception:
                        decrypted_oob_password = ""

                yield build_asset_response(
                    asset,
                    org_name=org_name,
                    include_credentials=True,
                    credentials_data=credentials,
                    include_decrypted_passwords=can_export_passwords,
                    oob_password=decrypted_oob_password,
                    creator_name=creator_names.get(asset.created_by_id),
                )

            offset += CHUNK_SIZE

    # Stream to file
    if format == "csv":
        buffer, count = await _export_csv_stream(_asset_data_gen(), export_columns)
        filename = f"资产导出_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        media_type = "text/csv"
    else:
        buffer, count = await _export_excel_stream(_asset_data_gen(), export_columns)
        filename = f"资产导出_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    # Audit log
    await log_operation(
        db=db,
        user_id=current_user.id,
        action="export",
        resource_type="asset",
        resource_id=0,
        details={
            "name": f"export_{export_category or scope}",
            "format": format,
            "scope": scope,
            "category": export_category,
            "count": count,
        },
    )

    return StreamingResponse(
        buffer,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{quote(filename)}"'},
    )


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
 
    # Handle owner validation
    if "owner_id" in update_data or "owner_name" in update_data:
        owner_id = update_data.get("owner_id")
        owner_name = update_data.get("owner_name")

        if owner_id is not None and owner_name is None:
            # Fetch owner name from database
            result = await db.execute(select(User.username).where(User.id == owner_id))
            owner_result = result.scalar_one_or_none()
            if owner_result:
                update_data["owner_name"] = owner_result
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
                update_data["owner_id"] = owner_result
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="负责人不存在"
                )

    # Handle OOB password encryption
    if "oob_password" in update_data and update_data["oob_password"] is not None:
        if update_data["oob_password"]:
            asset.oob_password_encrypted = encrypt_value(update_data["oob_password"])
        else:
            asset.oob_password_encrypted = None
        del update_data["oob_password"]

    # Extract database-specific fields before generic update
    host_ids = update_data.pop("host_ids", None)
    storage_locations_data = update_data.pop("storage_locations", None)

    for field, value in update_data.items():
        # Map schema 'extra_data' to model 'extra_data'
        if field == "extra_data":
            setattr(asset, "extra_data", value)
        else:
            setattr(asset, field, value)
 
    await db.commit()

    # Handle database asset relations (runs_on hosts)
    if host_ids is not None and asset.category == "database":
        # Delete existing relations
        await db.execute(
            delete(AssetHostRelation).where(AssetHostRelation.asset_id == asset_id)
        )
        # Create new relations
        if host_ids:
            for host_id in host_ids:
                host_result = await db.execute(
                    select(Asset).where(Asset.id == host_id, Asset.category == "host")
                )
                host_asset = host_result.scalar_one_or_none()
                if host_asset:
                    relation = AssetHostRelation(asset_id=asset.id, host_id=host_id)
                    db.add(relation)
        await db.commit()

    # Handle storage locations for database assets
    if storage_locations_data is not None and asset.category == "database":
        # Delete existing storage locations
        await db.execute(
            delete(StorageLocation).where(StorageLocation.asset_id == asset_id)
        )
        if storage_locations_data:
            for loc in storage_locations_data:
                if isinstance(loc, dict):
                    storage = StorageLocation(
                        asset_id=asset.id,
                        path=loc.get("path"),
                        path_type=loc.get("path_type"),
                        description=loc.get("description")
                    )
                else:
                    storage = StorageLocation(
                        asset_id=asset.id,
                        path=loc.path,
                        path_type=loc.path_type,
                        description=loc.description
                    )
                db.add(storage)
        await db.commit()

    # Audit log
    await log_operation(
        db, current_user.id, "update", "asset", 0,
        details={
            "name": asset.name,
            "category": asset.category,
            "asset_code": asset.asset_code,
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


# ============== Organization/Asset Tree APIs ==============
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

    return {"code": 0, "data": {"id": org.id, "name": org.name, "path": org.path}}


@org_router.put("/{org_id}")
async def update_organization(
    org_id: int,
    name: str = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("manage")),
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

    if name:
        org.name = name

    await db.commit()
    await db.refresh(org)

    return {"code": 0, "data": {"id": org.id, "name": org.name}}


@org_router.delete("/{org_id}")
async def delete_organization(
    org_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("manage")),
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

    await db.delete(org)
    await db.commit()

    return {"code": 0, "message": "节点已删除"}


# ============== Credential APIs ==============
cred_router = APIRouter(prefix="/credentials", tags=["凭证管理"])


@cred_router.get("")
async def list_credentials(
    asset_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("view_pwd")),
):
    """List credentials for an asset"""
    query = select(Credential)

    if asset_id:
        asset_result = await db.execute(select(Asset).where(Asset.id == asset_id))
        asset = asset_result.scalar_one_or_none()
        if not asset:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="资产不存在",
            )
        await check_resource_permission(
            current_user, "view_pwd", "asset", asset_id, db,
            organization_id=asset.organization_id,
        )
        query = query.where(Credential.asset_id == asset_id)
    else:
        # Filter by authorized assets
        authorized_ids = await get_authorized_asset_ids(current_user, db, "view_pwd")
        if authorized_ids is not None and len(authorized_ids) == 0:
            return {"code": 0, "data": []}
        if authorized_ids is not None:
            query = query.where(Credential.asset_id.in_(authorized_ids))

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
    request: Request,
    data: CredentialCreate,
    asset_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("manage")),
):
    """Create a new credential for an asset"""
    # Verify asset exists
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

    credential = Credential(
        asset_id=asset_id,
        username=data.username,
        password_encrypted=encrypt_value(data.password),
        credential_type=data.credential_type,
        extra_data=data.metadata,
    )
    db.add(credential)
    await db.flush()  # Get credential.id before committing

    # Log credential creation
    password_log = PasswordChangeLog(
        credential_id=credential.id,
        change_type="asset_credential",
        changed_by=current_user.id,
        ip_address=request.client.host if request.client else None,
    )
    db.add(password_log)

    await db.commit()
    await db.refresh(credential)

    return CredentialResponse(
        id=credential.id,
        asset_id=credential.asset_id,
        username=credential.username,
        credential_type=credential.credential_type,
        created_at=credential.created_at,
    )


class OOBDecryptResponse(BaseModel):
    """OOB password decrypt response"""
    oob_password: str



@router.post("/{asset_id}/decrypt-oob", response_model=OOBDecryptResponse)
async def decrypt_oob_password(
    asset_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("view_pwd")),
):
    """Decrypt OOB password for host asset (requires view_pwd permission)"""
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
        current_user, "view_pwd", "asset", asset_id, db,
        organization_id=asset.organization_id,
    )

    # Check new column first, fallback to extra_data for backward compatibility
    oob_password_value = asset.oob_password_encrypted
    source = "column"

    if not oob_password_value and asset.extra_data:
        oob_password_value = asset.extra_data.get("oob_password")
        source = "metadata"

    if not oob_password_value:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="未找到 OOB 密码"
        )

    # Check if value is encrypted (Fernet encrypted strings start with 'gAAAA')
    is_encrypted = oob_password_value.startswith('gAAAA') if oob_password_value else False

    try:
        if is_encrypted:
            decrypted_password = decrypt_value(oob_password_value)
        else:
            # Password is in plaintext (legacy data from metadata), return as-is
            # and migrate to encrypted column for security
            decrypted_password = oob_password_value

            # Migrate plaintext to encrypted column
            if source == "metadata" and not asset.oob_password_encrypted:
                from app.core.encryption import encrypt_value
                encrypted = encrypt_value(oob_password_value)
                asset.oob_password_encrypted = encrypted
                await db.flush()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="解密失败"
        )

    return OOBDecryptResponse(oob_password=decrypted_password)


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

    asset_result = await db.execute(select(Asset).where(Asset.id == credential.asset_id))
    asset = asset_result.scalar_one_or_none()

    # Check resource-level permission on the asset
    await check_resource_permission(
        current_user, "view_pwd", "asset", credential.asset_id, db,
        organization_id=asset.organization_id if asset else None,
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
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("manage")),
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

    asset_result = await db.execute(select(Asset).where(Asset.id == credential.asset_id))
    asset = asset_result.scalar_one_or_none()

    # Check resource-level permission on the asset
    await check_resource_permission(
        current_user, "manage", "asset", credential.asset_id, db,
        organization_id=asset.organization_id if asset else None,
    )

    # Update fields
    if data.username is not None:
        credential.username = data.username
    if data.password is not None:
        credential.password_encrypted = encrypt_value(data.password)

        # Log credential password change
        password_log = PasswordChangeLog(
            credential_id=credential_id,
            change_type="asset_credential",
            changed_by=current_user.id,
            ip_address=request.client.host if request.client else None,
        )
        db.add(password_log)
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
    current_user: User = Depends(PermissionChecker("manage")),
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

    asset_result = await db.execute(select(Asset).where(Asset.id == credential.asset_id))
    asset = asset_result.scalar_one_or_none()

    # Check resource-level permission on the asset
    await check_resource_permission(
        current_user, "manage", "asset", credential.asset_id, db,
        organization_id=asset.organization_id if asset else None,
    )

    await db.delete(credential)
    await db.commit()

    return ResponseBase(message="凭证已删除")

