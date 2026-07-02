"""
Settings API Routes
"""
from datetime import datetime, timezone
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.api.deps import PermissionChecker
from app.utils.audit import log_operation
from app.models import Setting, User


def format_datetime_utc(dt: datetime | None) -> str | None:
    """Format datetime as ISO 8601 with Z suffix for UTC"""
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc).isoformat().replace('+00:00', 'Z')


router = APIRouter(prefix="/settings", tags=["Settings"])


PUBLIC_BRANDING_KEYS = {"site_title", "login_subtitle", "logo_image", "login_background_image", "copyright_text", "beian_number", "beian_url"}


@router.get("")
async def get_settings(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("sys_config")),
) -> Dict[str, Any]:
    """
    Get all settings
    Requires sys_config permission
    """
    result = await db.execute(select(Setting))
    settings_list = result.scalars().all()

    # Convert to dictionary format
    settings_dict = {}
    for setting in settings_list:
        settings_dict[setting.key] = setting.value.get("value") if setting.value else None

    return {
        "code": 0,
        "message": "success",
        "data": settings_dict,
        "raw": [{"id": s.id, "key": s.key, "value": s.value, "description": s.description, "updated_at": format_datetime_utc(s.updated_at)} for s in settings_list]
    }


@router.get("/public")
async def get_public_settings(
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Get public branding settings (no authentication required)
    Used by the login page to display dynamic branding
    """
    result = await db.execute(select(Setting))
    settings_list = result.scalars().all()

    settings_dict = {}
    for setting in settings_list:
        if setting.key in PUBLIC_BRANDING_KEYS:
            settings_dict[setting.key] = setting.value.get("value") if setting.value else None

    return {
        "code": 0,
        "message": "success",
        "data": settings_dict,
    }


@router.get("/{key}")
async def get_setting(
    key: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("sys_config")),
) -> Dict[str, Any]:
    """
    Get a single setting by key
    Requires sys_config permission
    """
    result = await db.execute(select(Setting).where(Setting.key == key))
    setting = result.scalar_one_or_none()

    if not setting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Setting '{key}' not found"
        )

    return {
        "data": {
            "id": setting.id,
            "key": setting.key,
            "value": setting.value,
            "description": setting.description,
            "updated_at": format_datetime_utc(setting.updated_at)
        }
    }


@router.put("/{key}")
async def update_setting(
    key: str,
    value: Dict[str, Any],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("sys_config")),
    request: Request = None,
) -> Dict[str, Any]:
    """
    Update a single setting
    Requires sys_config permission
    """
    ip = request.client.host if request and request.client else None
    result = await db.execute(select(Setting).where(Setting.key == key))
    setting = result.scalar_one_or_none()

    if not setting:
        # Create new setting if it doesn't exist
        setting = Setting(key=key, value=value)
        db.add(setting)
    else:
        setting.value = value

    await db.commit()
    await db.refresh(setting)

    # Audit log
    await log_operation(
        db, current_user.id, "update", "setting", 0,
        details={
            "name": key,
            "value": value,
        },
        ip_address=ip,
    )

    return {
        "data": {
            "id": setting.id,
            "key": setting.key,
            "value": setting.value,
            "description": setting.description,
            "updated_at": format_datetime_utc(setting.updated_at)
        }
    }


@router.put("")
async def update_settings(
    settings_data: Dict[str, Any],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("sys_config")),
    request: Request = None,
) -> Dict[str, Any]:
    """
    Update multiple settings at once. Creates missing settings if needed.
    Requires sys_config permission
    """
    ip = request.client.host if request and request.client else None
    updated = []

    for key, value in settings_data.items():
        result = await db.execute(select(Setting).where(Setting.key == key))
        setting = result.scalar_one_or_none()

        if setting:
            setting.value = {"value": value}
        else:
            setting = Setting(key=key, value={"value": value})
            db.add(setting)
        updated.append(key)

    await db.commit()

    # Audit log
    await log_operation(
        db, current_user.id, "update", "setting", 0,
        details={
            "name": "batch_update",
            "keys": updated,
        },
        ip_address=ip,
    )

    return {
        "data": {
            "updated": updated,
            "message": f"Updated {len(updated)} settings"
        }
    }