"""Tests for GET /authorizations (list_authorizations) and DELETE /authorizations/{id}."""
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from tests.factories import FakeDB, FakeResult, auth, user

from app.api import authorizations as authz_api


@pytest.mark.asyncio
async def test_list_authorizations_resolves_entity_and_asset_names():
    from app.models import Asset

    item = auth(entity_type="user", entity_id=1, target_type="asset", target_ids=["asset-1"])
    db = FakeDB(
        FakeResult(scalar=1),  # pagination count
        FakeResult(scalars=[item]),  # page fetch
        FakeResult(scalars=[user(id=1, username="alice")]),  # user names
        FakeResult(scalars=[Asset(id="asset-1", name="db-primary", category="database")]),  # asset names
    )

    response = await authz_api.list_authorizations(
        page=1, limit=20, entity_type=None, target_type=None, is_active=None, keyword=None,
        db=db, current_user=user(is_superuser=True),
    )

    assert response["data"][0]["entity_name"] == "alice"
    assert response["data"][0]["target_name"] == "db-primary"
    assert response["meta"].total == 1


@pytest.mark.asyncio
async def test_list_authorizations_resolves_group_and_organization_default_sentinel():
    from app.models import Group

    item = auth(entity_type="group", entity_id=10, target_type="organization", target_ids=["__all__"])
    db = FakeDB(
        FakeResult(scalar=1),
        FakeResult(scalars=[item]),
        FakeResult(scalars=[Group(id=10, name="ops")]),  # group name lookup
        FakeResult(scalars=[]),  # org lookup — "__all__" is not a digit, so org_ids_int is empty
    )

    response = await authz_api.list_authorizations(
        page=1, limit=20, entity_type=None, target_type=None, is_active=None, keyword=None,
        db=db, current_user=user(is_superuser=True),
    )

    assert response["data"][0]["entity_name"] == "ops"
    assert response["data"][0]["target_name"] == "Default"


@pytest.mark.asyncio
async def test_list_authorizations_falls_back_to_placeholder_when_entity_missing():
    item = auth(entity_type="user", entity_id=999, target_type="asset", target_ids=["asset-missing"])
    db = FakeDB(
        FakeResult(scalar=1),
        FakeResult(scalars=[item]),
        FakeResult(scalars=[]),  # no matching user found
        FakeResult(scalars=[]),  # no matching asset found
    )

    response = await authz_api.list_authorizations(
        page=1, limit=20, entity_type=None, target_type=None, is_active=None, keyword=None,
        db=db, current_user=user(is_superuser=True),
    )

    assert response["data"][0]["entity_name"] == "User 999"
    assert response["data"][0]["target_name"] == "Asset asset-missing"


@pytest.mark.asyncio
async def test_delete_authorization_404_when_not_found():
    db = FakeDB(FakeResult(scalar_one_or_none=None))

    with pytest.raises(HTTPException) as exc:
        await authz_api.delete_authorization(
            auth_id=99,
            db=db,
            current_user=user(is_superuser=True),
            request=SimpleNamespace(client=SimpleNamespace(host="127.0.0.1")),
        )

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_delete_authorization_deletes_and_logs_resolved_names(monkeypatch):
    target = auth(id=50, entity_type="user", entity_id=1, target_type="asset", target_ids=["asset-1"])

    async def fake_entity_name(db, entity_type, entity_id):
        return "alice"

    async def fake_target_names(db, target_type, target_ids):
        return "db-primary"

    audit_calls = []

    async def fake_log(*args, **kwargs):
        audit_calls.append((args, kwargs))

    monkeypatch.setattr(authz_api, "_resolve_entity_name", fake_entity_name)
    monkeypatch.setattr(authz_api, "resolve_target_names", fake_target_names)
    monkeypatch.setattr(authz_api, "log_operation", fake_log)

    db = FakeDB(FakeResult(scalar_one_or_none=target))

    response = await authz_api.delete_authorization(
        auth_id=50,
        db=db,
        current_user=user(id=2, is_superuser=True),
        request=SimpleNamespace(client=SimpleNamespace(host="127.0.0.1")),
    )

    assert response.message
    assert target in db.deleted
    assert db.commits == 1
    details = audit_calls[0][1]["details"]
    assert details["entity_name"] == "alice"
    assert details["name"] == "alice -> db-primary"
