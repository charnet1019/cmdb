"""
Asset Management API
CRUD, listing, statistics, and bulk operations for assets.

Related asset sub-domains live in sibling modules that import the shared
`router` and helpers defined here:
  - app.api.asset_config: network-device config file version management
  - app.api.asset_import_export: XLSX import and Excel/CSV export
  - app.api.organizations: organization tree CRUD (org_router)
  - app.api.credentials: per-asset credential CRUD + decrypt (cred_router)
"""
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, delete, inspect, false
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import Asset, Authorization, Organization, User, AssetHostRelation, StorageLocation
from app.schemas import AssetCreate, ResponseBase, BulkUpdateRequest, BulkDeleteRequest
from app.api.deps import PermissionChecker, check_resource_permission, get_authorized_asset_ids
from app.core.encryption import encrypt_value
from app.core.asset_categories import asset_category_label
from app.utils.audit import log_operation
from app.utils.authorization_cleanup import cleanup_authorization_targets
from app.utils.pagination import get_pagination_meta


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

# Fields on AssetCreate/AssetUpdate that only make sense for specific asset
# categories. Used to reject e.g. a "web" asset silently storing network
# hardware fields (device_type/vendor/...) with no validation error.
CATEGORY_ONLY_FIELDS: Dict[str, set] = {
    "host": {
        "cpu", "memory", "system_disk", "data_disk", "model", "serial_number", "vendor",
        "oob_address", "oob_username", "oob_password",
    },
    "network": {"device_type", "vendor", "model", "serial_number"},
    "database": {"db_type", "namespace", "host_ids", "storage_locations"},
    "cloud": set(),
    "web": set(),
    "gpt": set(),
}

# The union of every category-restricted field above — anything in this set
# that isn't in the target category's own allowed set is out of place.
_ALL_CATEGORY_RESTRICTED_FIELDS: set = set().union(*CATEGORY_ONLY_FIELDS.values())


def _validate_category_fields(category: str, fields: Dict[str, Any]) -> None:
    """Reject category-specific fields (network/host hardware fields, OOB
    fields, database runs_on/storage_locations) that don't belong to `category`.

    Only flags fields with a truthy value — an unset/None/empty field is not
    an error, since schemas share these fields across all categories.
    """
    allowed = CATEGORY_ONLY_FIELDS.get(category, set())
    invalid = sorted(
        field for field in _ALL_CATEGORY_RESTRICTED_FIELDS - allowed
        if fields.get(field)
    )
    if invalid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"字段 {', '.join(invalid)} 不适用于{asset_category_label(category)}类型资产",
        )

# Common fields for all asset types
COMMON_FIELDS = [
    "id", "name", "asset_code", "category", "internal_address",
    "external_address", "platform", "organization_id", "organization_name",
    "notes", "extra_data", "created_at", "updated_at",
    "applicant", "credentials"
]


def _client_ip(request: Request | None) -> Optional[str]:
    return request.client.host if request and request.client else None



def _export_target_name(scope: str, category: Optional[str], organization_id: Optional[int], search: Optional[str]) -> str:
    if category:
        return f"{asset_category_label(category)}资产"
    if scope == "selected":
        return "选中资产"
    if scope == "filtered" or search or organization_id is not None:
        return "筛选资产"
    return "全部资产"


def _storage_location_items(locations) -> list[dict[str, Any]]:
    items = []
    for loc in locations or []:
        if isinstance(loc, dict):
            items.append({
                "path": loc.get("path"),
                "path_type": loc.get("path_type"),
                "description": loc.get("description"),
            })
        else:
            items.append({
                "path": loc.path,
                "path_type": loc.path_type,
                "description": loc.description,
            })
    return items


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
    if asset.oob_password_encrypted:
        data["has_oob_password"] = True
    if oob_password is not None:
        data["oob_password"] = oob_password
    if asset.status:
        data["status"] = asset.status
    if asset.category == "network":
        unloaded = inspect(asset).unloaded
        if "config_file" not in unloaded and asset.config_file:
            data["config_file"] = {
                "id": asset.config_file.id,
                "filename": asset.config_file.filename,
                "current_version_id": asset.config_file.current_version_id,
                "updated_at": asset.config_file.updated_at.isoformat() if asset.config_file.updated_at else None,
            }
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


def _encrypt_oob_password(value: Optional[str]) -> Optional[str]:
    """Encrypt a plaintext OOB password, or clear it: an empty/None value
    means "no password" and must never be encrypted into a non-empty ciphertext."""
    return encrypt_value(value) if value else None


async def _sync_host_relations(db: AsyncSession, asset_id: str, host_ids: Optional[List[str]], *, replace: bool = False) -> None:
    """Create AssetHostRelation rows linking a database asset to its runs_on hosts.

    If replace=True, existing relations are deleted first — used by update_asset,
    where an empty host_ids list means "clear all relations" rather than "no change".
    """
    if replace:
        await db.execute(delete(AssetHostRelation).where(AssetHostRelation.asset_id == asset_id))
    for host_id in host_ids or []:
        # Validate host exists and is category='host'
        host_result = await db.execute(
            select(Asset).where(Asset.id == host_id, Asset.category == "host")
        )
        if host_result.scalar_one_or_none():
            db.add(AssetHostRelation(asset_id=asset_id, host_id=host_id))
    await db.commit()


async def _sync_storage_locations(db: AsyncSession, asset_id: str, locations, *, replace: bool = False) -> None:
    """Create StorageLocation rows for a database asset.

    Accepts either StorageLocationCreate-like objects (attribute access) or
    plain dicts (as produced by Pydantic's model_dump()) — update_asset's
    update_data always carries dicts, while create_asset's schema objects
    still carry the original Pydantic models.

    If replace=True, existing storage locations are deleted first — used by
    update_asset, where an empty list means "clear all" rather than "no change".
    """
    if replace:
        await db.execute(delete(StorageLocation).where(StorageLocation.asset_id == asset_id))
    for loc in locations or []:
        if isinstance(loc, dict):
            path, path_type, description = loc.get("path"), loc.get("path_type"), loc.get("description")
        else:
            path, path_type, description = loc.path, loc.path_type, loc.description
        db.add(StorageLocation(asset_id=asset_id, path=path, path_type=path_type, description=description))
    await db.commit()


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
        selectinload(Asset.config_file),
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

    meta = await get_pagination_meta(db, query, page, limit)

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

    return {
        "code": 0,
        "message": "success",
        "data": asset_responses,
        "meta": meta.model_dump(),
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

    _validate_category_fields(data.category, data.model_dump(exclude_unset=True))

    # Resolve owner info. owner_name is free text (not required to match a
    # real user account) — owner_id is only set as a best-effort link when
    # the text happens to match an existing username.
    owner_id = data.owner_id
    owner_name = data.owner_name
    if owner_id is not None and owner_name is None:
        result = await db.execute(select(User.username).where(User.id == owner_id))
        owner_name = result.scalar_one_or_none()
    elif owner_name is not None and owner_id is None:
        result = await db.execute(select(User.id, User.username).where(User.username == owner_name))
        owner_result = result.first()
        if owner_result:
            owner_id = owner_result[0]

    # Encrypt OOB password if provided
    oob_password_encrypted = _encrypt_oob_password(data.oob_password)

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
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="资产编号已存在")
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
        # Only reuse an existing asset-level "manage" authorization that is permanent
        # (no valid_from/valid_until window). Appending the new asset into a
        # time-boxed authorization would silently inherit an unrelated expiry —
        # either locking the creator out early or granting access past its intended window.
        existing = await db.execute(
            select(Authorization)
            .where(Authorization.entity_type == "user")
            .where(Authorization.entity_id == current_user.id)
            .where(Authorization.target_type == "asset")
            .where(Authorization.is_active == True)
            .where(Authorization.permissions.contains(["manage"]))
            .where(Authorization.valid_from.is_(None))
            .where(Authorization.valid_until.is_(None))
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

    # Handle database asset relations (runs_on hosts) and storage locations
    if data.category == "database":
        if data.host_ids:
            await _sync_host_relations(db, asset.id, data.host_ids)
        if data.storage_locations:
            await _sync_storage_locations(db, asset.id, data.storage_locations)

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
    fetched_assets = result.scalars().all()

    # This endpoint only supports bulk status changes (activate/deactivate).
    # Reject unsupported keys instead of silently dropping them — a caller
    # asking to bulk-set organization_id/owner_id etc. would otherwise get a
    # 200 "success" response with nothing actually changed.
    unsupported_keys = set(body.data.keys()) - {"status"}
    if unsupported_keys:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"批量操作不支持以下字段: {', '.join(sorted(unsupported_keys))}",
        )
    if "status" not in body.data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请提供要更新的字段",
        )

    # Silently drop IDs the caller isn't authorized for, the same way
    # nonexistent IDs are silently dropped — treating "exists but forbidden"
    # differently from "doesn't exist" would let a caller enumerate real
    # asset IDs by comparing 403 vs. "excluded from the batch" responses.
    assets = []
    for asset in fetched_assets:
        try:
            await check_resource_permission(
                current_user, "manage", "asset", asset.id, db,
                organization_id=asset.organization_id,
            )
            assets.append(asset)
        except HTTPException:
            continue

    if not assets:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="未找到任何资产"
        )

    # Update each asset
    for asset in assets:
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
    fetched_assets = result.scalars().all()

    # Silently drop IDs the caller isn't authorized for, the same way
    # nonexistent IDs are silently dropped — treating "exists but forbidden"
    # differently from "doesn't exist" would let a caller enumerate real
    # asset IDs by comparing 403 vs. "excluded from the batch" responses.
    assets = []
    for asset in fetched_assets:
        try:
            await check_resource_permission(
                current_user, "manage", "asset", asset.id, db,
                organization_id=asset.organization_id,
            )
            assets.append(asset)
        except HTTPException:
            continue

    if not assets:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="未找到任何资产"
        )

    # Remove dangling references from authorizations that target these assets
    await cleanup_authorization_targets(db, "asset", [a.id for a in assets])

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


# get_asset / update_asset / delete_asset (the /{asset_id} wildcard routes)
# live in app.api.asset_detail, imported last in app/api/__init__.py so
# they're registered after every fixed-path route (/stats, /bulk, /export,
# /import/..., /{asset_id}/config/...). See that module's docstring for why
# the import order matters.
