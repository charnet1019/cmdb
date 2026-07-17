"""
Password Change Log Audit API
"""
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, alias

from app.database import get_db
from app.models import User, PasswordChangeLog, Asset, Credential
from app.api.deps import PermissionChecker
from app.utils.datetime_utils import format_datetime_utc
from app.utils.pagination import get_pagination_meta

router = APIRouter(prefix="/logs", tags=["日志审计"])


@router.get("/password")
async def list_password_logs(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    user_id: Optional[int] = Query(None),
    change_type: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("audit_log")),
):
    """List password change logs with pagination and filters"""
    # Aliases for multiple User joins
    UserAlias = alias(User)
    ChangerAlias = alias(User)

    query = select(PasswordChangeLog)

    # Apply filters
    if search:
        query = (
            query
            .outerjoin(UserAlias, UserAlias.c.id == PasswordChangeLog.user_id)
            .outerjoin(Credential, Credential.id == PasswordChangeLog.credential_id)
            .outerjoin(Asset, Asset.id == Credential.asset_id)
            .outerjoin(ChangerAlias, ChangerAlias.c.id == PasswordChangeLog.changed_by)
            .where(
                or_(
                    UserAlias.c.username.ilike(f"%{search}%"),
                    Credential.username.ilike(f"%{search}%"),
                    Asset.name.ilike(f"%{search}%"),
                    ChangerAlias.c.username.ilike(f"%{search}%"),
                )
            )
        )

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

    meta = await get_pagination_meta(db, query, page, limit)

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
        "meta": meta,
    }
