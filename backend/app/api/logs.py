"""
Log Audit API
Login logs, operation logs, and password change logs
"""
from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_

from app.database import get_db
from app.models import User, LoginLog, OperationLog, PasswordChangeLog, Asset, Credential
from app.api.deps import get_current_user, PermissionChecker
from app.schemas import PaginationMeta, ResponseBase


def format_datetime_utc(dt: datetime | None) -> str | None:
    """Format datetime as ISO 8601 with Z suffix for UTC"""
    if dt is None:
        return None
    # Ensure we treat it as UTC and add Z suffix
    return dt.replace(tzinfo=timezone.utc).isoformat().replace('+00:00', 'Z')


router = APIRouter(prefix="/logs", tags=["日志审计"])


# ============== Login Logs ==============
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

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()

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
        "meta": PaginationMeta(
            total=total,
            page=page,
            limit=limit,
            pages=(total + limit - 1) // limit,
        ),
        "stats": {
            "today_total": today_count,
            "success_rate": success_rate,
            "failed_count": failed_count,
        }
    }


# ============== Operation Logs ==============
@router.get("/operation")
async def list_operation_logs(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    user_id: Optional[int] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("audit_log")),
):
    """List operation logs with pagination and filters"""
    query = select(OperationLog)

    # Apply filters
    if search:
        query = query.where(
            or_(
                OperationLog.resource_type.ilike(f"%{search}%"),
                OperationLog.details.ilike(f"%{search}%"),
            )
        )

    if action:
        query = query.where(OperationLog.action == action)

    if user_id:
        query = query.where(OperationLog.user_id == user_id)

    if date_from:
        try:
            from_date = datetime.fromisoformat(date_from)
            query = query.where(OperationLog.created_at >= from_date)
        except ValueError:
            pass

    if date_to:
        try:
            to_date = datetime.fromisoformat(date_to) + timedelta(days=1)
            query = query.where(OperationLog.created_at < to_date)
        except ValueError:
            pass

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # Apply pagination
    query = query.offset((page - 1) * limit).limit(limit)
    query = query.order_by(OperationLog.created_at.desc())

    result = await db.execute(query)
    logs = result.scalars().all()

    # Get usernames
    user_ids = list(set(log.user_id for log in logs if log.user_id))
    users_map = {}
    if user_ids:
        users_result = await db.execute(
            select(User).where(User.id.in_(user_ids))
        )
        users = users_result.scalars().all()
        users_map = {u.id: u.username for u in users}

    return {
        "code": 0,
        "message": "success",
        "data": [
            {
                "id": log.id,
                "user_id": log.user_id,
                "username": users_map.get(log.user_id, "Unknown"),
                "action": log.action,
                "resource_type": log.resource_type,
                "resource_id": log.resource_id,
                "resource_name": (log.details or {}).get("username") or (log.details or {}).get("name") or (log.details or {}).get("group_name") or str(log.resource_id) if log.resource_id else None,
                "details": log.details,
                "ip_address": log.ip_address,
                "status": log.status,
                "created_at": format_datetime_utc(log.created_at),
            }
            for log in logs
        ],
        "meta": PaginationMeta(
            total=total,
            page=page,
            limit=limit,
            pages=(total + limit - 1) // limit,
        )
    }


# ============== Password Change Logs ==============
@router.get("/password")
async def list_password_logs(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    user_id: Optional[int] = Query(None),
    change_type: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("audit_log")),
):
    """List password change logs with pagination and filters"""
    query = select(PasswordChangeLog)

    # Apply filters
    if user_id:
        query = query.where(PasswordChangeLog.user_id == user_id)

    if change_type:
        query = query.where(PasswordChangeLog.change_type == change_type)

    if date_from:
        try:
            from_date = datetime.fromisoformat(date_from)
            query = query.where(PasswordChangeLog.created_at >= from_date)
        except ValueError:
            pass

    if date_to:
        try:
            to_date = datetime.fromisoformat(date_to) + timedelta(days=1)
            query = query.where(PasswordChangeLog.created_at < to_date)
        except ValueError:
            pass

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # Apply pagination
    query = query.offset((page - 1) * limit).limit(limit)
    query = query.order_by(PasswordChangeLog.created_at.desc())

    result = await db.execute(query)
    logs = result.scalars().all()

    # Get usernames
    user_ids = list(set(log.user_id for log in logs if log.user_id))
    user_ids.extend(list(set(log.changed_by for log in logs if log.changed_by)))
    user_ids = list(set(user_ids))

    users_map = {}
    if user_ids:
        users_result = await db.execute(
            select(User).where(User.id.in_(user_ids))
        )
        users = users_result.scalars().all()
        users_map = {u.id: u.username for u in users}

    # Resolve credential_id → asset name + credential username
    credential_ids = list(set(log.credential_id for log in logs if log.credential_id))
    asset_names_map = {}
    cred_usernames_map = {}
    if credential_ids:
        creds_result = await db.execute(
            select(Credential.id, Credential.asset_id, Credential.username).where(Credential.id.in_(credential_ids))
        )
        cred_to_asset = {}
        for row in creds_result.all():
            cred_id, asset_id, cred_username = row
            cred_to_asset[cred_id] = asset_id
            cred_usernames_map[cred_id] = cred_username
        cred_asset_ids = list(cred_to_asset.values())

        if cred_asset_ids:
            assets_result = await db.execute(
                select(Asset.id, Asset.name).where(Asset.id.in_(cred_asset_ids))
            )
            assets_map = {row[0]: row[1] for row in assets_result.all()}
            for cred_id, asset_id in cred_to_asset.items():
                asset_names_map[cred_id] = assets_map.get(asset_id, asset_id)

    return {
        "code": 0,
        "message": "success",
        "data": [
            {
                "id": log.id,
                "user_id": log.user_id,
                "username": users_map.get(log.user_id, "Unknown") if log.user_id else cred_usernames_map.get(log.credential_id) if log.credential_id else None,
                "credential_id": log.credential_id,
                "asset_name": asset_names_map.get(log.credential_id) if log.credential_id else None,
                "change_type": log.change_type,
                "changed_by": log.changed_by,
                "changed_by_name": users_map.get(log.changed_by, "Unknown"),
                "ip_address": log.ip_address,
                "status": log.status,
                "created_at": format_datetime_utc(log.created_at),
            }
            for log in logs
        ],
        "meta": PaginationMeta(
            total=total,
            page=page,
            limit=limit,
            pages=(total + limit - 1) // limit,
        )
    }