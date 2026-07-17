"""
Login Log Audit API
"""
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_

from app.database import get_db
from app.models import User, LoginLog
from app.api.deps import PermissionChecker
from app.utils.datetime_utils import format_datetime_utc
from app.utils.pagination import get_pagination_meta

router = APIRouter(prefix="/logs", tags=["日志审计"])


@router.get("/login")
async def list_login_logs(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("audit_log")),
):
    """List login logs with pagination and filters"""
    query = select(LoginLog)

    # Apply filters
    if search:
        query = query.where(
            or_(
                LoginLog.username.ilike(f"%{search}%"),
                LoginLog.ip_address.ilike(f"%{search}%"),
            )
        )

    if status:
        query = query.where(LoginLog.status == status)

    if date_from:
        try:
            from_date = datetime.fromisoformat(date_from)
            query = query.where(LoginLog.created_at >= from_date)
        except ValueError:
            pass

    if date_to:
        try:
            to_date = datetime.fromisoformat(date_to) + timedelta(days=1)
            query = query.where(LoginLog.created_at < to_date)
        except ValueError:
            pass

    meta = await get_pagination_meta(db, query, page, limit)

    # Calculate stats with single query using case aggregation
    # Use UTC datetime without timezone for compatibility with database
    today = datetime.utcnow().date()
    today_start = datetime.combine(today, datetime.min.time())

    stats_query = select(
        func.count().filter(LoginLog.created_at >= today_start).label("today_count"),
        func.count().filter(LoginLog.status == "success").label("success_count"),
        func.count().filter(LoginLog.status == "failed").label("failed_count"),
    ).select_from(LoginLog)

    stats_result = await db.execute(stats_query)
    stats_row = stats_result.one()
    today_count = stats_row.today_count or 0
    success_count = stats_row.success_count or 0
    failed_count = stats_row.failed_count or 0

    total_logins = success_count + failed_count
    success_rate = round((success_count / total_logins * 100), 1) if total_logins > 0 else 0

    # Apply pagination
    query = query.offset((page - 1) * limit).limit(limit)
    query = query.order_by(LoginLog.created_at.desc())

    result = await db.execute(query)
    logs = result.scalars().all()

    return {
        "code": 0,
        "message": "success",
        "data": [
            {
                "id": log.id,
                "user_id": log.user_id,
                "username": log.username,
                "ip_address": log.ip_address,
                "user_agent": log.user_agent,
                "status": log.status,
                "failure_reason": log.failure_reason,
                "created_at": format_datetime_utc(log.created_at),
            }
            for log in logs
        ],
        "meta": meta,
        "stats": {
            "today_total": today_count,
            "success_rate": success_rate,
            "failed_count": failed_count,
        }
    }
