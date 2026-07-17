"""Tests for GET /logs/login, /logs/operation, /logs/password and POST /logs/cleanup."""
from datetime import datetime
from types import SimpleNamespace

import pytest

from tests.factories import FakeDB, FakeResult, user

from app.api import logs as logs_api
from app.api import logs_login as logs_login_api
from app.api import logs_operation as logs_operation_api
from app.api import logs_password as logs_password_api
from app.models import LoginLog, OperationLog, PasswordChangeLog


@pytest.mark.asyncio
async def test_list_login_logs_returns_items_meta_and_stats():
    items = [
        LoginLog(id=1, username="alice", ip_address="1.1.1.1", status="success", created_at=datetime(2026, 1, 1)),
        LoginLog(id=2, username="bob", ip_address="2.2.2.2", status="failed", failure_reason="密码错误", created_at=datetime(2026, 1, 1)),
    ]
    db = FakeDB(
        FakeResult(scalar=2),  # pagination count
        FakeResult(one_row=SimpleNamespace(today_count=2, success_count=1, failed_count=1)),
        FakeResult(scalars=items),
    )

    response = await logs_login_api.list_login_logs(
        page=1, limit=20, search=None, status=None, date_from=None, date_to=None,
        db=db, current_user=user(is_superuser=True),
    )

    assert response["code"] == 0
    assert len(response["data"]) == 2
    assert response["data"][1]["failure_reason"] == "密码错误"
    assert response["meta"].total == 2
    assert response["stats"]["today_total"] == 2
    assert response["stats"]["success_rate"] == 50.0
    assert response["stats"]["failed_count"] == 1


@pytest.mark.asyncio
async def test_list_login_logs_zero_logins_gives_zero_success_rate():
    db = FakeDB(
        FakeResult(scalar=0),
        FakeResult(one_row=SimpleNamespace(today_count=0, success_count=0, failed_count=0)),
        FakeResult(scalars=[]),
    )

    response = await logs_login_api.list_login_logs(
        page=1, limit=20, search=None, status=None, date_from=None, date_to=None,
        db=db, current_user=user(is_superuser=True),
    )

    assert response["stats"]["success_rate"] == 0
    assert response["data"] == []


@pytest.mark.asyncio
async def test_list_login_logs_ignores_malformed_date_filter():
    db = FakeDB(
        FakeResult(scalar=0),
        FakeResult(one_row=SimpleNamespace(today_count=0, success_count=0, failed_count=0)),
        FakeResult(scalars=[]),
    )

    # Should not raise despite an invalid ISO date string — silently ignored.
    response = await logs_login_api.list_login_logs(
        page=1, limit=20, search=None, status=None, date_from="not-a-date", date_to=None,
        db=db, current_user=user(is_superuser=True),
    )

    assert response["code"] == 0


@pytest.mark.asyncio
async def test_list_operation_logs_resolves_usernames():
    items = [OperationLog(id=1, user_id=1, action="create", resource_type="asset", resource_id=5, details={}, status="success", created_at=datetime(2026, 1, 1))]
    db = FakeDB(
        FakeResult(scalar=1),
        FakeResult(scalars=items),
        FakeResult(scalars=[user(id=1, username="alice")]),
    )

    response = await logs_operation_api.list_operation_logs(
        page=1, limit=20, search=None, action=None, user_id=None, date_from=None, date_to=None,
        db=db, current_user=user(is_superuser=True),
    )

    assert response["data"][0]["id"] == 1
    assert response["meta"].total == 1


@pytest.mark.asyncio
async def test_list_operation_logs_skips_username_lookup_when_no_user_ids():
    items = [OperationLog(id=1, user_id=None, action="create", resource_type="asset", resource_id=5, details={}, status="success", created_at=datetime(2026, 1, 1))]
    db = FakeDB(
        FakeResult(scalar=1),
        FakeResult(scalars=items),
    )

    response = await logs_operation_api.list_operation_logs(
        page=1, limit=20, search=None, action=None, user_id=None, date_from=None, date_to=None,
        db=db, current_user=user(is_superuser=True),
    )

    assert len(response["data"]) == 1
    assert db.executed  # only the count + fetch query, no username lookup


@pytest.mark.asyncio
async def test_list_password_logs_returns_items_and_meta():
    items = [
        PasswordChangeLog(id=1, user_id=1, change_type="user_password", changed_by=1, status="success", created_at=datetime(2026, 1, 1)),
    ]
    db = FakeDB(
        FakeResult(scalar=1),
        FakeResult(scalars=items),
        FakeResult(scalars=[user(id=1, username="alice")]),
    )

    response = await logs_password_api.list_password_logs(
        page=1, limit=20, search=None, user_id=None, change_type=None, date_from=None, date_to=None,
        db=db, current_user=user(is_superuser=True),
    )

    assert response["data"][0]["id"] == 1
    assert response["meta"].total == 1


@pytest.mark.asyncio
async def test_trigger_cleanup_logs_deleted_counts(monkeypatch):
    audit_calls = []

    async def fake_cleanup(db):
        return {"login_logs": 10, "operation_logs": 5}

    async def fake_log(*args, **kwargs):
        audit_calls.append((args, kwargs))

    monkeypatch.setattr(logs_api, "cleanup_expired_logs", fake_cleanup)
    monkeypatch.setattr(logs_api, "log_operation", fake_log)

    response = await logs_api.trigger_cleanup(
        db=FakeDB(),
        current_user=user(is_superuser=True),
        request=SimpleNamespace(client=SimpleNamespace(host="127.0.0.1")),
    )

    assert response["data"] == {"login_logs": 10, "operation_logs": 5}
    details = audit_calls[0][1]["details"]
    assert details["deleted_counts"] == {"login_logs": 10, "operation_logs": 5}
