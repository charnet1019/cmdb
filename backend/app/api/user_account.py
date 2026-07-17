"""
User Account Actions API
Force-logout, password reset, and authorization lookups for a user
"""
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import User, Group, UserGroup, Authorization, Asset, PasswordChangeLog
from app.utils.audit import log_operation
from app.schemas import PasswordResetRequest, ResponseBase
from app.api.deps import get_current_user, PermissionChecker, get_user_permissions
from app.core.security import verify_password, get_password_hash
from app.core.password_policy import validate_password_strength_from_settings, check_password_not_reused, record_password_history
from app.core.session import force_logout_user
from app.api.users import (
    router,
    _publish_force_logout_event,
    generate_temporary_password,
    send_user_password_email,
)


@router.post("/{user_id}/force-logout", response_model=ResponseBase)
async def force_logout_user_sessions(
    user_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("user_mgmt")),
):
    """Admin: invalidate all active sessions for a user."""
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能强制离线自己",
        )

    result = await db.execute(select(User).where(User.id == user_id))
    target_user = result.scalar_one_or_none()
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")

    terminated_count = await force_logout_user(user_id)
    await _publish_force_logout_event(user_id, "admin_forced", "账号已被管理员强制离线")

    await log_operation(
        db, current_user.id, "update", "user", user_id,
        details={
            "action": "force_logout",
            "username": target_user.username,
            "terminated_sessions": terminated_count,
        },
        ip_address=request.client.host if request.client else None,
    )

    return ResponseBase(
        message="用户已强制离线",
        data={"terminated_sessions": terminated_count},
    )


@router.post("/{user_id}/reset-password", response_model=ResponseBase)
async def reset_user_password(
    user_id: int,
    data: PasswordResetRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("user_mgmt")),
):
    """Reset user password (admin only)"""
    ip = request.client.host if request.client else None
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )

    if data.method not in {"manual", "auto"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不支持的密码重置方式")

    if data.method == "manual":
        if not data.new_password:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请输入新密码")
        # Validate password
        is_valid, errors = await validate_password_strength_from_settings(data.new_password, db)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="; ".join(errors)
            )
        if verify_password(data.new_password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="新密码不能与当前密码相同"
            )
        await check_password_not_reused(data.new_password, user.id, db)
        new_password_hash = get_password_hash(data.new_password)
        user.password_hash = new_password_hash
        temp_password = None
    else:
        temp_password = await generate_temporary_password(db)
        new_password_hash = get_password_hash(temp_password)
        user.password_hash = new_password_hash

    if data.force_change:
        user.must_change_password = True

    await record_password_history(new_password_hash, user.id, db)
    await db.commit()

    # Log as password change (not operation)
    password_log = PasswordChangeLog(
        user_id=user_id,
        change_type="user_password",
        changed_by=current_user.id,
        ip_address=ip,
    )
    db.add(password_log)
    await db.commit()

    # Password is already committed at this point. Email sending happens after
    # the transaction closes — a failure here must not undo the password reset;
    # report it back to the admin instead so they can relay the password manually.
    email_sent = False
    if temp_password and data.send_email:
        try:
            await send_user_password_email(db, user, temp_password, "reset")
            email_sent = True
        except HTTPException:
            email_sent = False

    return ResponseBase(
        message="密码重置成功",
        data={"email_sent": email_sent, "temp_password": None if email_sent else temp_password} if temp_password else None,
    )


@router.get("/{user_id}/authorizations")
async def get_user_authorizations(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get user's asset authorizations — self-lookup allowed, others require view_users or user_mgmt"""
    if user_id != current_user.id and not current_user.is_superuser:
        perms = await get_user_permissions(current_user, db)
        if "user_mgmt" not in perms and "view_users" not in perms:
            raise HTTPException(status_code=403, detail="缺少 'view_users' 或 'user_mgmt' 权限")

    # Check user exists
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    # Get user's groups
    groups_result = await db.execute(
        select(Group).join(UserGroup).where(UserGroup.user_id == user_id)
    )
    user_groups = groups_result.scalars().all()
    group_ids = [g.id for g in user_groups]

    # Get direct authorizations (entity_type='user')
    direct_auths_result = await db.execute(
        select(Authorization).where(
            Authorization.entity_type == "user",
            Authorization.entity_id == user_id,
            Authorization.is_active == True,
        )
    )
    direct_auths = direct_auths_result.scalars().all()

    # Get inherited authorizations (entity_type='group')
    inherited_auths = []
    if group_ids:
        inherited_auths_result = await db.execute(
            select(Authorization).where(
                Authorization.entity_type == "group",
                Authorization.entity_id.in_(group_ids),
                Authorization.is_active == True,
            )
        )
        inherited_auths = inherited_auths_result.scalars().all()

    # Collect all asset IDs
    asset_ids = set()
    for auth in direct_auths + inherited_auths:
        if auth.target_type == "asset":
            asset_ids.update(auth.target_ids)

    # Batch fetch assets
    assets_map = {}
    if asset_ids:
        assets_result = await db.execute(select(Asset).where(Asset.id.in_(asset_ids)))
        for asset in assets_result.scalars().all():
            assets_map[asset.id] = asset

    # Build response — one entry per (auth, asset) pair
    direct_list = []
    for auth in direct_auths:
        for target_id in auth.target_ids:
            asset = assets_map.get(target_id)
            if asset:
                direct_list.append({
                    "id": auth.id,
                    "asset_id": asset.id,
                    "asset_name": asset.name,
                    "asset_category": asset.category,
                    "permissions": auth.permissions,
                    "valid_until": auth.valid_until.isoformat() if auth.valid_until else None,
                    "status": "active" if auth.is_active else "inactive",
                    "source_type": "direct",
                })

    inherited_list = []
    for auth in inherited_auths:
        for target_id in auth.target_ids:
            asset = assets_map.get(target_id)
            if asset:
                # Find group name
                group_name = next((g.name for g in user_groups if g.id == auth.entity_id), "Unknown")
                inherited_list.append({
                    "id": auth.id,
                    "asset_id": asset.id,
                    "asset_name": asset.name,
                    "asset_category": asset.category,
                    "permissions": auth.permissions,
                    "valid_until": auth.valid_until.isoformat() if auth.valid_until else None,
                    "status": "active" if auth.is_active else "inactive",
                    "source_type": "group",
                    "group_id": auth.entity_id,
                    "group_name": group_name,
                })

    return {
        "code": 0,
        "data": {
            "direct": direct_list,
            "inherited": inherited_list,
            "total": len(direct_list) + len(inherited_list),
        }
    }
