"""
Dashboard API
Statistics and overview data for dashboard page
"""
from datetime import datetime, timedelta
from typing import List, Dict
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, distinct

from app.database import get_db
from app.models import User, Asset, LoginLog
from app.api.deps import get_current_user
from app.schemas import ResponseBase


router = APIRouter(prefix="/dashboard", tags=["仪表盘"])


@router.get("/stats")
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get dashboard statistics
    """
    # Total assets count
    assets_result = await db.execute(select(func.count()).select_from(Asset))
    total_assets = assets_result.scalar() or 0

    # Active assets count
    from app.models import AssetStatus

    # Active assets count (not deactivated, pending_scrap, scrapped, returned)
    inactive_statuses = [AssetStatus.DEACTIVATED, AssetStatus.PENDING_SCRAP, AssetStatus.SCRAPPED, AssetStatus.RETURNED]
    active_assets_result = await db.execute(
        select(func.count()).select_from(Asset).where(Asset.status.notin_(inactive_statuses))
    )
    active_assets = active_assets_result.scalar() or 0

    # Total users count
    users_result = await db.execute(select(func.count()).select_from(User))
    total_users = users_result.scalar() or 0

    # Active users count
    active_users_result = await db.execute(
        select(func.count()).select_from(User).where(User.is_active == True)
    )
    active_users = active_users_result.scalar() or 0

    # Online users (logged in within last 30 minutes)
    thirty_minutes_ago = datetime.utcnow() - timedelta(minutes=30)
    online_users_result = await db.execute(
        select(func.count(distinct(LoginLog.user_id)))
        .where(LoginLog.created_at >= thirty_minutes_ago)
        .where(LoginLog.status == "success")
    )
    online_users = online_users_result.scalar() or 0

    # Asset type distribution
    from app.models import AssetStatus

    inactive_statuses = [AssetStatus.DEACTIVATED, AssetStatus.PENDING_SCRAP, AssetStatus.SCRAPPED, AssetStatus.RETURNED]
    asset_distribution_result = await db.execute(
        select(Asset.category, func.count().label("count"))
        .where(Asset.status.notin_(inactive_statuses))
        .group_by(Asset.category)
    )
    asset_distribution = [
        {"type": row.category, "count": row.count}
        for row in asset_distribution_result.all()
    ]

    # Recent successful logins (last 10)
    recent_logins_result = await db.execute(
        select(LoginLog, User)
        .join(User, LoginLog.user_id == User.id, isouter=True)
        .where(LoginLog.status == "success")
        .order_by(LoginLog.created_at.desc())
        .limit(10)
    )
    recent_logins = []
    for login_log, user in recent_logins_result.all():
        recent_logins.append({
            "user": user.full_name if user and user.full_name else (user.username if user else login_log.username),
            "time": login_log.created_at.strftime("%H:%M"),
            "ip": login_log.ip_address,
            "user_id": login_log.user_id,
        })

    return {
        "code": 0,
        "data": {
            "total_assets": total_assets,
            "active_assets": active_assets,
            "total_users": total_users,
            "active_users": active_users,
            "online_users": online_users,
            "asset_distribution": asset_distribution,
            "recent_logins": recent_logins,
        }
    }


@router.get("/alerts")
async def get_alerts(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get system alerts (failed logins, expiring authorizations, etc.)
    """
    # Failed login attempts in last 24 hours
    twenty_four_hours_ago = datetime.utcnow() - timedelta(hours=24)
    failed_logins_result = await db.execute(
        select(func.count())
        .where(LoginLog.status == "failed")
        .where(LoginLog.created_at >= twenty_four_hours_ago)
    )
    failed_logins = failed_logins_result.scalar() or 0

    # Count as alerts
    alerts = failed_logins if failed_logins > 10 else 0

    return {
        "code": 0,
        "data": {
            "alerts": alerts,
            "failed_logins_24h": failed_logins,
        }
    }