"""
Log cleanup service — delete expired audit logs based on retention settings
"""
import logging
from datetime import datetime, timedelta

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import LoginLog, OperationLog, PasswordChangeLog, Setting

logger = logging.getLogger(__name__)

RETENTION_KEYS = {
    "login_log_retention": LoginLog,
    "operation_log_retention": OperationLog,
    "password_log_retention": PasswordChangeLog,
}

DEFAULT_RETENTION_DAYS = 30


async def get_retention_days(db: AsyncSession, key: str) -> int:
    result = await db.execute(select(Setting).where(Setting.key == key))
    setting = result.scalar_one_or_none()
    if setting and setting.value and isinstance(setting.value.get("value"), int):
        return setting.value["value"]
    return DEFAULT_RETENTION_DAYS


async def cleanup_expired_logs(db: AsyncSession) -> dict[str, int]:
    """Delete logs older than their configured retention period.

    Returns a dict mapping log type name to number of deleted rows.
    """
    deleted = {}
    for key, model in RETENTION_KEYS.items():
        retention = await get_retention_days(db, key)
        cutoff = datetime.utcnow() - timedelta(days=retention)
        result = await db.execute(delete(model).where(model.created_at < cutoff))
        count = result.rowcount if result.rowcount else 0
        deleted[key] = count
        if count:
            logger.info("Deleted %d expired %s (retention: %d days)", count, key, retention)
    await db.commit()
    return deleted
