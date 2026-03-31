"""
Settings API Routes
"""
from datetime import datetime, timezone
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.api.deps import get_current_superuser
from app.models import Setting, User


def format_datetime_utc(dt: datetime | None) -> str | None:
    """Format datetime as ISO 8601 with Z suffix for UTC"""
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc).isoformat().replace('+00:00', 'Z')


router = APIRouter(prefix="/settings", tags=["Settings"])


@router.get("")
async def get_settings(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
) -> Dict[str, Any]:
    """
    Get all settings
    Requires superuser permission
    """
    result = await db.execute(select(Setting))
    settings = result.scalars().all()

    # Convert to dictionary format
    settings_dict = {}
    for setting in settings:
        settings_dict[setting.key] = setting.value.get("value") if setting.value else None

    return {
        "code": 0,
        "message": "success",
        "data": settings_dict,
        "raw": [{"id": s.id, "key": s.key, "value": s.value, "description": s.description, "updated_at": format_datetime_utc(s.updated_at)} for s in settings]
    }


@router.get("/{key}")
async def get_setting(
    key: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
) -> Dict[str, Any]:
    """
    Get a single setting by key
    Requires superuser permission
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
    current_user: User = Depends(get_current_superuser),
) -> Dict[str, Any]:
    """
    Update a single setting
    Requires superuser permission
    """
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
    current_user: User = Depends(get_current_superuser),
) -> Dict[str, Any]:
    """
    Update multiple settings at once
    Requires superuser permission
    """
    updated = []

    for key, value in settings_data.items():
        result = await db.execute(select(Setting).where(Setting.key == key))
        setting = result.scalar_one_or_none()

        if setting:
            setting.value = {"value": value}
            updated.append(key)

    await db.commit()

    return {
        "data": {
            "updated": updated,
            "message": f"Updated {len(updated)} settings"
        }
    }