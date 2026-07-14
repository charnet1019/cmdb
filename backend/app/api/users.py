"""
User Management API
CRUD operations for users and user groups
"""
from typing import Optional, List
from datetime import datetime
from email.message import EmailMessage
from email.utils import formataddr
import asyncio
import secrets
import smtplib
import string
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_

from app.database import get_db
from app.models import User, Group, UserGroup, Authorization, Asset, Organization, PasswordChangeLog, Setting
from app.utils.audit import log_operation
from app.schemas import (
    UserCreate, UserUpdate, UserResponse, UserSimple, UserDetailResponse,
    UserListResponse, PaginationMeta,
    GroupCreate, GroupUpdate, GroupResponse, GroupSimple, GroupDetailResponse,
    GroupListResponse, PasswordResetRequest, ResponseBase
)
from app.api.deps import get_current_user, PermissionChecker, get_user_permissions
from app.core.security import get_password_hash, verify_password
from app.core.password_policy import validate_password_strength_from_settings
from app.core.session import force_logout_user
from app.core.events import publish_user_event
from app.core.encryption import decrypt_value
from app.config import settings


router = APIRouter(prefix="/users", tags=["用户管理"])


async def _publish_force_logout_event(user_id: int, reason: str, message: str) -> None:
    try:
        await publish_user_event(user_id, "force_logout", {"reason": reason, "message": message})
    except Exception:
        # Session invalidation remains authoritative; API 401 handling is the fallback.
        pass

SMTP_SETTING_KEYS = (
    "smtp_host",
    "smtp_port",
    "smtp_use_ssl",
    "smtp_username",
    "smtp_password",
    "smtp_from_email",
    "smtp_from_name",
)


def _setting_plain_value(setting: Setting | None, default=None):
    if not setting or not isinstance(setting.value, dict):
        return default
    return setting.value.get("value", default)


async def _get_setting_value(db: AsyncSession, key: str, default=None):
    result = await db.execute(select(Setting).where(Setting.key == key))
    return _setting_plain_value(result.scalar_one_or_none(), default)


async def generate_temporary_password(db: AsyncSession) -> str:
    min_length = int(await _get_setting_value(db, "password_min_length", settings.PASSWORD_MIN_LENGTH) or settings.PASSWORD_MIN_LENGTH)
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


def _decrypt_smtp_password(value: str | None) -> str:
    if not value:
        return ""
    if isinstance(value, str) and value.startswith("gAAAA"):
        return decrypt_value(value)
    return str(value)


async def _load_smtp_config(db: AsyncSession) -> dict:
    result = await db.execute(select(Setting).where(Setting.key.in_(SMTP_SETTING_KEYS)))
    setting_map = {setting.key: _setting_plain_value(setting, "") for setting in result.scalars().all()}
    return {
        "host": str(setting_map.get("smtp_host") or "").strip(),
        "port": int(setting_map.get("smtp_port") or 465),
        "use_ssl": bool(setting_map.get("smtp_use_ssl", True)),
        "username": str(setting_map.get("smtp_username") or "").strip(),
        "password": _decrypt_smtp_password(setting_map.get("smtp_password")),
        "from_email": str(setting_map.get("smtp_from_email") or "").strip(),
        "from_name": str(setting_map.get("smtp_from_name") or "CMDB").strip() or "CMDB",
    }


def _send_password_email_sync(config: dict, recipient_email: str, username: str, temp_password: str, action: str) -> None:
    action_label = "创建" if action == "create" else "重置"
    msg = EmailMessage()
    msg["Subject"] = f"CMDB 账号密码已{action_label}"
    msg["From"] = formataddr((config["from_name"], config["from_email"]))
    msg["To"] = recipient_email
    msg.set_content(
        f"您好，\n\n"
        f"您的 CMDB 账号密码已{action_label}。\n\n"
        f"用户名：{username}\n"
        f"临时密码：{temp_password}\n\n"
        f"请登录后立即修改密码。\n"
    )

    smtp_cls = smtplib.SMTP_SSL if config["use_ssl"] else smtplib.SMTP
    with smtp_cls(config["host"], config["port"], timeout=10) as server:
        if config["username"]:
            server.login(config["username"], config["password"])
        server.send_message(msg)


async def send_user_password_email(db: AsyncSession, target_user: User, temp_password: str, action: str) -> None:
    config = await _load_smtp_config(db)
    if not config["host"] or not config["from_email"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="邮件服务器未配置完整，请先在系统设置中配置 SMTP 服务器和发件人邮箱")
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
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"邮件发送失败: {exc}") from exc


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


async def _resolve_authorization_target_names(db: AsyncSession, auth: Authorization) -> str:
    if auth.target_type == "asset":
        result = await db.execute(select(Asset.name).where(Asset.id.in_(auth.target_ids or [])))
        names = [row[0] for row in result.all()]
    else:
        names = []
        target_ids = auth.target_ids or []
        if "__all__" in target_ids:
            names.append("Default")
        org_ids = [int(target_id) for target_id in target_ids if str(target_id).isdigit()]
        if org_ids:
            result = await db.execute(select(Organization.name).where(Organization.id.in_(org_ids)))
            names.extend(row[0] for row in result.all())
    if len(names) <= 3:
        return ", ".join(names) if names else str(auth.target_ids or [])
    return ", ".join(names[:3]) + f" 等{len(names)}个"


async def _authorization_audit_item(db: AsyncSession, auth: Authorization) -> dict:
    return {
        "id": auth.id,
        "entity_type": auth.entity_type,
        "entity_id": auth.entity_id,
        "target_type": auth.target_type,
        "target_ids": list(auth.target_ids or []),
        "target_names": await _resolve_authorization_target_names(db, auth),
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

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()

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
        meta=PaginationMeta(
            total=total,
            page=page,
            limit=limit,
            pages=(total + limit - 1) // limit,
        )
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
        user = User(
            username=data.username,
            email=data.email,
            full_name=data.full_name,
            phone=data.phone,
            password_hash=get_password_hash(initial_password),
            is_active=data.is_active,
            mfa_enabled=data.mfa_enabled,
            must_change_password=True,
        )

        db.add(user)
        await db.flush()

        # Add user to groups
        if data.group_ids:
            for group_id in data.group_ids:
                user_group = UserGroup(user_id=user.id, group_id=group_id)
                db.add(user_group)

        if temp_password and data.send_email:
            await send_user_password_email(db, user, temp_password, "create")

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
                "group_ids": data.group_ids or [],
            },
            ip_address=ip,
        )

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

    if data.method == "manual" and data.new_password:
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
        user.password_hash = get_password_hash(data.new_password)
        temp_password = None
    else:
        temp_password = await generate_temporary_password(db)
        user.password_hash = get_password_hash(temp_password)

    if data.force_change:
        user.must_change_password = True

    email_sent = False
    if temp_password and data.send_email:
        try:
            await send_user_password_email(db, user, temp_password, "reset")
        except HTTPException:
            await db.rollback()
            raise
        email_sent = True

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


# ============== Group APIs ==============
group_router = APIRouter(prefix="/groups", tags=["用户组管理"])


@group_router.get("", response_model=GroupListResponse)
async def list_groups(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("view_users")),
):
    """List all user groups"""
    query = select(Group)

    if search:
        query = query.where(Group.name.ilike(f"%{search}%"))

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # Apply pagination
    query = query.offset((page - 1) * limit).limit(limit)
    query = query.order_by(Group.created_at.desc())

    result = await db.execute(query)
    groups = result.scalars().all()

    # Batch fetch member counts
    group_ids = [g.id for g in groups]
    member_counts: dict[int, int] = {}
    if group_ids:
        counts_result = await db.execute(
            select(UserGroup.group_id, func.count()).where(UserGroup.group_id.in_(group_ids)).group_by(UserGroup.group_id)
        )
        member_counts = dict(counts_result.all())

    group_responses = [
        {
            "id": group.id,
            "name": group.name,
            "description": group.description,
            "is_default": group.is_default,
            "created_at": group.created_at,
            "member_count": member_counts.get(group.id, 0),
        }
        for group in groups
    ]

    return GroupListResponse(
        data=group_responses,
        meta=PaginationMeta(
            total=total,
            page=page,
            limit=limit,
            pages=(total + limit - 1) // limit,
        )
    )


@group_router.post("", response_model=GroupDetailResponse, status_code=status.HTTP_201_CREATED)
async def create_group(
    data: GroupCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("user_mgmt")),
):
    """Create a new user group"""
    ip = request.client.host if request.client else None
    # Check if name exists
    existing = await db.execute(
        select(Group).where(Group.name == data.name)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户组名称已存在"
        )

    group = Group(
        name=data.name,
        description=data.description,
    )

    db.add(group)
    await db.flush()

    initial_member_ids = list(data.initial_member_ids or [])

    # Add initial members
    if initial_member_ids:
        for user_id in initial_member_ids:
            user_group = UserGroup(user_id=user_id, group_id=group.id)
            db.add(user_group)

    await db.commit()
    await db.refresh(group)

    await log_operation(
        db, current_user.id, "create", "group", group.id,
        details={
            "name": group.name,
            "initial_member_ids": initial_member_ids,
            "initial_member_count": len(initial_member_ids),
        },
        ip_address=ip,
    )

    return GroupDetailResponse(
        data=GroupResponse(
            id=group.id,
            name=group.name,
            description=group.description,
            created_at=group.created_at,
            member_count=len(data.initial_member_ids or []),
        )
    )


@group_router.delete("/{group_id}", response_model=ResponseBase)
async def delete_group(
    group_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("user_mgmt")),
):
    """Delete a user group"""
    ip = request.client.host if request.client else None
    result = await db.execute(
        select(Group).where(Group.id == group_id)
    )
    group = result.scalar_one_or_none()

    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户组不存在"
        )

    if group.is_default:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="默认用户组无法被删除"
        )

    # Check if group has members — require empty before deletion
    member_count_result = await db.execute(
        select(func.count()).select_from(UserGroup).where(UserGroup.group_id == group_id)
    )
    member_count = member_count_result.scalar_one()
    if member_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"用户组下还有 {member_count} 名成员，请先移除所有成员后再删除"
        )

    auth_count_result = await db.execute(
        select(func.count()).select_from(Authorization).where(
            Authorization.entity_type == "group",
            Authorization.entity_id == group_id,
        )
    )
    auth_count = auth_count_result.scalar_one()
    if auth_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"用户组还有 {auth_count} 条授权，请先删除授权后再删除用户组"
        )

    group_name = group.name
    await db.delete(group)
    await db.commit()

    await log_operation(
        db, current_user.id, "delete", "group", group_id,
        details={"name": group_name},
        ip_address=ip,
    )

    return ResponseBase(message="用户组已删除")


@group_router.get("/{group_id}/authorizations")
async def get_group_authorizations(
    group_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("view_users")),
):
    """Get group's asset authorizations"""
    # Check group exists
    result = await db.execute(select(Group).where(Group.id == group_id))
    group = result.scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="用户组不存在")

    # Get group authorizations
    auths_result = await db.execute(
        select(Authorization).where(
            Authorization.entity_type == "group",
            Authorization.entity_id == group_id,
            Authorization.is_active == True,
        )
    )
    auths = auths_result.scalars().all()

    # Collect asset IDs
    asset_ids = set()
    for auth in auths:
        if auth.target_type == "asset":
            asset_ids.update(auth.target_ids)

    # Batch fetch assets
    assets_map = {}
    if asset_ids:
        assets_result = await db.execute(select(Asset).where(Asset.id.in_(asset_ids)))
        for asset in assets_result.scalars().all():
            assets_map[asset.id] = asset

    # Build response — one entry per (auth, asset) pair
    auth_list = []
    for auth in auths:
        for target_id in auth.target_ids:
            asset = assets_map.get(target_id)
            if asset:
                auth_list.append({
                    "id": auth.id,
                    "asset_id": asset.id,
                    "asset_name": asset.name,
                    "asset_category": asset.category,
                    "permissions": auth.permissions,
                    "valid_until": auth.valid_until.isoformat() if auth.valid_until else None,
                    "status": "active" if auth.is_active else "inactive",
                })

    return {
        "code": 0,
        "data": auth_list,
        "total": len(auth_list),
    }


@group_router.put("/{group_id}", response_model=GroupDetailResponse)
async def update_group(
    group_id: int,
    request: Request,
    data: GroupUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("user_mgmt")),
):
    """Update a user group"""
    ip = request.client.host if request.client else None
    result = await db.execute(select(Group).where(Group.id == group_id))
    group = result.scalar_one_or_none()

    if not group:
        raise HTTPException(status_code=404, detail="用户组不存在")

    changes = {}
    if data.name is not None and data.name != group.name:
        # Check name uniqueness
        existing = await db.execute(
            select(Group).where(Group.name == data.name, Group.id != group_id)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="用户组名称已存在")
        changes["name"] = [group.name, data.name]
        group.name = data.name

    if data.description is not None and data.description != group.description:
        changes["description"] = [group.description, data.description]
        group.description = data.description

    await db.commit()
    await db.refresh(group)

    if changes:
        await log_operation(
            db, current_user.id, "update", "group", group_id,
            details={"changes": changes, "name": group.name},
            ip_address=ip,
        )

    # Get member count
    member_count_result = await db.execute(
        select(func.count()).select_from(UserGroup).where(UserGroup.group_id == group.id)
    )
    member_count = member_count_result.scalar() or 0

    return GroupDetailResponse(
        data=GroupResponse(
            id=group.id,
            name=group.name,
            description=group.description,
            created_at=group.created_at,
            member_count=member_count,
        )
    )


@group_router.get("/{group_id}/members")
async def get_group_members(
    group_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("view_users")),
):
    """Get members of a group"""
    result = await db.execute(select(Group).where(Group.id == group_id))
    group = result.scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="用户组不存在")

    # Get members
    members_result = await db.execute(
        select(User).join(UserGroup).where(UserGroup.group_id == group_id)
    )
    members = members_result.scalars().all()

    return {
        "code": 0,
        "data": [
            {
                "id": u.id,
                "username": u.username,
                "full_name": u.full_name,
                "email": u.email,
                "is_active": u.is_active,
            }
            for u in members
        ]
    }


@group_router.post("/{group_id}/members")
async def add_group_members(
    group_id: int,
    user_ids: List[int],
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("user_mgmt")),
):
    """Add members to a group"""
    ip = request.client.host if request.client else None
    result = await db.execute(select(Group).where(Group.id == group_id))
    group = result.scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="用户组不存在")

    added_user_ids = []
    skipped_user_ids = []
    for user_id in user_ids:
        # Check user exists
        user_result = await db.execute(select(User).where(User.id == user_id))
        if not user_result.scalar_one_or_none():
            skipped_user_ids.append(user_id)
            continue

        # Check if already member
        existing = await db.execute(
            select(UserGroup).where(
                UserGroup.group_id == group_id,
                UserGroup.user_id == user_id
            )
        )
        if existing.scalar_one_or_none():
            skipped_user_ids.append(user_id)
            continue

        user_group = UserGroup(user_id=user_id, group_id=group_id)
        db.add(user_group)
        added_user_ids.append(user_id)

    await db.commit()

    added = len(added_user_ids)
    if added > 0:
        name_map = await _resolve_user_names(db, list(user_ids))
        await log_operation(
            db, current_user.id, "add_group_members", "group", group_id,
            details={
                "name": group.name,
                "requested_user_ids": list(user_ids),
                "requested_user_names": [name_map.get(user_id, str(user_id)) for user_id in user_ids],
                "added_user_ids": added_user_ids,
                "added_user_names": [name_map.get(user_id, str(user_id)) for user_id in added_user_ids],
                "skipped_user_ids": skipped_user_ids,
                "skipped_user_names": [name_map.get(user_id, str(user_id)) for user_id in skipped_user_ids],
                "added": added,
            },
            ip_address=ip,
        )

    return {"code": 0, "message": f"已添加 {added} 名成员"}


@group_router.delete("/{group_id}/members/{user_id}")
async def remove_group_member(
    group_id: int,
    user_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("user_mgmt")),
):
    """Remove a member from a group"""
    ip = request.client.host if request.client else None
    result = await db.execute(
        select(UserGroup).where(
            UserGroup.group_id == group_id,
            UserGroup.user_id == user_id
        )
    )
    user_group = result.scalar_one_or_none()

    if not user_group:
        raise HTTPException(status_code=404, detail="成员不存在")

    # Get user and group names for logging
    user_result = await db.execute(select(User).where(User.id == user_id))
    user_obj = user_result.scalar_one_or_none()
    user_name = user_obj.username if user_obj else str(user_id)
    group_result = await db.execute(select(Group).where(Group.id == group_id))
    group_obj = group_result.scalar_one_or_none()
    group_name = group_obj.name if group_obj else str(group_id)

    await db.delete(user_group)
    await db.commit()

    await log_operation(
        db, current_user.id, "remove_group_member", "group", group_id,
        details={
            "user_id": user_id,
            "username": user_name,
            "group_id": group_id,
            "group_name": group_name,
        },
        ip_address=ip,
    )

    return ResponseBase(message="成员已移除")