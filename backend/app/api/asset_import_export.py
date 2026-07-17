"""
Asset Import/Export API
XLSX bulk import (with per-category templates) and Excel/CSV export with
chunked streaming.
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
from urllib.parse import quote
from fastapi import Depends, HTTPException, status, Query, Request, File, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import Asset, Organization, User, AssetHostRelation
from app.schemas import ResponseBase
from app.api.deps import get_user_permissions, PermissionChecker, check_resource_permission, get_authorized_asset_ids
from app.api.assets import (
    router,
    build_asset_response,
    apply_search_filter,
    get_descendant_org_ids,
    _client_ip,
    _export_target_name,
)
from app.core.encryption import decrypt_value
from app.core.asset_categories import asset_category_label
from app.services.import_service import (
    parse_import_file,
    batch_create_assets,
    batch_update_assets,
    get_created_orgs,
)
from app.services.template_service import (
    generate_category_template,
    CATEGORY_FIELDS,
)
from app.services.export_service import (
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


# ============== Import APIs ==============
@router.get("/import/template/{category}")
async def download_import_template(
    category: str,
    mode: str = Query("create", description="create or update"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("manage")),
    request: Request = None,
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
    category_label = asset_category_label(category)
    mode_label = "创建" if mode == "create" else "更新"
    await log_operation(
        db=db,
        user_id=current_user.id,
        action="download",
        resource_type="asset",
        resource_id=0,
        details={
            "name": f"{category_label}资产导入模板",
            "target_name": f"{category_label}资产",
            "action": "download_import_template",
            "category": category,
            "category_label": category_label,
            "mode": mode,
            "mode_label": mode_label,
            "filename": filename,
        },
        ip_address=_client_ip(request),
    )
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
    request: Request = None,
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
                "name": f"{asset_category_label(category)}资产",
                "target_name": f"{asset_category_label(category)}资产",
                "action": "import_assets",
                "category": category,
                "category_label": asset_category_label(category),
                "mode": mode,
                "total_rows": len(valid_records) + len(parse_errors),
                "success_count": success_count,
                "failed_count": len(all_errors),
                "created_orgs": list(created_orgs) if created_orgs else None,
            },
            ip_address=_client_ip(request),
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
    request: Request = None,
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
        if "export_pwd" not in permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="导出密码需要 'export_pwd' 权限",
            )
        password_authorized_ids = await get_authorized_asset_ids(current_user, db, "export_pwd")
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
    export_target_name = _export_target_name(scope, export_category, organization_id, search)
    await log_operation(
        db=db,
        user_id=current_user.id,
        action="export",
        resource_type="asset",
        resource_id=0,
        details={
            "name": export_target_name,
            "target_name": export_target_name,
            "action": "export_assets",
            "format": format,
            "scope": scope,
            "category": export_category,
            "category_label": asset_category_label(export_category) if export_category else None,
            "organization_id": organization_id,
            "search": search,
            "include_passwords": can_export_passwords,
            "count": count,
        },
        ip_address=_client_ip(request),
    )

    return StreamingResponse(
        buffer,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{quote(filename)}"'},
    )
