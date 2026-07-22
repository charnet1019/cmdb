"""
Credential Management API
CRUD + decrypt operations for per-asset login credentials, plus OOB password decrypt.
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import Asset, Credential, User, PasswordChangeLog
from app.schemas import (
    CredentialCreate, CredentialUpdate, CredentialResponse, CredentialDecryptResponse,
    ResponseBase,
)
from app.api.deps import PermissionChecker, check_resource_permission, get_authorized_asset_ids
from app.api.assets import _client_ip
from app.core.encryption import encrypt_value, decrypt_value
from app.utils.audit import log_operation
from app.utils.rate_limit import check_credential_decrypt_rate_limit


cred_router = APIRouter(prefix="/credentials", tags=["凭证管理"])

# decrypt_oob_password lives under /assets/{asset_id}/decrypt-oob (not
# /credentials/...), so it needs its own router with the /assets prefix
# rather than cred_router.
oob_router = APIRouter(prefix="/assets", tags=["资产管理"])


class OOBDecryptResponse(BaseModel):
    """OOB password decrypt response"""
    oob_password: str


@cred_router.get("")
async def list_credentials(
    asset_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("view_pwd")),
):
    """List credentials for an asset"""
    query = select(Credential)

    if asset_id:
        asset_result = await db.execute(select(Asset).where(Asset.id == asset_id))
        asset = asset_result.scalar_one_or_none()
        if not asset:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="资产不存在",
            )
        await check_resource_permission(
            current_user, "view_pwd", "asset", asset_id, db,
            organization_id=asset.organization_id,
        )
        query = query.where(Credential.asset_id == asset_id)
    else:
        # Filter by authorized assets
        authorized_ids = await get_authorized_asset_ids(current_user, db, "view_pwd")
        if authorized_ids is not None and len(authorized_ids) == 0:
            return {"code": 0, "data": []}
        if authorized_ids is not None:
            query = query.where(Credential.asset_id.in_(authorized_ids))

    result = await db.execute(query)
    credentials = result.scalars().all()

    return {
        "code": 0,
        "data": [
            {
                "id": c.id,
                "asset_id": c.asset_id,
                "username": c.username,
                "credential_type": c.credential_type,
                "created_at": c.created_at,
            }
            for c in credentials
        ]
    }


@cred_router.post("", response_model=CredentialResponse, status_code=status.HTTP_201_CREATED)
async def create_credential(
    request: Request,
    data: CredentialCreate,
    asset_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("manage")),
):
    """Create a new credential for an asset"""
    # Verify asset exists
    result = await db.execute(
        select(Asset).where(Asset.id == asset_id)
    )
    asset = result.scalar_one_or_none()
    if not asset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="资产不存在"
        )

    # Check resource-level permission
    await check_resource_permission(
        current_user, "manage", "asset", asset_id, db,
        organization_id=asset.organization_id,
    )

    credential = Credential(
        asset_id=asset_id,
        username=data.username,
        password_encrypted=encrypt_value(data.password),
        credential_type=data.credential_type,
        extra_data=data.metadata,
    )
    db.add(credential)
    await db.flush()  # Get credential.id before committing

    # Log credential creation
    password_log = PasswordChangeLog(
        credential_id=credential.id,
        change_type="asset_credential",
        changed_by=current_user.id,
        ip_address=request.client.host if request.client else None,
    )
    db.add(password_log)

    await db.commit()
    await db.refresh(credential)

    await log_operation(
        db, current_user.id, "create", "credential", credential.id,
        details={
            "name": credential.username,
            "action": "create_credential",
            "asset_id": credential.asset_id,
            "asset_name": asset.name,
            "asset_category": asset.category,
            "credential_id": credential.id,
            "credential_username": credential.username,
            "credential_type": credential.credential_type,
        },
        ip_address=_client_ip(request),
    )

    return CredentialResponse(
        id=credential.id,
        asset_id=credential.asset_id,
        username=credential.username,
        credential_type=credential.credential_type,
        created_at=credential.created_at,
    )


@oob_router.post("/{asset_id}/decrypt-oob", response_model=OOBDecryptResponse)
async def decrypt_oob_password(
    asset_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("view_pwd")),
    request: Request = None,
):
    """Decrypt OOB password for host asset (requires view_pwd permission)"""
    await check_credential_decrypt_rate_limit(db, current_user.id)

    result = await db.execute(
        select(Asset).where(Asset.id == asset_id)
    )
    asset = result.scalar_one_or_none()

    if not asset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="资产不存在"
        )

    # Check resource-level permission
    await check_resource_permission(
        current_user, "view_pwd", "asset", asset_id, db,
        organization_id=asset.organization_id,
    )

    if not asset.oob_password_encrypted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="未找到 OOB 密码"
        )

    try:
        decrypted_password = decrypt_value(asset.oob_password_encrypted)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="解密失败"
        )

    await log_operation(
        db, current_user.id, "decrypt", "credential", 0,
        details={
            "name": asset.oob_username or "OOB",
            "action": "decrypt_oob_password",
            "asset_id": asset.id,
            "asset_name": asset.name,
            "asset_category": asset.category,
            "credential_username": asset.oob_username,
            "credential_type": "oob",
        },
        ip_address=_client_ip(request),
    )

    return OOBDecryptResponse(oob_password=decrypted_password)


@cred_router.post("/{credential_id}/decrypt", response_model=CredentialDecryptResponse)
async def decrypt_credential(
    credential_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("view_pwd")),
    request: Request = None,
):
    """Decrypt credential password (requires view_pwd permission)"""
    await check_credential_decrypt_rate_limit(db, current_user.id)

    result = await db.execute(
        select(Credential).where(Credential.id == credential_id)
    )
    credential = result.scalar_one_or_none()

    if not credential:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="凭证不存在"
        )

    asset_result = await db.execute(select(Asset).where(Asset.id == credential.asset_id))
    asset = asset_result.scalar_one_or_none()

    # Check resource-level permission on the asset
    await check_resource_permission(
        current_user, "view_pwd", "asset", credential.asset_id, db,
        organization_id=asset.organization_id if asset else None,
    )

    try:
        decrypted_password = decrypt_value(credential.password_encrypted)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="解密失败"
        )

    await log_operation(
        db, current_user.id, "decrypt", "credential", credential.id,
        details={
            "name": credential.username,
            "action": "decrypt_credential",
            "asset_id": credential.asset_id,
            "asset_name": asset.name if asset else None,
            "asset_category": asset.category if asset else None,
            "credential_id": credential.id,
            "credential_username": credential.username,
            "credential_type": credential.credential_type,
        },
        ip_address=_client_ip(request),
    )

    return CredentialDecryptResponse(
        id=credential.id,
        username=credential.username,
        password=decrypted_password,
    )


@cred_router.put("/{credential_id}", response_model=CredentialResponse)
async def update_credential(
    credential_id: int,
    data: CredentialUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("manage")),
):
    """Update a credential"""
    result = await db.execute(
        select(Credential).where(Credential.id == credential_id)
    )
    credential = result.scalar_one_or_none()

    if not credential:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="凭证不存在"
        )

    asset_result = await db.execute(select(Asset).where(Asset.id == credential.asset_id))
    asset = asset_result.scalar_one_or_none()

    # Check resource-level permission on the asset
    await check_resource_permission(
        current_user, "manage", "asset", credential.asset_id, db,
        organization_id=asset.organization_id if asset else None,
    )

    changes = {}

    def record_credential_change(field: str, before, after) -> None:
        if before != after:
            changes[field] = [before, after]

    # Update fields
    if data.username is not None:
        record_credential_change("username", credential.username, data.username)
        credential.username = data.username
    if data.password is not None:
        changes["password"] = ["未变更", "已更新"]
        credential.password_encrypted = encrypt_value(data.password)

        # Log credential password change
        password_log = PasswordChangeLog(
            credential_id=credential_id,
            change_type="asset_credential",
            changed_by=current_user.id,
            ip_address=request.client.host if request.client else None,
        )
        db.add(password_log)
    if data.metadata is not None:
        record_credential_change("metadata", credential.extra_data, data.metadata)
        credential.extra_data = data.metadata

    await db.commit()
    await db.refresh(credential)

    if changes:
        await log_operation(
            db, current_user.id, "update", "credential", credential.id,
            details={
                "name": credential.username,
                "action": "update_credential",
                "asset_id": credential.asset_id,
                "asset_name": asset.name if asset else None,
                "asset_category": asset.category if asset else None,
                "credential_id": credential.id,
                "credential_username": credential.username,
                "credential_type": credential.credential_type,
                "changes": changes,
            },
            ip_address=_client_ip(request),
        )

    return CredentialResponse(
        id=credential.id,
        asset_id=credential.asset_id,
        username=credential.username,
        credential_type=credential.credential_type,
        created_at=credential.created_at,
    )


@cred_router.delete("/{credential_id}", response_model=ResponseBase)
async def delete_credential(
    credential_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("manage")),
    request: Request = None,
):
    """Delete a credential"""
    result = await db.execute(
        select(Credential).where(Credential.id == credential_id)
    )
    credential = result.scalar_one_or_none()

    if not credential:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="凭证不存在"
        )

    asset_result = await db.execute(select(Asset).where(Asset.id == credential.asset_id))
    asset = asset_result.scalar_one_or_none()

    # Check resource-level permission on the asset
    await check_resource_permission(
        current_user, "manage", "asset", credential.asset_id, db,
        organization_id=asset.organization_id if asset else None,
    )

    credential_username = credential.username
    credential_type = credential.credential_type
    credential_asset_id = credential.asset_id
    asset_category = asset.category if asset else None
    asset_name = asset.name if asset else None

    await db.delete(credential)
    await db.commit()

    await log_operation(
        db, current_user.id, "delete", "credential", credential_id,
        details={
            "name": credential_username,
            "action": "delete_credential",
            "asset_id": credential_asset_id,
            "asset_name": asset_name,
            "asset_category": asset_category,
            "credential_id": credential_id,
            "credential_username": credential_username,
            "credential_type": credential_type,
        },
        ip_address=_client_ip(request),
    )

    return ResponseBase(message="凭证已删除")
