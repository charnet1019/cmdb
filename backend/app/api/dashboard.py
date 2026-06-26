"""
Dashboard API
Statistics and overview data for dashboard page
"""
from datetime import datetime
from typing import List, Dict, Optional
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, false

from app.database import get_db
from app.models import User, Asset, LoginLog
from app.api.deps import get_current_user, get_authorized_asset_ids
from app.core.redis_client import get_redis, ONLINE_KEY_PREFIX
from app.schemas import ResponseBase


router = APIRouter(prefix="/dashboard", tags=["仪表盘"])

# Sub-category field mapping: which column to group by for each asset category
SUB_CATEGORY_FIELDS: Dict[str, str] = {
    "host": "platform",
    "network": "platform",
    "database": "db_type",
    "cloud": "platform",
    "web": "platform",
    "gpt": "platform",
}

@router.get("/stats")
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get dashboard statistics
    """
    # Resource-level authorization filter
    authorized_ids = await get_authorized_asset_ids(current_user, db, "view")

    if authorized_ids is None:
        # Superuser — full access, no filter
        asset_filter = None
    elif len(authorized_ids) == 0:
        # No authorized assets — filter everything out
        asset_filter = false()
    else:
        # Filter to authorized IDs
        asset_filter = Asset.id.in_(authorized_ids)

    # Total assets count (all statuses)
    count_query = select(func.count()).select_from(Asset)
    if asset_filter is not None:
        count_query = count_query.where(asset_filter)
    assets_result = await db.execute(count_query)
    total_assets = assets_result.scalar() or 0

    # Asset type distribution (all statuses)
    dist_query = select(Asset.category, func.count().label("count"))
    if asset_filter is not None:
        dist_query = dist_query.where(asset_filter)
    asset_distribution_result = await db.execute(dist_query.group_by(Asset.category))
    asset_distribution = [
        {"type": row.category, "count": row.count}
        for row in asset_distribution_result.all()
    ]

    # Status distribution (all statuses)
    status_query = select(Asset.status, func.count().label("count"))
    if asset_filter is not None:
        status_query = status_query.where(asset_filter)
    status_result = await db.execute(status_query.group_by(Asset.status))
    status_distribution = [
        {"name": row[0], "count": row.count}
        for row in status_result.all()
    ]

    # Sub-distribution: for each category, group by the sub-category field (all statuses)
    sub_distribution: Dict[str, List[Dict[str, str | int]]] = {}
    for category, sub_field in SUB_CATEGORY_FIELDS.items():
        col = getattr(Asset, sub_field)
        sub_query = select(col, func.count().label("count")).where(Asset.category == category).where(col.isnot(None))
        if asset_filter is not None:
            sub_query = sub_query.where(asset_filter)
        sub_query = sub_query.group_by(col)
        sub_result = await db.execute(sub_query)
        sub_distribution[category] = [
            {"name": row[0], "count": row.count}
            for row in sub_result.all()
        ]

    # Total users count
    users_result = await db.execute(select(func.count()).select_from(User))
    total_users = users_result.scalar() or 0

    # Active users count
    active_users_result = await db.execute(
        select(func.count()).select_from(User).where(User.is_active == True)
    )
    active_users = active_users_result.scalar() or 0

    # Online users — count Redis presence keys
    redis_client = get_redis()
    keys = [k for k in await redis_client.keys(f"{ONLINE_KEY_PREFIX}*")]
    online_user_ids = {int(k.split(":online:")[1]) for k in keys}
    online_users = len(online_user_ids)

    # Recent successful logins (last 5)
    recent_logins_result = await db.execute(
        select(LoginLog, User)
        .join(User, LoginLog.user_id == User.id, isouter=True)
        .where(LoginLog.status == "success")
        .order_by(LoginLog.created_at.desc())
        .limit(5)
    )
    recent_logins = []
    for login_log, user in recent_logins_result.all():
        recent_logins.append({
            "user": user.full_name if user and user.full_name else (user.username if user else login_log.username),
            "time": login_log.created_at.strftime("%H:%M"),
            "ip": login_log.ip_address,
            "user_id": login_log.user_id,
            "is_online": login_log.user_id in online_user_ids,
        })

    return {
        "code": 0,
        "data": {
            "total_assets": total_assets,
            "total_users": total_users,
            "active_users": active_users,
            "online_users": online_users,
            "asset_distribution": asset_distribution,
            "status_distribution": status_distribution,
            "sub_distribution": sub_distribution,
            "recent_logins": recent_logins,
        }
    }