"""
Log Maintenance API
Manual log cleanup based on retention settings
"""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User
from app.api.deps import PermissionChecker
from app.utils.audit import log_operation
from app.services.log_cleanup import cleanup_expired_logs

router = APIRouter(prefix="/logs", tags=["日志审计"])


@router.post("/cleanup")
async def trigger_cleanup(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("sys_config")),
    request: Request = None,
):
    """Manually trigger log cleanup based on retention settings.

    Requires sys_config permission.
    """
    ip = request.client.host if request and request.client else None
    deleted = await cleanup_expired_logs(db)

    # Audit log
    await log_operation(
        db, current_user.id, "update", "log_cleanup", 0,
        details={
            "name": "manual_log_cleanup",
            "deleted_counts": deleted,
        },
        ip_address=ip,
    )

    return {
        "code": 0,
        "message": "success",
        "data": deleted,
    }
