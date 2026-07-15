"""Tests for POST/PUT /authorizations (create_authorization, update_authorization):
privilege-escalation guard, input validation, and duplicate detection."""
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from tests.factories import FakeDB, FakeResult, auth, user

from app.api import authorizations as authz_api
from app.schemas import AuthorizationCreate, AuthorizationUpdate


def _request():
    return SimpleNamespace(client=SimpleNamespace(host="127.0.0.1"))


@pytest.mark.asyncio
async def test_create_authorization_rejects_permissions_beyond_grantor_scope(monkeypatch):
    async def limited_permissions(current_user, db):
        return ["authorize", "view"]

    monkeypatch.setattr(authz_api, "get_user_permissions", limited_permissions)

    db = FakeDB()  # no DB calls expected — rejected before any query
    grantor = user(id=2, is_superuser=False)

    with pytest.raises(HTTPException) as exc:
        await authz_api.create_authorization(
            data=AuthorizationCreate(
                entity_type="user", entity_id=1, target_type="asset",
                target_ids=["asset-1"], permissions=["manage", "sys_config"],
            ),
            db=db,
            current_user=grantor,
            request=_request(),
        )

    assert exc.value.status_code == 403
    assert "manage" in exc.value.detail
    assert "sys_config" in exc.value.detail


@pytest.mark.asyncio
async def test_create_authorization_allows_permissions_within_grantor_scope(monkeypatch):
    async def limited_permissions(current_user, db):
        return ["authorize", "manage", "view"]

    audit_calls = []

    async def fake_log(*args, **kwargs):
        audit_calls.append((args, kwargs))

    monkeypatch.setattr(authz_api, "get_user_permissions", limited_permissions)
    monkeypatch.setattr(authz_api, "log_operation", fake_log)
    monkeypatch.setattr(authz_api, "_resolve_entity_name", lambda db, entity_type, entity_id: _async_return("alice"))
    monkeypatch.setattr(authz_api, "resolve_target_names", lambda db, target_type, target_ids: _async_return("db-primary"))

    target_user = user(id=1, username="alice")
    db = FakeDB(
        FakeResult(scalar_one_or_none=target_user),  # entity exists
        FakeResult(scalar_one_or_none=SimpleNamespace(id="asset-1")),  # target asset exists
        FakeResult(scalar_one_or_none=None),  # no duplicate active authorization
    )

    response = await authz_api.create_authorization(
        data=AuthorizationCreate(
            entity_type="user", entity_id=1, target_type="asset",
            target_ids=["asset-1"], permissions=["manage"],
        ),
        db=db,
        current_user=user(id=2, is_superuser=False),
        request=_request(),
    )

    assert response["message"] == "授权创建成功"
    assert db.commits == 1
    assert audit_calls


@pytest.mark.asyncio
async def test_create_authorization_superuser_bypasses_permission_scope_check(monkeypatch):
    monkeypatch.setattr(authz_api, "log_operation", lambda *a, **k: _async_return(None))
    monkeypatch.setattr(authz_api, "_resolve_entity_name", lambda db, entity_type, entity_id: _async_return("alice"))
    monkeypatch.setattr(authz_api, "resolve_target_names", lambda db, target_type, target_ids: _async_return("Default"))

    db = FakeDB(
        FakeResult(scalar_one_or_none=user(id=1)),  # entity exists
        FakeResult(scalar_one_or_none=None),  # no duplicate ("__all__" skips target existence check)
    )

    response = await authz_api.create_authorization(
        data=AuthorizationCreate(
            entity_type="user", entity_id=1, target_type="organization",
            target_ids=["__all__"], permissions=["manage", "sys_config", "user_mgmt"],
        ),
        db=db,
        current_user=user(id=99, is_superuser=True),
        request=_request(),
    )

    assert response["message"] == "授权创建成功"


@pytest.mark.asyncio
async def test_create_authorization_rejects_invalid_entity_type():
    db = FakeDB()

    with pytest.raises(HTTPException) as exc:
        await authz_api.create_authorization(
            data=AuthorizationCreate(
                entity_type="admin", entity_id=1, target_type="asset",
                target_ids=["asset-1"], permissions=["view"],
            ),
            db=db,
            current_user=user(is_superuser=True),
            request=_request(),
        )

    assert exc.value.status_code == 400
    assert db.executed == []


@pytest.mark.asyncio
async def test_create_authorization_rejects_invalid_target_type():
    db = FakeDB()

    with pytest.raises(HTTPException) as exc:
        await authz_api.create_authorization(
            data=AuthorizationCreate(
                entity_type="user", entity_id=1, target_type="host",
                target_ids=["asset-1"], permissions=["view"],
            ),
            db=db,
            current_user=user(is_superuser=True),
            request=_request(),
        )

    assert exc.value.status_code == 400
    assert db.executed == []


@pytest.mark.asyncio
async def test_create_authorization_rejects_non_numeric_org_target_id_with_400_not_500():
    db = FakeDB(
        FakeResult(scalar_one_or_none=user(id=1)),  # entity exists
    )

    with pytest.raises(HTTPException) as exc:
        await authz_api.create_authorization(
            data=AuthorizationCreate(
                entity_type="user", entity_id=1, target_type="organization",
                target_ids=["not-a-number"], permissions=["view"],
            ),
            db=db,
            current_user=user(is_superuser=True),
            request=_request(),
        )

    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_create_authorization_duplicate_check_ignores_inactive_rows(monkeypatch):
    """An inactive (soft-disabled) authorization with the same entity/target/permissions
    must not block creating a fresh active one."""
    monkeypatch.setattr(authz_api, "log_operation", lambda *a, **k: _async_return(None))
    monkeypatch.setattr(authz_api, "_resolve_entity_name", lambda db, entity_type, entity_id: _async_return("alice"))
    monkeypatch.setattr(authz_api, "resolve_target_names", lambda db, target_type, target_ids: _async_return("db-primary"))

    db = FakeDB(
        FakeResult(scalar_one_or_none=user(id=1)),  # entity exists
        FakeResult(scalar_one_or_none=SimpleNamespace(id="asset-1")),  # target exists
        FakeResult(scalar_one_or_none=None),  # duplicate query filters is_active=True — no match
    )

    response = await authz_api.create_authorization(
        data=AuthorizationCreate(
            entity_type="user", entity_id=1, target_type="asset",
            target_ids=["asset-1"], permissions=["view"],
        ),
        db=db,
        current_user=user(is_superuser=True),
        request=_request(),
    )

    assert response["message"] == "授权创建成功"


@pytest.mark.asyncio
async def test_update_authorization_rejects_permissions_beyond_grantor_scope(monkeypatch):
    async def limited_permissions(current_user, db):
        return ["authorize", "view"]

    monkeypatch.setattr(authz_api, "get_user_permissions", limited_permissions)

    existing = auth(id=50, permissions=["view"])
    db = FakeDB(FakeResult(scalar_one_or_none=existing))

    with pytest.raises(HTTPException) as exc:
        await authz_api.update_authorization(
            auth_id=50,
            data=AuthorizationUpdate(permissions=["manage", "sys_config"]),
            db=db,
            current_user=user(id=2, is_superuser=False),
            request=_request(),
        )

    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_update_authorization_rejects_non_numeric_org_target_id_with_400_not_500():
    existing = auth(id=50, target_type="organization", target_ids=["7"], permissions=["view"])
    db = FakeDB(
        FakeResult(scalar_one_or_none=existing),  # load authorization
        FakeResult(scalar_one_or_none=user(id=1, username="alice")),  # _resolve_entity_name
        FakeResult(scalars=[]),  # resolve_target_names (org lookup for before_target_names)
    )

    with pytest.raises(HTTPException) as exc:
        await authz_api.update_authorization(
            auth_id=50,
            data=AuthorizationUpdate(target_ids=["not-a-number"]),
            db=db,
            current_user=user(is_superuser=True),
            request=_request(),
        )

    assert exc.value.status_code == 400


async def _async_return(value):
    return value
