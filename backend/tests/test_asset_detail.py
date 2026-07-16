"""Tests for app.api.asset_detail: get_asset/update_asset/delete_asset —
the /{asset_id} wildcard routes (moved out of app.api.assets during the
router split, into their own module so they register after fixed paths
like /assets/export)."""
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from tests.factories import FakeDB, FakeResult, asset, asset_with_credentials, user

from app.api import asset_detail as asset_detail_api
from app.schemas import AssetUpdate


@pytest.mark.asyncio
async def test_update_asset_success_updates_fields_encrypts_oob_and_checks_manage(monkeypatch):
    checked = {}
    audit_calls = []

    async def allow(current_user, permission, target_type, resource_id, db, organization_id=None):
        checked.update(
            permission=permission,
            target_type=target_type,
            resource_id=resource_id,
            organization_id=organization_id,
        )
        return True

    async def fake_log(*args, **kwargs):
        audit_calls.append((args, kwargs))

    existing = asset_with_credentials(category="host", name="old", owner_id=None, owner_name=None)
    reloaded = existing
    db = FakeDB(
        FakeResult(scalar_one_or_none=existing),
        FakeResult(scalar_one_or_none=2),
        FakeResult(scalar_one=reloaded),
    )
    monkeypatch.setattr(asset_detail_api, "check_resource_permission", allow)
    monkeypatch.setattr(asset_detail_api, "log_operation", fake_log)

    response = await asset_detail_api.update_asset(
        asset_id="asset-1",
        data=AssetUpdate(
            name="new-name",
            owner_name="bob",
            oob_password="new-oob",
            status="maintenance",
        ),
        db=db,
        current_user=user(is_superuser=True),
        request=SimpleNamespace(client=SimpleNamespace(host="127.0.0.1")),
    )

    assert response["name"] == "new-name"
    assert existing.owner_id == 2
    assert existing.oob_password_encrypted.startswith("gAAAA")
    assert existing.status == "maintenance"
    assert checked == {
        "permission": "manage",
        "target_type": "asset",
        "resource_id": "asset-1",
        "organization_id": 7,
    }
    assert audit_calls
    assert audit_calls[0][0][2] == "update"


@pytest.mark.asyncio
async def test_delete_asset_success_checks_manage_and_deletes(monkeypatch):
    checked = {}
    audit_calls = []

    async def allow(current_user, permission, target_type, resource_id, db, organization_id=None):
        checked["permission"] = permission
        checked["resource_id"] = resource_id
        checked["organization_id"] = organization_id
        return True

    async def fake_log(*args, **kwargs):
        audit_calls.append((args, kwargs))

    existing = asset(category="host", asset_code="CI-001")
    db = FakeDB(
        FakeResult(scalar_one_or_none=existing),
        FakeResult(scalars=[]),  # cleanup_authorization_targets: no matching authorizations
    )
    monkeypatch.setattr(asset_detail_api, "check_resource_permission", allow)
    monkeypatch.setattr(asset_detail_api, "log_operation", fake_log)

    response = await asset_detail_api.delete_asset(
        asset_id="asset-1",
        db=db,
        current_user=user(is_superuser=True),
        request=SimpleNamespace(client=SimpleNamespace(host="127.0.0.1")),
    )

    assert response.message == "资产已删除"
    assert db.deleted == [existing]
    assert checked == {"permission": "manage", "resource_id": "asset-1", "organization_id": 7}
    assert audit_calls


@pytest.mark.asyncio
async def test_update_asset_rejects_field_not_matching_existing_category(monkeypatch):
    async def allow(*args, **kwargs):
        return True

    monkeypatch.setattr(asset_detail_api, "check_resource_permission", allow)

    existing = asset(category="gpt")
    db = FakeDB(FakeResult(scalar_one_or_none=existing))

    with pytest.raises(HTTPException) as exc:
        await asset_detail_api.update_asset(
            asset_id="asset-1",
            data=AssetUpdate(vendor="Cisco"),
            db=db,
            current_user=user(is_superuser=True),
            request=SimpleNamespace(client=SimpleNamespace(host="127.0.0.1")),
        )

    assert exc.value.status_code == 400
    assert "vendor" in exc.value.detail


class _IntegrityErrorFakeDB(FakeDB):
    """FakeDB variant whose commit() raises IntegrityError once, simulating a
    duplicate asset_code unique-constraint violation at flush/commit time."""

    async def commit(self):
        raise IntegrityError("UPDATE assets ...", {}, Exception("duplicate key value violates unique constraint"))


@pytest.mark.asyncio
async def test_update_asset_duplicate_asset_code_returns_400_not_500(monkeypatch):
    async def allow(*args, **kwargs):
        return True

    monkeypatch.setattr(asset_detail_api, "check_resource_permission", allow)

    existing = asset(category="host", asset_code="CI-001")
    db = _IntegrityErrorFakeDB(FakeResult(scalar_one_or_none=existing))

    with pytest.raises(HTTPException) as exc:
        await asset_detail_api.update_asset(
            asset_id="asset-1",
            data=AssetUpdate(asset_code="CI-002"),
            db=db,
            current_user=user(is_superuser=True),
            request=SimpleNamespace(client=SimpleNamespace(host="127.0.0.1")),
        )

    assert exc.value.status_code == 400
    assert "资产编号已存在" in exc.value.detail
    assert db.rollbacks == 1
