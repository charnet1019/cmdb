"""Shared helpers for reading generic key/value entries from the settings table."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Setting


def setting_plain_value(setting: Setting | None, default=None):
    if not setting or not isinstance(setting.value, dict):
        return default
    return setting.value.get("value", default)


async def get_setting_value(db: AsyncSession, key: str, default=None):
    result = await db.execute(select(Setting).where(Setting.key == key))
    return setting_plain_value(result.scalar_one_or_none(), default)


async def get_int_setting(db: AsyncSession, key: str, default: int, min_value: int, max_value: int) -> int:
    value = await get_setting_value(db, key, default)
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(min_value, min(parsed, max_value))
