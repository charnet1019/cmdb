"""Regression test: updating an asset's owner (by owner_id or owner_name)
must produce exactly one "owner" audit change entry, not two separate
owner_id/owner_name entries that both render under the same "负责人" label
as duplicate "将负责人从空修改为X" log lines."""
from types import SimpleNamespace

import pytest

from tests.factories import FakeDB, FakeResult, asset_with_credentials, user

from app.api import assets as asset_api


@pytest.mark.asyncio
async def test_update_asset_owner_by_id_logs_single_consolidated_change(monkeypatch):
    async def allow(*args, **kwargs):
        return True

    audit_calls = []

    async def fake_log(*args, **kwargs):
        audit_calls.append((args, kwargs))

    monkeypatch.setattr(asset_api, "check_resource_permission", allow)
    monkeypatch.setattr(asset_api, "log_operation", fake_log)

    existing = asset_with_credentials(category="host", owner_id=None, owner_name=None)
    db = FakeDB(
        FakeResult(scalar_one_or_none=existing),
        FakeResult(scalar_one_or_none="bob"),  # username lookup for owner_id=4
        FakeResult(scalar_one=existing),
    )

    await asset_api.update_asset(
        asset_id="asset-1",
        data=asset_api.AssetUpdate(owner_id=4),
        db=db,
        current_user=user(is_superuser=True),
        request=SimpleNamespace(client=SimpleNamespace(host="127.0.0.1")),
    )

    changes = audit_calls[0][1]["details"]["changes"]
    assert "owner_id" not in changes
    assert "owner_name" not in changes
    assert changes["owner"] == [None, "bob"]
    assert existing.owner_id == 4
    assert existing.owner_name == "bob"


@pytest.mark.asyncio
async def test_update_asset_owner_by_name_logs_single_consolidated_change(monkeypatch):
    async def allow(*args, **kwargs):
        return True

    audit_calls = []

    async def fake_log(*args, **kwargs):
        audit_calls.append((args, kwargs))

    monkeypatch.setattr(asset_api, "check_resource_permission", allow)
    monkeypatch.setattr(asset_api, "log_operation", fake_log)

    existing = asset_with_credentials(category="host", owner_id=None, owner_name=None)
    db = FakeDB(
        FakeResult(scalar_one_or_none=existing),
        FakeResult(scalar_one_or_none=7),  # id lookup for owner_name="test"
        FakeResult(scalar_one=existing),
    )

    await asset_api.update_asset(
        asset_id="asset-1",
        data=asset_api.AssetUpdate(owner_name="test"),
        db=db,
        current_user=user(is_superuser=True),
        request=SimpleNamespace(client=SimpleNamespace(host="127.0.0.1")),
    )

    changes = audit_calls[0][1]["details"]["changes"]
    assert changes.get("owner") == [None, "test"]
    assert "owner_id" not in changes
    assert "owner_name" not in changes
    assert existing.owner_id == 7
    assert existing.owner_name == "test"


@pytest.mark.asyncio
async def test_update_asset_owner_id_not_found_raises_400():
    from fastapi import HTTPException

    existing = asset_with_credentials(category="host", owner_id=None, owner_name=None)
    db = FakeDB(
        FakeResult(scalar_one_or_none=existing),
        FakeResult(scalar_one_or_none=None),  # username lookup: no such user
    )

    with pytest.raises(HTTPException) as exc:
        await asset_api.update_asset(
            asset_id="asset-1",
            data=asset_api.AssetUpdate(owner_id=999),
            db=db,
            current_user=user(is_superuser=True),
            request=SimpleNamespace(client=SimpleNamespace(host="127.0.0.1")),
        )

    assert exc.value.status_code == 400
