"""Tests for cleanup_authorization_targets: removing dangling asset/organization
references from Authorization.target_ids when the underlying resource is deleted."""
import pytest

from tests.factories import FakeDB, FakeResult, auth

from app.utils.authorization_cleanup import cleanup_authorization_targets


@pytest.mark.asyncio
async def test_cleanup_removes_target_id_but_keeps_authorization_with_remaining_targets():
    item = auth(target_type="asset", target_ids=["asset-1", "asset-2"])
    db = FakeDB(FakeResult(scalars=[item]))

    await cleanup_authorization_targets(db, "asset", ["asset-1"])

    assert item.target_ids == ["asset-2"]
    assert db.deleted == []


@pytest.mark.asyncio
async def test_cleanup_deletes_authorization_when_no_targets_remain():
    item = auth(target_type="asset", target_ids=["asset-1"])
    db = FakeDB(FakeResult(scalars=[item]))

    await cleanup_authorization_targets(db, "asset", ["asset-1"])

    assert item in db.deleted


@pytest.mark.asyncio
async def test_cleanup_ignores_authorizations_without_matching_target_id():
    item = auth(target_type="asset", target_ids=["asset-99"])
    db = FakeDB(FakeResult(scalars=[item]))

    await cleanup_authorization_targets(db, "asset", ["asset-1"])

    assert item.target_ids == ["asset-99"]
    assert db.deleted == []


@pytest.mark.asyncio
async def test_cleanup_no_op_when_removed_ids_empty():
    db = FakeDB()  # no execute() calls expected

    await cleanup_authorization_targets(db, "asset", [])

    assert db.executed == []


@pytest.mark.asyncio
async def test_cleanup_handles_organization_target_type():
    item = auth(target_type="organization", target_ids=["7", "8"])
    db = FakeDB(FakeResult(scalars=[item]))

    await cleanup_authorization_targets(db, "organization", [7])

    assert item.target_ids == ["8"]
