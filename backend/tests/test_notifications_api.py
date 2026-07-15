"""Tests for GET /notifications, /notifications/sent, /notifications/can-send,
and POST /notifications/read-all.
"""
from datetime import datetime

import pytest

from tests.factories import FakeDB, FakeResult, user

from app.api import notifications as notifications_api
from app.models import Notification, NotificationReceipt


def _notification(**kwargs):
    data = {
        "id": 1,
        "sender_id": 1,
        "title": "维护通知",
        "content": "系统将于今晚维护",
        "created_at": datetime(2026, 1, 1),
    }
    data.update(kwargs)
    return Notification(**data)


def _receipt(**kwargs):
    data = {
        "id": 1,
        "notification_id": 1,
        "user_id": 2,
        "read_at": None,
        "created_at": datetime(2026, 1, 1),
    }
    data.update(kwargs)
    return NotificationReceipt(**data)


@pytest.mark.asyncio
async def test_list_notifications_returns_unread_items():
    receipt = _receipt(read_at=None)
    notification = _notification()
    sender = user(id=1, username="admin")

    db = FakeDB(
        FakeResult(scalar=1),
        FakeResult(all_rows=[(receipt, notification, sender)]),
    )

    response = await notifications_api.list_notifications(
        status_filter="unread", page=1, limit=20, db=db, current_user=user(id=2),
    )

    assert response["data"][0]["title"] == "维护通知"
    assert response["data"][0]["sender"]["username"] == "admin"
    assert response["data"][0]["read_at"] is None
    assert response["meta"]["total"] == 1


@pytest.mark.asyncio
async def test_list_notifications_handles_no_sender():
    receipt = _receipt()
    notification = _notification(sender_id=None)

    db = FakeDB(
        FakeResult(scalar=1),
        FakeResult(all_rows=[(receipt, notification, None)]),
    )

    response = await notifications_api.list_notifications(
        status_filter="all", page=1, limit=20, db=db, current_user=user(id=2),
    )

    assert response["data"][0]["sender"] is None


@pytest.mark.asyncio
async def test_list_sent_notifications_includes_recipient_count():
    notification = _notification()
    db = FakeDB(
        FakeResult(scalar=1),
        FakeResult(all_rows=[(notification, 5)]),
    )

    response = await notifications_api.list_sent_notifications(
        page=1, limit=20, db=db, current_user=user(id=1, username="admin"),
    )

    assert response["data"][0]["recipient_count"] == 5
    assert response["meta"]["total"] == 1


@pytest.mark.asyncio
async def test_can_send_notifications_reflects_permission_check(monkeypatch):
    async def fake_can_send(current_user, db):
        return True

    monkeypatch.setattr(notifications_api, "_can_send_notifications", fake_can_send)

    response = await notifications_api.can_send_notifications(db=FakeDB(), current_user=user())

    assert response["data"]["can_send"] is True


@pytest.mark.asyncio
async def test_mark_all_notifications_read_updates_unread_receipts():
    receipts = [_receipt(id=1, read_at=None), _receipt(id=2, read_at=None)]
    db = FakeDB(FakeResult(scalars=receipts))

    response = await notifications_api.mark_all_notifications_read(db=db, current_user=user(id=2))

    assert response["data"]["updated"] == 2
    assert all(r.read_at is not None for r in receipts)
    assert db.commits == 1


@pytest.mark.asyncio
async def test_mark_all_notifications_read_skips_commit_when_nothing_unread():
    db = FakeDB(FakeResult(scalars=[]))

    response = await notifications_api.mark_all_notifications_read(db=db, current_user=user(id=2))

    assert response["data"]["updated"] == 0
    assert db.commits == 0
