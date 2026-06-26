"""
API Dependencies
Dependency injection for FastAPI routes
"""
from datetime import datetime
from typing import Optional, List, Set, Dict
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text, func, or_, cast, String

from app.database import get_db
from app.core.security import decode_access_token
from app.models import User, Authorization, Group, UserGroup, Organization, Asset


# HTTP Bearer security scheme
security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Get current authenticated user from JWT token
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无法验证凭据",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token = credentials.credentials
    payload = decode_access_token(token)

    if payload is None:
        raise credentials_exception

    user_id: Optional[int] = payload.get("sub")
    if user_id is None:
        raise credentials_exception

    # Query user from database
    result = await db.execute(
        select(User).where(User.id == int(user_id))
    )
    user = result.scalar_one_or_none()

    if user is None:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="用户已被禁用"
        )

    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Verify user is active
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="用户已被禁用"
        )
    return current_user


async def get_current_superuser(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Verify user is superuser
    """
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )
    return current_user


# Permission hierarchy: higher permissions imply lower ones
IMPLIED_PERMISSIONS: Dict[str, Set[str]] = {
    "manage": {"view", "manage_pwd"},
    "manage_pwd": {"view_pwd"},
}

# Reverse map: to satisfy "view", also accept "manage"
PERMISSION_ALIASES: Dict[str, Set[str]] = {}
for higher, lowers in IMPLIED_PERMISSIONS.items():
    for lower in lowers:
        PERMISSION_ALIASES.setdefault(lower, set()).add(higher)


def _satisfies_permission(have: str, need: str) -> bool:
    """Check if having `have` satisfies needing `need` (via implication)."""
    if have == need:
        return True
    return need in IMPLIED_PERMISSIONS.get(have, set())


def _permission_variants(need: str) -> Set[str]:
    """Return all permission values that satisfy `need` (transitive)."""
    result = {need}
    # Walk up the reverse chain: manage → manage_pwd → view_pwd
    current = {need}
    while True:
        parents: Set[str] = set()
        for p in current:
            parents.update(PERMISSION_ALIASES.get(p, set()))
        if not parents or parents.issubset(result):
            break
        result.update(parents)
        current = parents
    return result


async def get_user_permissions(
    user: User,
    db: AsyncSession,
) -> List[str]:
    """
    Get all permissions for a user (direct + group permissions)
    """
    if user.is_superuser:
        return [
            "view", "manage", "user_mgmt", "sys_config",
            "audit_log", "view_pwd", "manage_pwd"
        ]

    now = datetime.utcnow()

    # Direct user permissions
    user_auths_result = await db.execute(
        select(Authorization)
        .where(Authorization.entity_type == "user")
        .where(Authorization.entity_id == user.id)
        .where(Authorization.is_active == True)
        .where(
            (Authorization.valid_from == None) | (Authorization.valid_from <= now)
        )
        .where(
            (Authorization.valid_until == None) | (Authorization.valid_until >= now)
        )
    )
    user_auths = user_auths_result.scalars().all()

    # Get user groups
    groups_result = await db.execute(
        select(Group.id)
        .join(UserGroup, Group.id == UserGroup.group_id)
        .where(UserGroup.user_id == user.id)
    )
    group_ids = [g[0] for g in groups_result.all()]

    # Group permissions
    permissions = set()
    for auth in user_auths:
        if auth.permissions:
            permissions.update(auth.permissions)

    if group_ids:
        group_auths_result = await db.execute(
            select(Authorization)
            .where(Authorization.entity_type == "group")
            .where(Authorization.entity_id.in_(group_ids))
            .where(Authorization.is_active == True)
            .where(
                (Authorization.valid_from == None) | (Authorization.valid_from <= now)
            )
            .where(
                (Authorization.valid_until == None) | (Authorization.valid_until >= now)
            )
        )
        group_auths = group_auths_result.scalars().all()
        for auth in group_auths:
            if auth.permissions:
                permissions.update(auth.permissions)

    # Expand permissions transitively (e.g., manage → manage_pwd → view_pwd)
    expanded = set(permissions)
    changed = True
    while changed:
        changed = False
        for perm in list(expanded):
            implied = IMPLIED_PERMISSIONS.get(perm, set())
            if not implied.issubset(expanded):
                expanded.update(implied)
                changed = True
    return list(expanded)


class PermissionChecker:
    """
    Permission checker dependency
    Usage: @Depends(PermissionChecker("view"))
    """

    def __init__(self, permission: str):
        self.permission = permission

    async def __call__(
        self,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> User:
        if current_user.is_superuser:
            return current_user

        permissions = await get_user_permissions(current_user, db)

        if not any(_satisfies_permission(p, self.permission) for p in permissions):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"缺少 '{self.permission}' 权限"
            )

        return current_user


async def check_resource_permission(
    user: User,
    permission: str,
    target_type: str,
    resource_id: str,
    db: AsyncSession,
    organization_id: Optional[int] = None,
) -> bool:
    """Check if user has a specific permission for a specific resource.

    Returns True if authorized. Raises 403 if not.
    """
    if user.is_superuser:
        return True

    now = datetime.utcnow()
    satisfying_perms = _permission_variants(permission)
    perm_check = or_(*[text(f"permissions @> '\"{p}\"'::jsonb") for p in satisfying_perms])

    # Check direct authorization on the resource
    result = await db.execute(
        select(Authorization)
        .where(or_(
            text(f"(entity_type = 'user' AND entity_id = {user.id})"),
            text(f"(entity_type = 'group' AND entity_id IN (SELECT group_id FROM user_groups WHERE user_id = {user.id}))"),
        ))
        .where(Authorization.target_type == target_type)
        .where(
            or_(
                text(f"target_ids @> '{resource_id}'::jsonb"),
                text(f"target_ids @> '__all__'::jsonb"),
            )
        )
        .where(Authorization.is_active == True)
        .where(
            (Authorization.valid_from == None) | (Authorization.valid_from <= now)
        )
        .where(
            (Authorization.valid_until == None) | (Authorization.valid_until >= now)
        )
        .where(perm_check)
        .limit(1)
    )

    if result.scalar_one_or_none():
        return True

    # For asset resources, also check organization-level authorization
    if target_type == "asset" and organization_id is not None:
        result = await db.execute(
            select(Authorization)
            .where(or_(
                text(f"(entity_type = 'user' AND entity_id = {user.id})"),
                text(f"(entity_type = 'group' AND entity_id IN (SELECT group_id FROM user_groups WHERE user_id = {user.id}))"),
            ))
            .where(Authorization.target_type == "organization")
            .where(
                or_(
                    text(f"target_ids @> '{organization_id}'::jsonb"),
                    text(f"target_ids @> '__all__'::jsonb"),
                )
            )
            .where(Authorization.is_active == True)
            .where(
                (Authorization.valid_from == None) | (Authorization.valid_from <= now)
            )
            .where(
                (Authorization.valid_until == None) | (Authorization.valid_until >= now)
            )
            .where(perm_check)
            .limit(1)
        )

        if result.scalar_one_or_none():
            return True

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=f"缺少资源 '{permission}' 权限"
    )


async def get_authorized_asset_ids(
    user: User,
    db: AsyncSession,
    permission: str = "view",
) -> Optional[Set[str]]:
    """Get set of asset IDs the user has `permission` for.

    Returns None if user has full access (superuser or no authorizations exist).
    """
    if user.is_superuser:
        return None

    # Check if any authorizations exist at all
    count_result = await db.execute(select(func.count()).select_from(Authorization))
    total = count_result.scalar()
    if total == 0:
        return set()  # No authorizations configured → non-superuser sees nothing

    now = datetime.utcnow()
    satisfying_perms = _permission_variants(permission)

    # Direct asset authorizations
    asset_ids: Set[str] = set()

    # Get user's group IDs
    groups_result = await db.execute(
        select(Group.id)
        .join(UserGroup, Group.id == UserGroup.group_id)
        .where(UserGroup.user_id == user.id)
    )
    group_ids = [g[0] for g in groups_result.all()]

    # Entity IDs to check
    entity_conditions_list = [(Authorization.entity_type == "user", Authorization.entity_id == user.id)]
    if group_ids:
        entity_conditions_list.append((Authorization.entity_type == "group", Authorization.entity_id.in_(group_ids)))

    for ec in entity_conditions_list:
        result = await db.execute(
            select(
                cast(
                    func.jsonb_array_elements_text(Authorization.target_ids),
                    String,
                )
            )
            .where(*ec)
            .where(Authorization.target_type == "asset")
            .where(Authorization.is_active == True)
            .where(
                (Authorization.valid_from == None) | (Authorization.valid_from <= now)
            )
            .where(
                (Authorization.valid_until == None) | (Authorization.valid_until >= now)
            )
            .where(
                or_(*[text(f"permissions @> '\"{p}\"'::jsonb") for p in satisfying_perms])
            )
        )
        for row in result.scalars().all():
            if row == "__all__":
                return None  # All assets authorized
            asset_ids.add(row)

    # Organization-level authorizations → find assets in descendant organizations
    org_ids: List[int] = []
    for ec in entity_conditions_list:
        result = await db.execute(
            select(
                cast(
                    func.jsonb_array_elements_text(Authorization.target_ids),
                    String,
                )
            )
            .where(*ec)
            .where(Authorization.target_type == "organization")
            .where(Authorization.is_active == True)
            .where(
                (Authorization.valid_from == None) | (Authorization.valid_from <= now)
            )
            .where(
                (Authorization.valid_until == None) | (Authorization.valid_until >= now)
            )
            .where(
                or_(*[text(f"permissions @> '\"{p}\"'::jsonb") for p in satisfying_perms])
            )
        )
        for row in result.scalars().all():
            if row == "__all__":
                return None  # All orgs → all assets authorized
            try:
                org_ids.append(int(row))
            except (ValueError, TypeError):
                pass

    if org_ids:
        # Find the organization paths (including descendants)
        orgs_result = await db.execute(
            select(Organization.id, Organization.path).where(Organization.id.in_(org_ids))
        )
        org_paths = orgs_result.all()

        # Build LIKE patterns for descendants
        like_patterns = []
        for _, path in org_paths:
            if path:
                like_patterns.append(path + "/%")
                like_patterns.append(path)  # The org itself

        if like_patterns:
            # Get all descendant org IDs
            descendant_orgs_result = await db.execute(
                select(Organization.id).where(
                    or_(*[Organization.path.like(p) for p in like_patterns])
                )
            )
            descendant_org_ids = {row[0] for row in descendant_orgs_result.all()}

            if descendant_org_ids:
                # Assets in those organizations
                assets_result = await db.execute(
                    select(Asset.id).where(Asset.organization_id.in_(descendant_org_ids))
                )
                for row in assets_result.scalars().all():
                    asset_ids.add(row)

    return set(asset_ids) if asset_ids else set()  # Empty set = authorized but no assets
