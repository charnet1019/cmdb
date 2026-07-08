"""Password policy helpers backed by system settings."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Setting


async def _setting_value(db: AsyncSession, key: str, default):
    result = await db.execute(select(Setting).where(Setting.key == key))
    setting = result.scalar_one_or_none()
    if not setting or not isinstance(setting.value, dict):
        return default
    return setting.value.get("value", default)


async def validate_password_strength_from_settings(
    password: str,
    db: AsyncSession,
) -> tuple[bool, list[str]]:
    min_length = int(await _setting_value(db, "password_min_length", settings.PASSWORD_MIN_LENGTH))
    require_uppercase = bool(await _setting_value(db, "password_require_uppercase", settings.PASSWORD_REQUIRE_UPPERCASE))
    require_lowercase = bool(await _setting_value(db, "password_require_lowercase", settings.PASSWORD_REQUIRE_LOWERCASE))
    require_digit = bool(await _setting_value(db, "password_require_digit", settings.PASSWORD_REQUIRE_DIGIT))
    require_special = bool(await _setting_value(db, "password_require_special", settings.PASSWORD_REQUIRE_SPECIAL))

    min_length = max(8, min(min_length, settings.PASSWORD_MAX_LENGTH))
    errors: list[str] = []

    if len(password) < min_length:
        errors.append(f"密码长度不能少于 {min_length} 个字符")
    if len(password) > settings.PASSWORD_MAX_LENGTH:
        errors.append(f"密码长度不能超过 {settings.PASSWORD_MAX_LENGTH} 个字符")
    if require_uppercase and not any(c.isupper() for c in password):
        errors.append("密码必须包含大写字母")
    if require_lowercase and not any(c.islower() for c in password):
        errors.append("密码必须包含小写字母")
    if require_digit and not any(c.isdigit() for c in password):
        errors.append("密码必须包含数字")
    if require_special:
        special_chars = "!@#$%^&*()_+-=[]{}|;:',.<>/?"
        if not any(c in special_chars for c in password):
            errors.append("密码必须包含特殊字符")

    return len(errors) == 0, errors
