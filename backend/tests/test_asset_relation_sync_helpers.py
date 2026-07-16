"""Tests for _sync_host_relations / _sync_storage_locations, the shared
helpers used by both create_asset and update_asset to (re)create a database
asset's runs_on hosts and storage locations."""
from types import SimpleNamespace

import pytest

from tests.factories import FakeDB, FakeResult

from app.api import assets as asset_api
from app.models import Asset, AssetHostRelation, StorageLocation


@pytest.mark.asyncio
async def test_sync_host_relations_create_mode_adds_valid_hosts():
    host = Asset(id="host-1", name="db-host", category="host")
    db = FakeDB(FakeResult(scalar_one_or_none=host))

    await asset_api._sync_host_relations(db, "db-1", ["host-1"])

    relation = next(o for o in db.added if isinstance(o, AssetHostRelation))
    assert relation.asset_id == "db-1"
    assert relation.host_id == "host-1"
    assert db.commits == 1


@pytest.mark.asyncio
async def test_sync_host_relations_skips_invalid_host():
    db = FakeDB(FakeResult(scalar_one_or_none=None))

    await asset_api._sync_host_relations(db, "db-1", ["not-a-host"])

    assert db.added == []


@pytest.mark.asyncio
async def test_sync_host_relations_replace_mode_deletes_first():
    host = Asset(id="host-1", name="db-host", category="host")
    db = FakeDB(
        FakeResult(),  # delete
        FakeResult(scalar_one_or_none=host),  # host lookup for recreation
    )

    await asset_api._sync_host_relations(db, "db-1", ["host-1"], replace=True)

    assert len(db.executed) == 2
    relation = next(o for o in db.added if isinstance(o, AssetHostRelation))
    assert relation.host_id == "host-1"


@pytest.mark.asyncio
async def test_sync_host_relations_replace_mode_empty_list_clears_all():
    db = FakeDB(FakeResult())  # delete only, nothing to recreate

    await asset_api._sync_host_relations(db, "db-1", [], replace=True)

    assert len(db.executed) == 1
    assert db.added == []


@pytest.mark.asyncio
async def test_sync_storage_locations_accepts_pydantic_like_objects():
    db = FakeDB()
    loc = SimpleNamespace(path="/data", path_type="data", description="main")

    await asset_api._sync_storage_locations(db, "db-1", [loc])

    location = next(o for o in db.added if isinstance(o, StorageLocation))
    assert location.asset_id == "db-1"
    assert location.path == "/data"
    assert db.commits == 1


@pytest.mark.asyncio
async def test_sync_storage_locations_accepts_plain_dicts():
    db = FakeDB()
    loc = {"path": "/log", "path_type": "log", "description": None}

    await asset_api._sync_storage_locations(db, "db-1", [loc])

    location = next(o for o in db.added if isinstance(o, StorageLocation))
    assert location.path == "/log"
    assert location.path_type == "log"


@pytest.mark.asyncio
async def test_sync_storage_locations_replace_mode_deletes_first():
    db = FakeDB(FakeResult())

    await asset_api._sync_storage_locations(db, "db-1", [], replace=True)

    assert len(db.executed) == 1
    assert db.added == []
