"""Tests for import_service database-asset relation helpers:
_handle_database_relations (create) and _replace_database_relations (update),
which share host-lookup/StorageLocation-construction logic."""
import pytest

from tests.factories import FakeDB, FakeResult

from app.models import Asset, AssetHostRelation, StorageLocation
from app.services import import_service


@pytest.mark.asyncio
async def test_handle_database_relations_adds_host_relation_and_storage_location():
    host = Asset(id="host-1", name="db-host", category="host")
    db = FakeDB(FakeResult(scalar_one_or_none=host))

    record = {
        "runs_on": ["db-host"],
        "storage_locations": [{"path": "/data", "path_type": "data", "description": "main"}],
    }

    await import_service._handle_database_relations("db-1", record, db)

    relation = next(o for o in db.added if isinstance(o, AssetHostRelation))
    location = next(o for o in db.added if isinstance(o, StorageLocation))
    assert relation.asset_id == "db-1"
    assert relation.host_id == "host-1"
    assert location.asset_id == "db-1"
    assert location.path == "/data"


@pytest.mark.asyncio
async def test_handle_database_relations_skips_host_not_found():
    db = FakeDB(FakeResult(scalar_one_or_none=None))

    await import_service._handle_database_relations("db-1", {"runs_on": ["missing-host"]}, db)

    assert db.added == []


@pytest.mark.asyncio
async def test_replace_database_relations_deletes_before_recreating():
    host = Asset(id="host-1", name="db-host", category="host")
    db = FakeDB(
        FakeResult(),  # delete AssetHostRelation
        FakeResult(),  # delete StorageLocation
        FakeResult(scalar_one_or_none=host),  # host lookup for recreation
    )

    record = {"runs_on": ["db-host"], "storage_locations": []}

    await import_service._replace_database_relations("db-1", record, db)

    # Both delete statements ran (runs_on present + storage_locations present),
    # then the host lookup for recreation.
    assert len(db.executed) == 3
    relation = next(o for o in db.added if isinstance(o, AssetHostRelation))
    assert relation.host_id == "host-1"


@pytest.mark.asyncio
async def test_replace_database_relations_leaves_untouched_field_alone():
    """If 'runs_on' isn't in the record at all (update didn't touch it),
    no delete should run for it — only storage_locations gets cleared."""
    db = FakeDB(FakeResult())  # only the storage_locations delete is expected

    record = {"storage_locations": []}

    await import_service._replace_database_relations("db-1", record, db)

    assert len(db.executed) == 1  # only the storage_locations delete
    assert db.added == []
