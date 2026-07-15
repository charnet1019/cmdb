"""
Settings API Routes
"""
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional
from email.utils import parseaddr
from urllib.parse import urlparse
from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.api.deps import AUTH_COOKIE_NAME, PermissionChecker
from app.utils.audit import log_operation
from app.utils.rate_limit import check_smtp_test_email_rate_limit
from app.utils.smtp import load_smtp_config, build_test_email, send_smtp_message, raise_smtp_config_incomplete, SMTP_ENCRYPTION_MODES
from app.models import Setting, User
from app.core.encryption import encrypt_value
from app.core.session import load_user_session, set_user_session_timeout


logger = logging.getLogger(__name__)


def format_datetime_utc(dt: datetime | None) -> str | None:
    """Format datetime as ISO 8601 with Z suffix for UTC"""
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc).isoformat().replace('+00:00', 'Z')


router = APIRouter(prefix="/settings", tags=["Settings"])


PUBLIC_BRANDING_KEYS = {"site_title", "login_subtitle", "logo_image", "login_background_image", "copyright_text", "beian_number", "beian_url"}

SETTING_SCHEMA: Dict[str, tuple[type, int | None]] = {
    "site_title": (str, 100),
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
    "decrypt_rate_limit": (int, None),
    "otp_issuer_name": (str, 100),
    "login_subtitle": (str, 200),
    "logo_image": (str, 500),
    "login_background_image": (str, 500),
    "smtp_host": (str, 255),
    "smtp_port": (int, None),
    "smtp_encryption": (str, 20),
    "smtp_username": (str, 255),
    "smtp_password": (str, 500),
    "smtp_from_email": (str, 255),
    "smtp_from_name": (str, 100),
}

INT_RANGES = {
    "login_log_retention": (1, 3650),
    "operation_log_retention": (1, 3650),
    "password_log_retention": (1, 3650),
    "password_min_length": (8, 128),
    "max_login_attempts": (1, 50),
    "lockout_duration": (1, 1440),
    "session_timeout": (1, 10080),
    "decrypt_rate_limit": (1, 100),
    "smtp_port": (1, 65535),
}

URL_KEYS = {"beian_url", "logo_image", "login_background_image"}
EMAIL_KEYS = {"smtp_from_email"}
ENUM_VALUES = {"smtp_encryption": {"ssl", "starttls", "none"}}
HOSTNAME_KEYS = {"smtp_host"}
SMTP_PASSWORD_MASK = "********"
SENSITIVE_SETTING_KEY_PARTS = ("secret", "token", "credential", "private_key", "api_key", "smtp_password")


class TestEmailRequest(BaseModel):
    """Request body for sending a test email using the currently-edited (unsaved)
    or currently-saved SMTP configuration."""
    recipient: str = Field(..., max_length=255)
    smtp_host: Optional[str] = Field(None, max_length=255)
    smtp_port: Optional[int] = Field(None, ge=1, le=65535)
    smtp_encryption: Optional[str] = Field(None, max_length=20)
    smtp_username: Optional[str] = Field(None, max_length=255)
    smtp_password: Optional[str] = Field(None, max_length=500)
    smtp_from_email: Optional[str] = Field(None, max_length=255)
    smtp_from_name: Optional[str] = Field(None, max_length=100)


def _audit_setting_value(key: str, value: Any) -> Any:
    lowered = key.lower()
    if any(part in lowered for part in SENSITIVE_SETTING_KEY_PARTS):
        return "<redacted>"
    return value


def _response_setting_value(key: str, value: Any) -> Any:
    if key == "smtp_password":
        return SMTP_PASSWORD_MASK if value else ""
    return value


def _set_auth_cookie(response: Response, request: Request, token: str, ttl_seconds: int) -> None:
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=token,
        max_age=ttl_seconds,
        httponly=True,
        secure=request.url.scheme == "https",
        samesite="lax",
        path="/",
    )


async def _apply_current_session_timeout(
    request: Request | None,
    response: Response,
    timeout_minutes: int,
) -> str | None:
    if request is None:
        return None
    session_id = getattr(request.state, "session_id", None)
    if not session_id:
        return None

    current_payload = await load_user_session(session_id)
    if not current_payload:
        return None
    if current_payload.get("remember"):
        return current_payload.get("expires_at")

    ttl_seconds = max(60, timeout_minutes * 60)
    session_payload = await set_user_session_timeout(session_id, timedelta(seconds=ttl_seconds))
    if not session_payload:
        return None

    _set_auth_cookie(response, request, session_id, ttl_seconds)
    return session_payload.get("expires_at")


def _validate_url(key: str, value: str) -> str:
    if not value:
        return value
    parsed = urlparse(value)
    if key in {"logo_image", "login_background_image"} and value.startswith("/uploads/"):
        return value
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        return value
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"设置项 '{key}' 必须是 http(s) URL 或允许的上传路径",
    )


def _validate_hostname(key: str, value: str) -> str:
    """Reject obviously malformed values (URLs, whitespace, control chars) while
    still allowing any legitimate hostname or IP, including private/internal
    ranges commonly used for internal SMTP relays."""
    if not value:
        return value
    if "://" in value or "/" in value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"设置项 '{key}' 应为主机名或 IP 地址，不能包含协议前缀或路径",
        )
    if any(ch.isspace() or ord(ch) < 0x20 for ch in value):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"设置项 '{key}' 不能包含空白或控制字符",
        )
    return value


def _normalize_setting(key: str, value: Any, existing_value: Any = None) -> Any:
    if key not in SETTING_SCHEMA:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不允许的设置项: {key}",
        )

    expected_type, max_length = SETTING_SCHEMA[key]
    if key == "smtp_password":
        if value in (None, "", SMTP_PASSWORD_MASK):
            return existing_value if value == SMTP_PASSWORD_MASK and existing_value else ""
        return encrypt_value(str(value))

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
    if key in HOSTNAME_KEYS:
        normalized = _validate_hostname(key, normalized)
    if key in ENUM_VALUES:
        normalized = normalized.lower()
        if normalized not in ENUM_VALUES[key]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"设置项 '{key}' 必须是 {', '.join(sorted(ENUM_VALUES[key]))} 之一",
            )
    if key in EMAIL_KEYS and normalized:
        _, parsed_email = parseaddr(normalized)
        if not parsed_email or "@" not in parsed_email:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="设置项 smtp_from_email 必须是有效邮箱地址")
        normalized = parsed_email
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
        stored_value = setting.value.get("value") if setting.value else None
        settings_dict[setting.key] = _response_setting_value(setting.key, stored_value)

    return {
        "code": 0,
        "message": "success",
        "data": settings_dict,
        "raw": [{"id": s.id, "key": s.key, "value": {"value": _response_setting_value(s.key, s.value.get("value") if s.value else None)}, "description": s.description, "updated_at": format_datetime_utc(s.updated_at)} for s in settings_list]
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
            "value": {"value": _response_setting_value(setting.key, setting.value.get("value") if setting.value else None)},
            "description": setting.description,
            "updated_at": format_datetime_utc(setting.updated_at)
        }
    }


@router.put("/{key}")
async def update_setting(
    key: str,
    value: Dict[str, Any],
    response: Response,
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

    incoming_value = value.get("value") if isinstance(value, dict) and "value" in value else value
    previous_value = setting.value.get("value") if setting and setting.value else None
    normalized_value = _normalize_setting(key, incoming_value, previous_value)
    changes = {}
    if previous_value != normalized_value:
        changes[key] = [_audit_setting_value(key, previous_value), _audit_setting_value(key, normalized_value)]

    if not setting:
        setting = Setting(key=key, value={"value": normalized_value})
        db.add(setting)
    else:
        setting.value = {"value": normalized_value}

    await db.commit()
    await db.refresh(setting)

    session_expires_at = None
    if key == "session_timeout":
        session_expires_at = await _apply_current_session_timeout(request, response, normalized_value)

    # Audit log
    if changes:
        await log_operation(
            db, current_user.id, "update", "setting", 0,
            details={
                "name": key,
                "value": _audit_setting_value(key, normalized_value),
                "changes": changes,
            },
            ip_address=ip,
        )

    return {
        "data": {
            "id": setting.id,
            "key": setting.key,
            "value": {"value": _response_setting_value(setting.key, setting.value.get("value") if setting.value else None)},
            "description": setting.description,
            "updated_at": format_datetime_utc(setting.updated_at),
            "session_expires_at": session_expires_at,
        }
    }


@router.put("")
async def update_settings(
    settings_data: Dict[str, Any],
    response: Response,
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
    changes = {}
    session_timeout_value = None

    for key, value in settings_data.items():
        result = await db.execute(select(Setting).where(Setting.key == key))
        setting = result.scalar_one_or_none()

        previous_value = setting.value.get("value") if setting and setting.value else None
        normalized_value = _normalize_setting(key, value, previous_value)
        if key == "session_timeout":
            session_timeout_value = normalized_value
        if previous_value != normalized_value:
            changes[key] = [_audit_setting_value(key, previous_value), _audit_setting_value(key, normalized_value)]
        if setting:
            setting.value = {"value": normalized_value}
        else:
            setting = Setting(key=key, value={"value": normalized_value})
            db.add(setting)
        updated.append(key)

    await db.commit()

    session_expires_at = None
    if session_timeout_value is not None:
        session_expires_at = await _apply_current_session_timeout(request, response, session_timeout_value)

    # Audit log
    if changes:
        await log_operation(
            db, current_user.id, "update", "setting", 0,
            details={
                "name": "batch_update",
                "keys": list(changes.keys()),
                "changes": changes,
            },
            ip_address=ip,
        )

    return {
        "data": {
            "updated": updated,
            "message": f"Updated {len(updated)} settings",
            "session_expires_at": session_expires_at,
        }
    }


@router.post("/email/test")
async def send_test_email(
    data: TestEmailRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("sys_config")),
) -> Dict[str, Any]:
    """
    Send a test email using the currently-edited (unsaved) SMTP fields if provided,
    falling back to the saved settings for any field left blank.
    Requires sys_config permission.
    """
    ip = request.client.host if request.client else None

    recipient = data.recipient.strip()
    _, parsed_email = parseaddr(recipient)
    if not parsed_email or "@" not in parsed_email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请输入有效的收件人邮箱地址")

    await check_smtp_test_email_rate_limit(current_user.id)

    saved_config = await load_smtp_config(db)
    config = dict(saved_config)
    if data.smtp_host is not None:
        config["host"] = data.smtp_host.strip()
    if data.smtp_port is not None:
        config["port"] = data.smtp_port
    if data.smtp_encryption is not None:
        encryption = data.smtp_encryption.strip().lower()
        if encryption not in SMTP_ENCRYPTION_MODES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="加密方式必须是 ssl、starttls 或 none 之一")
        config["encryption"] = encryption
    if data.smtp_username is not None:
        config["username"] = data.smtp_username.strip()
    if data.smtp_password:
        # A literal mask means "keep the saved password" — already the default in config.
        if data.smtp_password != SMTP_PASSWORD_MASK:
            config["password"] = data.smtp_password
    if data.smtp_from_email is not None:
        config["from_email"] = data.smtp_from_email.strip()
    if data.smtp_from_name is not None:
        config["from_name"] = data.smtp_from_name.strip() or "CMDB"

    if not config["host"] or not config["from_email"]:
        raise_smtp_config_incomplete()

    log_details = {
        "action": "send_test_email",
        "recipient": recipient,
        "smtp_host": config["host"],
        "smtp_port": config["port"],
        "smtp_encryption": config["encryption"],
    }

    try:
        msg = build_test_email(config, recipient)
        await asyncio.to_thread(send_smtp_message, config, msg)
    except Exception as exc:
        logger.warning("Test email send failed for user_id=%s host=%s: %s", current_user.id, config["host"], exc)
        await log_operation(
            db, current_user.id, "test", "setting", 0,
            details=log_details, ip_address=ip, status="failed",
        )
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="测试邮件发送失败，请检查邮件服务器配置") from exc

    await log_operation(
        db, current_user.id, "test", "setting", 0,
        details=log_details, ip_address=ip,
    )

    return {"code": 0, "message": "测试邮件已发送", "data": {"recipient": recipient}}