"""In-app notifications API."""
from __future__ import annotations

from datetime import datetime, timezone
from math import ceil
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_user_permissions
from app.core.events import publish_user_event
from app.database import get_db
from app.models import Notification, NotificationReceipt, User, UserGroup


router = APIRouter(prefix="/notifications", tags=["站内信"])


class NotificationCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=120)
    content: str = Field(..., min_length=1, max_length=5000)
    recipient_scope: Literal["all", "users", "groups"] = "users"
    user_ids: list[int] = Field(default_factory=list)
    group_ids: list[int] = Field(default_factory=list)


def _utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def _can_send_notifications(current_user: User, db: AsyncSession) -> bool:
    if current_user.is_superuser:
        return True
    permissions = await get_user_permissions(current_user, db)
    return bool({"manage", "authorize"} & set(permissions))


async def _resolve_recipient_ids(data: NotificationCreate, current_user: User, db: AsyncSession) -> list[int]:
    if data.recipient_scope == "all":
        result = await db.execute(
            select(User.id)
            .where(User.is_active == True)
            .where(User.id != current_user.id)
        )
        return sorted({row[0] for row in result.all()})

    if data.recipient_scope == "users":
        if not data.user_ids:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请选择收件人")
        result = await db.execute(
            select(User.id)
            .where(User.id.in_(data.user_ids))
            .where(User.is_active == True)
        )
        return sorted({row[0] for row in result.all()})

    if not data.group_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请选择收件用户组")
    result = await db.execute(
        select(UserGroup.user_id)
        .join(User, User.id == UserGroup.user_id)
        .where(UserGroup.group_id.in_(data.group_ids))
        .where(User.is_active == True)
    )
    return sorted({row[0] for row in result.all()})


def _notification_item(receipt: NotificationReceipt, notification: Notification, sender: User | None) -> dict:
    return {
        "id": receipt.id,
        "notification_id": notification.id,
        "title": notification.title,
        "content": notification.content,
        "sender": {
            "id": sender.id,
            "username": sender.username,
            "full_name": sender.full_name,
        } if sender else None,
        "read_at": receipt.read_at.isoformat() if receipt.read_at else None,
        "created_at": receipt.created_at.isoformat() if receipt.created_at else notification.created_at.isoformat(),
    }


@router.get("")
async def list_notifications(
    status_filter: Literal["all", "unread", "read"] = Query("all", alias="status"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    filters = [NotificationReceipt.user_id == current_user.id]
    if status_filter == "unread":
        filters.append(NotificationReceipt.read_at == None)
    elif status_filter == "read":
        filters.append(NotificationReceipt.read_at != None)

    total_result = await db.execute(
        select(func.count(NotificationReceipt.id)).where(*filters)
    )
    total = total_result.scalar() or 0

    result = await db.execute(
        select(NotificationReceipt, Notification, User)
        .join(Notification, Notification.id == NotificationReceipt.notification_id)
        .outerjoin(User, User.id == Notification.sender_id)
        .where(*filters)
        .order_by(NotificationReceipt.created_at.desc(), NotificationReceipt.id.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    )
    items = [_notification_item(receipt, notification, sender) for receipt, notification, sender in result.all()]

    return {
        "code": 0,
        "message": "success",
        "data": items,
        "meta": {
            "total": total,
            "page": page,
            "limit": limit,
            "pages": ceil(total / limit) if total else 0,
        },
    }


@router.get("/unread-count")
async def unread_count(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(func.count(NotificationReceipt.id))
        .where(NotificationReceipt.user_id == current_user.id)
        .where(NotificationReceipt.read_at == None)
    )
    return {"code": 0, "message": "success", "data": {"count": result.scalar() or 0}}


@router.get("/can-send")
async def can_send_notifications(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return {"code": 0, "message": "success", "data": {"can_send": await _can_send_notifications(current_user, db)}}


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_notification(
    data: NotificationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not await _can_send_notifications(current_user, db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="缺少发送站内信权限")

    recipient_ids = await _resolve_recipient_ids(data, current_user, db)
    if not recipient_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="没有可接收的有效用户")

    notification = Notification(
        sender_id=current_user.id,
        title=data.title.strip(),
        content=data.content.strip(),
    )
    db.add(notification)
    await db.flush()

    receipts = []
    for user_id in recipient_ids:
        receipt = NotificationReceipt(notification_id=notification.id, user_id=user_id)
        db.add(receipt)
        receipts.append(receipt)

    await db.flush()
    await db.commit()
    await db.refresh(notification)

    event_data = {
        "id": notification.id,
        "title": notification.title,
        "content": notification.content,
        "sender": {
            "id": current_user.id,
            "username": current_user.username,
            "full_name": current_user.full_name,
        },
        "created_at": notification.created_at.isoformat(),
    }
    for receipt in receipts:
        await publish_user_event(receipt.user_id, "notification", {**event_data, "receipt_id": receipt.id})

    return {
        "code": 0,
        "message": "站内信已发送",
        "data": {
            "id": notification.id,
            "recipient_count": len(recipient_ids),
        },
    }


@router.post("/{receipt_id}/read")
async def mark_notification_read(
    receipt_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(NotificationReceipt)
        .where(NotificationReceipt.id == receipt_id)
        .where(NotificationReceipt.user_id == current_user.id)
    )
    receipt = result.scalar_one_or_none()
    if not receipt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="站内信不存在")

    if receipt.read_at is None:
        receipt.read_at = _utc_now_naive()
        await db.commit()

    return {"code": 0, "message": "已标记为已读", "data": {"id": receipt_id}}


@router.post("/read-all")
async def mark_all_notifications_read(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(NotificationReceipt)
        .where(NotificationReceipt.user_id == current_user.id)
        .where(NotificationReceipt.read_at == None)
    )
    receipts = result.scalars().all()
    now = _utc_now_naive()
    for receipt in receipts:
        receipt.read_at = now
    if receipts:
        await db.commit()

    return {"code": 0, "message": "全部已读", "data": {"updated": len(receipts)}}
