"""
User Management API
CRUD operations for users
"""
from typing import Optional, List
import asyncio
import logging
import secrets
import string
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_

from app.database import get_db
from app.models import User, Group, UserGroup, Authorization
from app.utils.audit import log_operation
from app.utils.naming import resolve_target_names
from app.utils.pagination import get_pagination_meta
from app.utils.rate_limit import check_password_email_rate_limit
from app.utils.smtp import load_smtp_config, build_password_email, send_smtp_message, raise_smtp_config_incomplete
from app.schemas import (
    UserCreate, UserUpdate, UserResponse, UserDetailResponse,
    UserListResponse, ResponseBase
)
from app.api.deps import get_current_user, PermissionChecker, get_user_permissions
from app.core.security import get_password_hash
from app.core.password_policy import validate_password_strength_from_settings, record_password_history
from app.core.settings_helper import get_setting_value
from app.core.session import force_logout_user
from app.core.events import publish_user_event
from app.config import settings


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users", tags=["用户管理"])


async def _publish_force_logout_event(user_id: int, reason: str, message: str) -> None:
    try:
        await publish_user_event(user_id, "force_logout", {"reason": reason, "message": message})
    except Exception:
        # Session invalidation remains authoritative; API 401 handling is the fallback.
        pass


async def generate_temporary_password(db: AsyncSession) -> str:
    min_length = int(await get_setting_value(db, "password_min_length", settings.PASSWORD_MIN_LENGTH) or settings.PASSWORD_MIN_LENGTH)
    length = max(16, min(min_length, settings.PASSWORD_MAX_LENGTH))
    special_chars = "!_-+=*"
    required = [
        secrets.choice(string.ascii_lowercase),
        secrets.choice(string.ascii_uppercase),
        secrets.choice(string.digits),
        secrets.choice(special_chars),
    ]
    alphabet = string.ascii_letters + string.digits + special_chars
    chars = required + [secrets.choice(alphabet) for _ in range(length - len(required))]
    secrets.SystemRandom().shuffle(chars)
    return "".join(chars)


def _send_password_email_sync(config: dict, recipient_email: str, username: str, temp_password: str, action: str) -> None:
    msg = build_password_email(config, recipient_email, username, temp_password, action)
    send_smtp_message(config, msg)


async def send_user_password_email(db: AsyncSession, target_user: User, temp_password: str, action: str) -> None:
    config = await load_smtp_config(db)
    if not config["host"] or not config["from_email"]:
        raise_smtp_config_incomplete()
    await check_password_email_rate_limit(target_user.id)
    try:
        await asyncio.to_thread(
            _send_password_email_sync,
            config,
            target_user.email,
            target_user.username,
            temp_password,
            action,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("Password email send failed for user_id=%s action=%s: %s", target_user.id, action, exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="邮件发送失败，请检查邮件服务器配置") from exc


async def _resolve_user_names(db: AsyncSession, user_ids: List[int]) -> dict[int, str]:
    ids = sorted({int(user_id) for user_id in user_ids if user_id is not None})
    if not ids:
        return {}
    result = await db.execute(select(User.id, User.username).where(User.id.in_(ids)))
    return {row.id: row.username for row in result.all()}


async def _resolve_group_names(db: AsyncSession, group_ids: List[int]) -> dict[int, str]:
    ids = sorted({int(group_id) for group_id in group_ids if group_id is not None})
    if not ids:
        return {}
    result = await db.execute(select(Group.id, Group.name).where(Group.id.in_(ids)))
    return {row.id: row.name for row in result.all()}


async def _authorization_audit_item(db: AsyncSession, auth: Authorization) -> dict:
    return {
        "id": auth.id,
        "entity_type": auth.entity_type,
        "entity_id": auth.entity_id,
        "target_type": auth.target_type,
        "target_ids": list(auth.target_ids or []),
        "target_names": await resolve_target_names(db, auth.target_type, auth.target_ids),
        "permissions": list(auth.permissions or []),
    }


# ============== User APIs ==============
@router.get("", response_model=UserListResponse)
async def list_users(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("view_users")),
):
    """List all users with pagination and search"""
    query = select(User)

    # Apply filters
    if search:
        query = query.where(
            or_(
                User.username.ilike(f"%{search}%"),
                User.email.ilike(f"%{search}%"),
                User.full_name.ilike(f"%{search}%"),
            )
        )

    if is_active is not None:
        query = query.where(User.is_active == is_active)

    meta = await get_pagination_meta(db, query, page, limit)

    # Apply pagination
    query = query.offset((page - 1) * limit).limit(limit)
    query = query.order_by(User.created_at.desc())

    result = await db.execute(query)
    users = result.scalars().all()

    # Batch fetch groups for all users
    user_ids = [u.id for u in users]
    if user_ids:
        groups_result = await db.execute(
            select(UserGroup, Group).join(Group, Group.id == UserGroup.group_id).where(UserGroup.user_id.in_(user_ids))
        )
        user_groups_map: dict[int, list[dict]] = {}
        for ug, g in groups_result.all():
            user_groups_map.setdefault(ug.user_id, []).append({"id": g.id, "name": g.name})
    else:
        user_groups_map = {}

    user_responses = [
        {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "full_name": user.full_name,
            "phone": user.phone,
            "is_active": user.is_active,
            "mfa_enabled": user.mfa_enabled,
            "mfa_bound": bool(user.mfa_secret),
            "avatar_url": user.avatar_url,
            "last_login_at": user.last_login_at,
            "created_at": user.created_at,
            "groups": user_groups_map.get(user.id, []),
        }
        for user in users
    ]

    return UserListResponse(
        data=user_responses,
        meta=meta,
    )


@router.post("", response_model=UserDetailResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    data: UserCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("user_mgmt")),
):
    """Create a new user (admin only)"""
    ip = request.client.host if request.client else None
    try:
        # Check if username exists
        existing = await db.execute(
            select(User).where(User.username == data.username)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="用户名已存在"
            )

        # Check if email exists
        existing = await db.execute(
            select(User).where(User.email == data.email)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="邮箱已被使用"
            )

        if data.password_method not in {"manual", "auto"}:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不支持的密码设置方式")

        temp_password = None
        initial_password = data.password
        if data.password_method == "auto":
            if not data.send_email:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="自动生成密码必须发送邮件给用户")
            temp_password = await generate_temporary_password(db)
            initial_password = temp_password
        elif not initial_password:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请输入密码")

        is_valid, errors = await validate_password_strength_from_settings(initial_password, db)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="; ".join(errors)
            )

        # Create user (MFA enabled but no secret — user binds on first login)
        initial_password_hash = get_password_hash(initial_password)
        user = User(
            username=data.username,
            email=data.email,
            full_name=data.full_name,
            phone=data.phone,
            password_hash=initial_password_hash,
            is_active=data.is_active,
            mfa_enabled=data.mfa_enabled,
            must_change_password=data.must_change_password,
        )

        db.add(user)
        await db.flush()
        await record_password_history(initial_password_hash, user.id, db)

        # Add user to groups
        if data.group_ids:
            for group_id in data.group_ids:
                user_group = UserGroup(user_id=user.id, group_id=group_id)
                db.add(user_group)

        await db.commit()
        await db.refresh(user)

        # Fetch groups after commit
        groups_result = await db.execute(
            select(Group).join(UserGroup).where(UserGroup.user_id == user.id)
        )
        groups = groups_result.scalars().all()

        await log_operation(
            db, current_user.id, "create", "user", user.id,
            details={
                "username": user.username,
                "email": user.email,
                "is_active": user.is_active,
                "mfa_enabled": user.mfa_enabled,
                "mfa_bound": bool(user.mfa_secret),
                "must_change_password": user.must_change_password,
                "group_ids": data.group_ids or [],
            },
            ip_address=ip,
        )
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        await log_operation(
            db, current_user.id, "create", "user", 0,
            details={"username": data.username, "error": str(e)},
            ip_address=ip, status="failed",
        )
        raise

    # User is already committed at this point. Email sending happens on a
    # separate, already-closed-transaction path — a failure here must not
    # undo the user that was just created; report it back to the admin instead.
    email_sent = None
    if temp_password and data.send_email:
        try:
            await send_user_password_email(db, user, temp_password, "create")
            email_sent = True
        except HTTPException:
            email_sent = False

    return UserDetailResponse(
        data=UserResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            full_name=user.full_name,
            phone=user.phone,
            is_active=user.is_active,
            mfa_enabled=user.mfa_enabled,
            mfa_bound=bool(user.mfa_secret),
            avatar_url=user.avatar_url,
            last_login_at=user.last_login_at,
            created_at=user.created_at,
            groups=[{"id": g.id, "name": g.name} for g in groups],
        ),
        email_sent=email_sent,
        temp_password=temp_password if email_sent is False else None,
    )


@router.get("/{user_id}", response_model=UserDetailResponse)
async def get_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get user by ID — anyone can view self, others require user_mgmt"""
    if user_id != current_user.id and not current_user.is_superuser:
        perms = await get_user_permissions(current_user, db)
        if "user_mgmt" not in perms:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="缺少 user_mgmt 权限"
            )

    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )

    # Get user groups
    groups_result = await db.execute(
        select(Group).join(UserGroup).where(UserGroup.user_id == user.id)
    )
    groups = groups_result.scalars().all()

    return UserDetailResponse(
        data=UserResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            full_name=user.full_name,
            phone=user.phone,
            is_active=user.is_active,
            mfa_enabled=user.mfa_enabled,
            mfa_bound=bool(user.mfa_secret),
            avatar_url=user.avatar_url,
            last_login_at=user.last_login_at,
            created_at=user.created_at,
            groups=[{"id": g.id, "name": g.name} for g in groups],
        )
    )


@router.put("/{user_id}", response_model=UserDetailResponse)
async def update_user(
    user_id: int,
    data: UserUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update user information — self-update allowed, others require user_mgmt"""
    ip = request.client.host if request.client else None

    perms = await get_user_permissions(current_user, db)
    has_user_mgmt = current_user.is_superuser or "user_mgmt" in perms
    is_self_update = user_id == current_user.id

    if not is_self_update and not has_user_mgmt:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="缺少 user_mgmt 权限"
        )

    admin_only_fields = {
        "group_ids",
        "is_active",
        "is_superuser",
        "mfa_enabled",
    }
    submitted_fields = data.model_dump(exclude_unset=True)
    admin_field_updates = admin_only_fields.intersection(submitted_fields.keys())
    if admin_field_updates and not has_user_mgmt:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="缺少 user_mgmt 权限"
        )

    if "is_superuser" in submitted_fields and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只有超级管理员可以变更超级管理员状态"
        )

    if is_self_update and submitted_fields.get("is_active") is False:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能禁用自己"
        )

    if is_self_update and submitted_fields.get("is_superuser") is False and current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能移除自己的超级管理员权限"
        )

    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )

    # Track what changed
    changes = {}
    force_logout_after_commit = False
    if data.email is not None and data.email != user.email:
        # Check email uniqueness
        existing = await db.execute(
            select(User).where(User.email == data.email, User.id != user_id)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="邮箱已被使用"
            )
        changes["email"] = [user.email, data.email]
        user.email = data.email

    if data.full_name is not None and data.full_name != user.full_name:
        changes["full_name"] = [user.full_name, data.full_name]
        user.full_name = data.full_name

    if data.phone is not None and data.phone != user.phone:
        changes["phone"] = [user.phone, data.phone]
        user.phone = data.phone

    if data.avatar_url is not None and data.avatar_url != user.avatar_url:
        changes["avatar_url"] = [user.avatar_url, data.avatar_url]
        user.avatar_url = data.avatar_url

    if data.is_active is not None and data.is_active != user.is_active:
        changes["is_active"] = [user.is_active, data.is_active]
        force_logout_after_commit = user.is_active and not data.is_active
        user.is_active = data.is_active

    if data.mfa_enabled is not None and data.mfa_enabled != user.mfa_enabled:
        mfa_bound_before = bool(user.mfa_secret)
        changes["mfa_enabled"] = [user.mfa_enabled, data.mfa_enabled]
        user.mfa_enabled = data.mfa_enabled
        if not data.mfa_enabled:
            # Clear secret when disabling MFA
            user.mfa_secret = None
        changes["mfa_bound"] = [mfa_bound_before, bool(user.mfa_secret)]

    if data.is_superuser is not None and data.is_superuser != user.is_superuser:
        changes["is_superuser"] = [user.is_superuser, data.is_superuser]
        user.is_superuser = data.is_superuser

    group_change_details = None

    # Update groups only when membership actually changes. The edit form may
    # submit the existing group_ids together with unrelated profile fields.
    if data.group_ids is not None:
        current_user_groups = (await db.execute(select(UserGroup).where(UserGroup.user_id == user_id))).scalars().all()
        current_group_ids = sorted(ug.group_id for ug in current_user_groups)
        new_group_ids = sorted(data.group_ids)
        if current_group_ids != new_group_ids:
            changes["group_ids"] = [current_group_ids, new_group_ids]
            added_group_ids = sorted(set(new_group_ids) - set(current_group_ids))
            removed_group_ids = sorted(set(current_group_ids) - set(new_group_ids))
            group_names = await _resolve_group_names(db, current_group_ids + new_group_ids)
            group_change_details = {
                "before_group_ids": current_group_ids,
                "before_group_names": [group_names.get(group_id, str(group_id)) for group_id in current_group_ids],
                "after_group_ids": new_group_ids,
                "after_group_names": [group_names.get(group_id, str(group_id)) for group_id in new_group_ids],
                "added_group_ids": added_group_ids,
                "added_group_names": [group_names.get(group_id, str(group_id)) for group_id in added_group_ids],
                "removed_group_ids": removed_group_ids,
                "removed_group_names": [group_names.get(group_id, str(group_id)) for group_id in removed_group_ids],
            }
            # Remove existing groups
            for ug in current_user_groups:
                await db.delete(ug)

            # Add new groups
            for group_id in data.group_ids:
                user_group = UserGroup(user_id=user.id, group_id=group_id)
                db.add(user_group)

    await db.commit()
    if force_logout_after_commit:
        await force_logout_user(user_id)
        await _publish_force_logout_event(user_id, "user_disabled", "账号已被管理员禁用，请重新登录")
    await db.refresh(user)

    if changes:
        details = {"changes": changes, "username": user.username}
        if group_change_details:
            details.update(group_change_details)
        await log_operation(
            db, current_user.id, "update", "user", user_id,
            details=details,
            ip_address=ip,
        )

    # Get updated groups
    groups_result = await db.execute(
        select(Group).join(UserGroup).where(UserGroup.user_id == user.id)
    )
    groups = groups_result.scalars().all()

    return UserDetailResponse(
        data=UserResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            full_name=user.full_name,
            phone=user.phone,
            is_active=user.is_active,
            mfa_enabled=user.mfa_enabled,
            mfa_bound=bool(user.mfa_secret),
            avatar_url=user.avatar_url,
            last_login_at=user.last_login_at,
            created_at=user.created_at,
            groups=[{"id": g.id, "name": g.name} for g in groups],
        )
    )


@router.delete("/{user_id}", response_model=ResponseBase)
async def delete_user(
    user_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("user_mgmt")),
):
    """Delete user (admin only)"""
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

    if user.username == "admin":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="默认用户禁止删除"
        )

    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能删除自己"
        )

    username = user.username

    # Capture direct authorizations before cleanup for audit logging.
    auth_result = await db.execute(
        select(Authorization).where(Authorization.entity_id == user_id, Authorization.entity_type == "user")
    )
    direct_authorizations = auth_result.scalars().all()
    deleted_authorization_items = [
        await _authorization_audit_item(db, auth)
        for auth in direct_authorizations
    ]

    # Clean up user-group associations
    ug_result = await db.execute(
        select(UserGroup).where(UserGroup.user_id == user_id)
    )
    for ug in ug_result.scalars().all():
        await db.delete(ug)

    # Delete authorizations belonging to this user
    for auth in direct_authorizations:
        await db.delete(auth)

    # FK references to other tables are handled by ON DELETE SET NULL
    await db.delete(user)
    await db.commit()
    await force_logout_user(user_id)

    await log_operation(
        db, current_user.id, "delete", "user", user_id,
        details={
            "username": username,
            "deleted_authorization_count": len(deleted_authorization_items),
            "deleted_authorizations": deleted_authorization_items,
        },
        ip_address=ip,
    )

    if deleted_authorization_items:
        await log_operation(
            db, current_user.id, "delete", "authorization", 0,
            details={
                "action": "delete_user_authorizations",
                "name": username,
                "username": username,
                "count": len(deleted_authorization_items),
                "authorizations": deleted_authorization_items,
            },
            ip_address=ip,
        )

    return ResponseBase(message="用户已删除")
