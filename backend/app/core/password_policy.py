"""Password policy helpers backed by system settings."""
from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import PasswordHistory
from app.core.security import verify_password
from app.core.settings_helper import get_setting_value


async def validate_password_strength_from_settings(
    password: str,
    db: AsyncSession,
) -> tuple[bool, list[str]]:
    min_length = int(await get_setting_value(db, "password_min_length", settings.PASSWORD_MIN_LENGTH))
    require_uppercase = bool(await get_setting_value(db, "password_require_uppercase", settings.PASSWORD_REQUIRE_UPPERCASE))
    require_lowercase = bool(await get_setting_value(db, "password_require_lowercase", settings.PASSWORD_REQUIRE_LOWERCASE))
    require_digit = bool(await get_setting_value(db, "password_require_digit", settings.PASSWORD_REQUIRE_DIGIT))
    require_special = bool(await get_setting_value(db, "password_require_special", settings.PASSWORD_REQUIRE_SPECIAL))

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


async def check_password_not_reused(
    password: str,
    user_id: int,
    db: AsyncSession,
) -> None:
    """Raise 400 if `password` matches any of the user's last N password
    hashes, where N is the configured history_count."""
    history_count = int(await get_setting_value(db, "password_history_count", settings.PASSWORD_HISTORY_COUNT))
    history_count = max(0, min(history_count, 20))
    if history_count <= 0:
        return

    result = await db.execute(
        select(PasswordHistory.password_hash)
        .where(PasswordHistory.user_id == user_id)
        .order_by(PasswordHistory.created_at.desc())
        .limit(history_count)
    )
    for (old_hash,) in result.all():
        if verify_password(password, old_hash):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"新密码不能与最近使用过的 {history_count} 次密码相同",
            )


async def record_password_history(
    password_hash: str,
    user_id: int,
    db: AsyncSession,
) -> None:
    """Store the new password hash and prune old entries beyond history_count."""
    history_count = int(await get_setting_value(db, "password_history_count", settings.PASSWORD_HISTORY_COUNT))
    history_count = max(0, min(history_count, 20))

    db.add(PasswordHistory(user_id=user_id, password_hash=password_hash))
    await db.flush()

    if history_count <= 0:
        return

    result = await db.execute(
        select(PasswordHistory.id)
        .where(PasswordHistory.user_id == user_id)
        .order_by(PasswordHistory.created_at.desc())
        .offset(history_count)
    )
    stale_ids = [row[0] for row in result.all()]
    if stale_ids:
        await db.execute(
            PasswordHistory.__table__.delete().where(PasswordHistory.id.in_(stale_ids))
        )
