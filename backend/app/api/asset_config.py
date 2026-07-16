"""
Network Device Config File API
Version-controlled configuration file storage for network-device assets:
metadata, content view/edit, download, version history, upload, rollback, delete.
"""
from urllib.parse import quote
from io import BytesIO
from pathlib import Path
import hashlib
from fastapi import Depends, HTTPException, status, Request, File, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import get_db
from app.models import Asset, User, AssetConfigFile, AssetConfigVersion
from app.api.deps import get_user_permissions, PermissionChecker, check_resource_permission
from app.api.assets import router
from app.core.encryption import encrypt_value, decrypt_value
from app.utils.audit import log_operation


class AssetConfigContentSave(BaseModel):
    filename: Optional[str] = None
    content: str
    change_summary: Optional[str] = None


class AssetConfigRollback(BaseModel):
    version_id: int
    change_summary: Optional[str] = None


ALLOWED_CONFIG_EXTENSIONS = {".cfg", ".conf"}
MAX_CONFIG_FILE_SIZE = 2 * 1024 * 1024


def _config_filename(filename: str | None) -> str:
    clean = Path(filename or "").name.strip()
    if not clean or clean != (filename or "").strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="配置文件名非法")
    if len(clean) > 255:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="配置文件名不能超过255个字符")
    ext = Path(clean).suffix.lower()
    if ext not in ALLOWED_CONFIG_EXTENSIONS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="仅支持 .cfg 和 .conf 配置文件")
    return clean


def _decode_config_content(content: bytes) -> str:
    if len(content) > MAX_CONFIG_FILE_SIZE:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="配置文件不能超过2MB")
    for encoding in ("utf-8-sig", "utf-8", "gbk"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="配置文件必须是 UTF-8 或 GBK 文本")


def _content_checksum(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


async def _get_network_asset_or_404(db: AsyncSession, asset_id: str, current_user: User, permission: str = "view") -> Asset:
    result = await db.execute(select(Asset).where(Asset.id == asset_id))
    asset = result.scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="资产不存在")
    if asset.category != "network":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="仅网络设备支持配置文件")
    await check_resource_permission(
        current_user, permission, "asset", asset_id, db,
        organization_id=asset.organization_id,
    )
    return asset


async def _can_manage_asset(current_user: User, asset: Asset, db: AsyncSession) -> bool:
    try:
        await check_resource_permission(
            current_user, "manage", "asset", str(asset.id), db,
            organization_id=asset.organization_id,
        )
        return True
    except HTTPException:
        return False


async def _can_view_config_content(current_user: User, asset: Asset, db: AsyncSession) -> bool:
    if await _can_manage_asset(current_user, asset, db):
        return True
    permissions = await get_user_permissions(current_user, db)
    return "view_pwd" in permissions


async def _get_config_file(db: AsyncSession, asset_id: str) -> AssetConfigFile | None:
    result = await db.execute(select(AssetConfigFile).where(AssetConfigFile.asset_id == asset_id))
    return result.scalar_one_or_none()


async def _get_current_config_version(db: AsyncSession, config_file: AssetConfigFile) -> AssetConfigVersion | None:
    if config_file.current_version_id:
        result = await db.execute(select(AssetConfigVersion).where(AssetConfigVersion.id == config_file.current_version_id))
        version = result.scalar_one_or_none()
        if version:
            return version
    result = await db.execute(
        select(AssetConfigVersion)
        .where(AssetConfigVersion.config_file_id == config_file.id)
        .order_by(AssetConfigVersion.version_no.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _next_config_version_no(db: AsyncSession, config_file_id: int) -> int:
    result = await db.execute(
        select(func.max(AssetConfigVersion.version_no)).where(AssetConfigVersion.config_file_id == config_file_id)
    )
    return int(result.scalar() or 0) + 1


async def _create_config_version(
    db: AsyncSession,
    config_file: AssetConfigFile,
    filename: str,
    content: str,
    user_id: int,
    change_summary: str | None,
    force_new: bool = False,
) -> tuple[AssetConfigVersion, bool]:
    checksum = _content_checksum(content)
    current = await _get_current_config_version(db, config_file)
    if not force_new and current and current.checksum == checksum and current.filename == filename:
        return current, False

    version = AssetConfigVersion(
        config_file_id=config_file.id,
        version_no=await _next_config_version_no(db, config_file.id),
        filename=filename,
        content_encrypted=encrypt_value(content),
        size=len(content.encode("utf-8")),
        checksum=checksum,
        change_summary=(change_summary or "").strip()[:255] or None,
        created_by=user_id,
    )
    db.add(version)
    await db.flush()
    config_file.filename = filename
    config_file.current_version_id = version.id
    config_file.updated_by = user_id
    return version, True


def _config_meta(config_file: AssetConfigFile | None, version: AssetConfigVersion | None, can_view: bool, can_edit: bool) -> dict:
    return {
        "id": config_file.id if config_file else None,
        "filename": config_file.filename if config_file else None,
        "current_version_id": config_file.current_version_id if config_file else None,
        "version_no": version.version_no if version else None,
        "size": version.size if version else None,
        "checksum": version.checksum if version else None,
        "updated_at": config_file.updated_at.isoformat() if config_file and config_file.updated_at else None,
        "can_view": can_view,
        "can_edit": can_edit,
    }


@router.get("/{asset_id}/config")
async def get_asset_config_meta(
    asset_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("view")),
):
    asset = await _get_network_asset_or_404(db, asset_id, current_user, "view")
    config_file = await _get_config_file(db, asset_id)
    version = await _get_current_config_version(db, config_file) if config_file else None
    can_edit = await _can_manage_asset(current_user, asset, db)
    can_view = can_edit or await _can_view_config_content(current_user, asset, db)
    return {"code": 0, "message": "success", "data": _config_meta(config_file, version, can_view, can_edit)}


@router.get("/{asset_id}/config/content")
async def get_asset_config_content(
    asset_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("view")),
):
    asset = await _get_network_asset_or_404(db, asset_id, current_user, "view")
    if not await _can_view_config_content(current_user, asset, db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="缺少查看配置文件权限")
    config_file = await _get_config_file(db, asset_id)
    if not config_file:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="配置文件不存在")
    version = await _get_current_config_version(db, config_file)
    if not version:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="配置版本不存在")
    return {
        "code": 0,
        "message": "success",
        "data": {
            **_config_meta(config_file, version, True, await _can_manage_asset(current_user, asset, db)),
            "content": decrypt_value(version.content_encrypted),
        },
    }


@router.get("/{asset_id}/config/download")
async def download_asset_config(
    asset_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("view")),
):
    asset = await _get_network_asset_or_404(db, asset_id, current_user, "view")
    if not await _can_view_config_content(current_user, asset, db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="缺少查看配置文件权限")
    config_file = await _get_config_file(db, asset_id)
    if not config_file:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="配置文件不存在")
    version = await _get_current_config_version(db, config_file)
    if not version:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="配置版本不存在")

    filename = version.filename or config_file.filename
    content = decrypt_value(version.content_encrypted)
    await log_operation(
        db, current_user.id, "download", "asset", 0,
        details={
            "name": f"{asset.name} / {filename}",
            "action": "download_config",
            "asset_id": asset_id,
            "asset_name": asset.name,
            "filename": filename,
            "version_no": version.version_no,
            "checksum": version.checksum,
            "size": version.size,
        },
        ip_address=request.client.host if request.client else None,
    )

    return StreamingResponse(
        BytesIO(content.encode("utf-8")),
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{quote(filename)}"'},
    )


@router.get("/{asset_id}/config/versions")
async def list_asset_config_versions(
    asset_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("view")),
):
    asset = await _get_network_asset_or_404(db, asset_id, current_user, "view")
    if not await _can_view_config_content(current_user, asset, db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="缺少查看配置文件权限")
    config_file = await _get_config_file(db, asset_id)
    if not config_file:
        return {"code": 0, "message": "success", "data": []}
    result = await db.execute(
        select(AssetConfigVersion, User.username)
        .outerjoin(User, User.id == AssetConfigVersion.created_by)
        .where(AssetConfigVersion.config_file_id == config_file.id)
        .order_by(AssetConfigVersion.version_no.desc())
    )
    data = []
    for version, username in result.all():
        data.append({
            "id": version.id,
            "version_no": version.version_no,
            "filename": version.filename,
            "size": version.size,
            "checksum": version.checksum,
            "change_summary": version.change_summary,
            "created_by": version.created_by,
            "created_by_username": username,
            "created_at": version.created_at.isoformat() if version.created_at else None,
            "is_current": version.id == config_file.current_version_id,
        })
    return {"code": 0, "message": "success", "data": data}


@router.get("/{asset_id}/config/versions/{version_id}")
async def get_asset_config_version_content(
    asset_id: str,
    version_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("view")),
):
    asset = await _get_network_asset_or_404(db, asset_id, current_user, "view")
    if not await _can_view_config_content(current_user, asset, db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="缺少查看配置文件权限")
    config_file = await _get_config_file(db, asset_id)
    if not config_file:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="配置文件不存在")
    result = await db.execute(
        select(AssetConfigVersion).where(
            AssetConfigVersion.id == version_id,
            AssetConfigVersion.config_file_id == config_file.id,
        )
    )
    version = result.scalar_one_or_none()
    if not version:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="配置版本不存在")
    return {
        "code": 0,
        "message": "success",
        "data": {
            "id": version.id,
            "version_no": version.version_no,
            "filename": version.filename,
            "size": version.size,
            "checksum": version.checksum,
            "change_summary": version.change_summary,
            "created_by": version.created_by,
            "created_at": version.created_at.isoformat() if version.created_at else None,
            "content": decrypt_value(version.content_encrypted),
            "is_current": version.id == config_file.current_version_id,
        },
    }


@router.post("/{asset_id}/config/upload")
async def upload_asset_config_file(
    asset_id: str,
    request: Request,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("manage")),
):
    asset = await _get_network_asset_or_404(db, asset_id, current_user, "manage")
    filename = _config_filename(file.filename)
    content = _decode_config_content(await file.read())
    config_file = await _get_config_file(db, asset_id)
    if not config_file:
        config_file = AssetConfigFile(asset_id=asset_id, filename=filename, created_by=current_user.id, updated_by=current_user.id)
        db.add(config_file)
        await db.flush()
    version, created = await _create_config_version(db, config_file, filename, content, current_user.id, "上传配置文件")
    await db.commit()
    await log_operation(
        db, current_user.id, "update", "asset", 0,
        details={
            "name": f"{asset.name} / {filename}",
            "action": "upload_config",
            "asset_id": asset_id,
            "asset_name": asset.name,
            "filename": filename,
            "version_no": version.version_no,
            "checksum": version.checksum,
            "size": version.size,
            "changed": created,
        },
        ip_address=request.client.host if request.client else None,
    )
    return {"code": 0, "message": "配置文件已上传" if created else "配置内容未变化", "data": _config_meta(config_file, version, True, True)}


@router.put("/{asset_id}/config/content")
async def save_asset_config_content(
    asset_id: str,
    data: AssetConfigContentSave,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("manage")),
):
    asset = await _get_network_asset_or_404(db, asset_id, current_user, "manage")
    if len(data.content.encode("utf-8")) > MAX_CONFIG_FILE_SIZE:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="配置文件不能超过2MB")
    config_file = await _get_config_file(db, asset_id)
    filename = _config_filename(data.filename or (config_file.filename if config_file else None))
    if not config_file:
        config_file = AssetConfigFile(asset_id=asset_id, filename=filename, created_by=current_user.id, updated_by=current_user.id)
        db.add(config_file)
        await db.flush()
    version, created = await _create_config_version(db, config_file, filename, data.content, current_user.id, data.change_summary or "编辑保存")
    await db.commit()
    await log_operation(
        db, current_user.id, "update", "asset", 0,
        details={
            "name": f"{asset.name} / {filename}",
            "action": "save_config",
            "asset_id": asset_id,
            "asset_name": asset.name,
            "filename": filename,
            "version_no": version.version_no,
            "checksum": version.checksum,
            "size": version.size,
            "changed": created,
        },
        ip_address=request.client.host if request.client else None,
    )
    return {"code": 0, "message": "配置已保存" if created else "配置内容未变化", "data": _config_meta(config_file, version, True, True)}


@router.post("/{asset_id}/config/rollback")
async def rollback_asset_config(
    asset_id: str,
    data: AssetConfigRollback,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("manage")),
):
    asset = await _get_network_asset_or_404(db, asset_id, current_user, "manage")
    config_file = await _get_config_file(db, asset_id)
    if not config_file:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="配置文件不存在")
    result = await db.execute(
        select(AssetConfigVersion).where(
            AssetConfigVersion.id == data.version_id,
            AssetConfigVersion.config_file_id == config_file.id,
        )
    )
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="配置版本不存在")
    content = decrypt_value(target.content_encrypted)
    version, created = await _create_config_version(
        db,
        config_file,
        target.filename,
        content,
        current_user.id,
        data.change_summary or f"回滚到版本 {target.version_no}",
        force_new=True,
    )
    await db.commit()
    await log_operation(
        db, current_user.id, "update", "asset", 0,
        details={
            "name": f"{asset.name} / {version.filename}",
            "action": "rollback_config",
            "asset_id": asset_id,
            "asset_name": asset.name,
            "filename": version.filename,
            "from_version_no": target.version_no,
            "version_no": version.version_no,
            "checksum": version.checksum,
            "size": version.size,
            "changed": created,
        },
        ip_address=request.client.host if request.client else None,
    )
    return {"code": 0, "message": "已回滚配置" if created else "目标版本与当前配置相同", "data": _config_meta(config_file, version, True, True)}


@router.delete("/{asset_id}/config")
async def delete_asset_config(
    asset_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("manage")),
):
    asset = await _get_network_asset_or_404(db, asset_id, current_user, "manage")
    config_file = await _get_config_file(db, asset_id)
    if not config_file:
        return {"code": 0, "message": "配置文件不存在", "data": {"deleted": False}}
    filename = config_file.filename
    await db.delete(config_file)
    await db.commit()
    await log_operation(
        db, current_user.id, "delete", "asset", 0,
        details={
            "name": f"{asset.name} / {filename}",
            "action": "delete_config",
            "asset_id": asset_id,
            "asset_name": asset.name,
            "filename": filename,
        },
        ip_address=request.client.host if request.client else None,
    )
    return {"code": 0, "message": "配置文件已删除", "data": {"deleted": True}}
