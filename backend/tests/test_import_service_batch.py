"""Tests for import_service.batch_create_assets / batch_update_assets:
per-record SAVEPOINT isolation so one bad row doesn't poison the whole batch,
and the asset_code duplicate pre-check."""
from types import SimpleNamespace

import pytest

from tests.factories import FakeDB, FakeResult, asset

from app.services import import_service


@pytest.mark.asyncio
async def test_batch_create_assets_bad_row_does_not_poison_later_rows(monkeypatch):
    """Row 2 fails inside the flush (simulated DB error); row 3 — a fresh,
    otherwise-valid record — must still succeed. Without the SAVEPOINT fix,
    the whole session would be left in a failed state after row 2's error,
    and the flush for row 3 would blow up too."""

    async def flaky_flush():
        # Every 2nd flush call raises, simulating a duplicate asset_code
        # constraint violation for exactly one record in the batch.
        flaky_flush.calls += 1
        if flaky_flush.calls == 2:
            raise Exception("duplicate key value violates unique constraint")
    flaky_flush.calls = 0

    db = FakeDB(
        FakeResult(scalars=[]),  # duplicate-name pre-check: none
        FakeResult(scalars=[]),  # duplicate-asset_code pre-check: none
    )
    monkeypatch.setattr(db, "flush", flaky_flush)

    records = [
        {"name": "host-1", "asset_code": "CI-001", "status": "active"},
        {"name": "host-2", "asset_code": "CI-002", "status": "active"},
        {"name": "host-3", "asset_code": "CI-003", "status": "active"},
    ]

    success_count, failed_records = await import_service.batch_create_assets(
        category="host", records=records, db=db,
    )

    assert success_count == 2
    assert failed_records == [{"name": "host-2", "error": "duplicate key value violates unique constraint"}]
    # Row 1 and row 3 both made it into db.added despite row 2's failure being
    # unwound by the SAVEPOINT rollback.
    assert len(db.added) == 2
    assert db.commits == 1


@pytest.mark.asyncio
async def test_batch_create_assets_rejects_duplicate_asset_code_against_existing_db_row():
    db = FakeDB(
        FakeResult(all_rows=[]),  # duplicate-name pre-check: none
        FakeResult(all_rows=[SimpleNamespace(asset_code="CI-001")]),  # asset_code already in DB
    )

    records = [{"name": "host-1", "asset_code": "CI-001", "status": "active"}]

    success_count, failed_records = await import_service.batch_create_assets(
        category="host", records=records, db=db,
    )

    assert success_count == 0
    assert failed_records == [{"name": "host-1", "error": "资产编号'CI-001'已存在"}]
    assert db.added == []


@pytest.mark.asyncio
async def test_batch_create_assets_rejects_duplicate_asset_code_within_same_batch():
    db = FakeDB(
        FakeResult(scalars=[]),  # duplicate-name pre-check: none
        FakeResult(scalars=[]),  # asset_code pre-check against DB: none
    )

    records = [
        {"name": "host-1", "asset_code": "CI-001", "status": "active"},
        {"name": "host-2", "asset_code": "CI-001", "status": "active"},
    ]

    success_count, failed_records = await import_service.batch_create_assets(
        category="host", records=records, db=db,
    )

    assert success_count == 1
    assert failed_records == [{"name": "host-2", "error": "资产编号'CI-001'已存在"}]


@pytest.mark.asyncio
async def test_batch_update_assets_bad_row_does_not_poison_later_rows(monkeypatch):
    asset_1 = asset(id="asset-1", category="host")
    asset_2 = asset(id="asset-2", category="host")

    db = FakeDB(
        FakeResult(scalar_one_or_none=asset_1),
        FakeResult(scalar_one_or_none=asset_2),
    )

    call_count = {"n": 0}

    async def flaky_replace_credentials(asset_id, record, cred_type, db):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise Exception("boom")

    monkeypatch.setattr(import_service, "_replace_credentials", flaky_replace_credentials)

    records = [
        {"id": "asset-1", "status": "active", "credentials": []},
        {"id": "asset-2", "status": "active", "credentials": []},
    ]

    success_count, failed_records = await import_service.batch_update_assets(
        category="host", records=records, db=db,
    )

    assert success_count == 1
    assert failed_records == [{"id": "asset-1", "error": "boom"}]
    assert db.commits == 1
