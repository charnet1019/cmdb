"""Tests that duplicate asset_code (a DB-unique column) surfaces as a clean
400 instead of an unhandled IntegrityError / raw 500."""
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from tests.factories import FakeDB, FakeResult, asset, user

from app.api import assets as asset_api


class _IntegrityErrorFakeDB(FakeDB):
    """FakeDB variant whose commit() raises IntegrityError once, simulating a
    duplicate asset_code unique-constraint violation at flush/commit time."""

    async def commit(self):
        raise IntegrityError("INSERT INTO assets ...", {}, Exception("duplicate key value violates unique constraint"))


@pytest.mark.asyncio
async def test_create_asset_duplicate_asset_code_returns_400_not_500():
    db = _IntegrityErrorFakeDB()

    with pytest.raises(HTTPException) as exc:
        await asset_api.create_asset(
            data=asset_api.AssetCreate(
                name="host-dup",
                category="host",
                asset_code="CI-001",
                status="active",
            ),
            db=db,
            current_user=user(is_superuser=True),
            request=SimpleNamespace(client=SimpleNamespace(host="127.0.0.1")),
        )

    assert exc.value.status_code == 400
    assert "资产编号已存在" in exc.value.detail
    assert db.rollbacks == 1


@pytest.mark.asyncio
async def test_update_asset_duplicate_asset_code_returns_400_not_500(monkeypatch):
    async def allow(*args, **kwargs):
        return True

    monkeypatch.setattr(asset_api, "check_resource_permission", allow)

    existing = asset(category="host", asset_code="CI-001")
    db = _IntegrityErrorFakeDB(FakeResult(scalar_one_or_none=existing))

    with pytest.raises(HTTPException) as exc:
        await asset_api.update_asset(
            asset_id="asset-1",
            data=asset_api.AssetUpdate(asset_code="CI-002"),
            db=db,
            current_user=user(is_superuser=True),
            request=SimpleNamespace(client=SimpleNamespace(host="127.0.0.1")),
        )

    assert exc.value.status_code == 400
    assert "资产编号已存在" in exc.value.detail
    assert db.rollbacks == 1
