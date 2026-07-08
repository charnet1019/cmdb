"""
Settings API Routes
"""
from datetime import datetime, timezone
from typing import Dict, Any
from urllib.parse import urlparse
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

SETTING_SCHEMA: Dict[str, tuple[type, int | None]] = {
    "site_title": (str, 100),
    "site_logo": (str, 500),
    "copyright_text": (str, 500),
    "beian_number": (str, 100),
    "beian_url": (str, 500),
    "login_log_retention": (int, None),
    "operation_log_retention": (int, None),
    "password_log_retention": (int, None),
    "password_min_length": (int, None),
    "password_require_uppercase": (bool, None),
    "password_require_lowercase": (bool, None),
    "password_require_digit": (bool, None),
    "password_require_special": (bool, None),
    "max_login_attempts": (int, None),
    "lockout_duration": (int, None),
    "session_timeout": (int, None),
    "otp_issuer_name": (str, 100),
    "login_subtitle": (str, 200),
    "logo_image": (str, 500),
    "login_background_image": (str, 500),
}

INT_RANGES = {
    "login_log_retention": (1, 3650),
    "operation_log_retention": (1, 3650),
    "password_log_retention": (1, 3650),
    "password_min_length": (8, 128),
    "max_login_attempts": (1, 50),
    "lockout_duration": (1, 1440),
    "session_timeout": (1, 10080),
}

URL_KEYS = {"beian_url", "site_logo", "logo_image", "login_background_image"}
SENSITIVE_SETTING_KEY_PARTS = ("secret", "token", "credential", "private_key", "api_key", "smtp_password")


def _audit_setting_value(key: str, value: Any) -> Any:
    lowered = key.lower()
    if any(part in lowered for part in SENSITIVE_SETTING_KEY_PARTS):
        return "<redacted>"
    return value


def _validate_url(key: str, value: str) -> str:
    if not value:
        return value
    parsed = urlparse(value)
    if key in {"site_logo", "logo_image", "login_background_image"} and value.startswith("/uploads/"):
        return value
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        return value
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"设置项 '{key}' 必须是 http(s) URL 或允许的上传路径",
    )


def _normalize_setting(key: str, value: Any) -> Any:
    if key not in SETTING_SCHEMA:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不允许的设置项: {key}",
        )

    expected_type, max_length = SETTING_SCHEMA[key]
    if value is None:
        return "" if expected_type is str else value

    if expected_type is bool:
        if not isinstance(value, bool):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"设置项 '{key}' 必须是布尔值")
        return value

    if expected_type is int:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"设置项 '{key}' 必须是整数")
        min_value, max_value = INT_RANGES.get(key, (0, 1000000))
        if parsed < min_value or parsed > max_value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"设置项 '{key}' 必须在 {min_value}-{max_value} 范围内",
            )
        return parsed

    normalized = str(value).replace("\x00", "").strip()
    if max_length is not None and len(normalized) > max_length:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"设置项 '{key}' 长度不能超过 {max_length}",
        )
    if key in URL_KEYS:
        normalized = _validate_url(key, normalized)
    return normalized


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
        normalized_value = _normalize_setting(key, value.get("value") if isinstance(value, dict) and "value" in value else value)
        setting = Setting(key=key, value={"value": normalized_value})
        db.add(setting)
    else:
        normalized_value = _normalize_setting(key, value.get("value") if isinstance(value, dict) and "value" in value else value)
        setting.value = {"value": normalized_value}

    await db.commit()
    await db.refresh(setting)

    # Audit log
    await log_operation(
        db, current_user.id, "update", "setting", 0,
        details={
            "name": key,
            "value": _audit_setting_value(key, value),
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

        normalized_value = _normalize_setting(key, value)
        if setting:
            setting.value = {"value": normalized_value}
        else:
            setting = Setting(key=key, value={"value": normalized_value})
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