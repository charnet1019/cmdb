"""Tests for GET/PUT /preferences/columns/{category}.

Covers the schema-version gating logic: stale (pre-v6) stored
column_visibility is a full-state snapshot, not a deviation-from-defaults
list, so it must be dropped rather than applied as-is.
"""
from datetime import datetime

import pytest

from tests.factories import FakeDB, FakeResult, user

from app.api import preferences as prefs_api
from app.models import UserPreference


def _preference(**kwargs):
    data = {
        "id": 1,
        "user_id": 1,
        "category": "all",
        "column_visibility": {"id": False},
        "column_order": ["name", "status"],
        "version": prefs_api.CURRENT_SCHEMA_VERSION,
        "updated_at": datetime(2026, 1, 1),
    }
    data.update(kwargs)
    return UserPreference(**data)


@pytest.mark.asyncio
async def test_get_column_config_returns_empty_when_no_preference_saved():
    db = FakeDB(FakeResult(scalar_one_or_none=None))

    response = await prefs_api.get_column_config(
        category="all", db=db, current_user=user(),
    )

    assert response["data"] == {}


@pytest.mark.asyncio
async def test_get_column_config_returns_visibility_for_current_schema_version():
    pref = _preference(version=prefs_api.CURRENT_SCHEMA_VERSION, column_visibility={"id": False})
    db = FakeDB(FakeResult(scalar_one_or_none=pref))

    response = await prefs_api.get_column_config(
        category="all", db=db, current_user=user(),
    )

    assert response["data"]["column_visibility"] == {"id": False}
    assert response["data"]["version"] == prefs_api.CURRENT_SCHEMA_VERSION


@pytest.mark.asyncio
async def test_get_column_config_drops_visibility_from_stale_schema_version():
    # Pre-v6 rows stored a full-state snapshot, not a deviation list — applying
    # it against current defaults would incorrectly hide/show columns.
    pref = _preference(version=prefs_api.CURRENT_SCHEMA_VERSION - 1, column_visibility={"id": False, "status": False})
    db = FakeDB(FakeResult(scalar_one_or_none=pref))

    response = await prefs_api.get_column_config(
        category="all", db=db, current_user=user(),
    )

    assert response["data"]["column_visibility"] == {}
    assert response["data"]["column_order"] == pref.column_order
    assert response["data"]["version"] == prefs_api.CURRENT_SCHEMA_VERSION - 1


@pytest.mark.asyncio
async def test_update_column_config_creates_new_preference():
    db = FakeDB(FakeResult(scalar_one_or_none=None))

    response = await prefs_api.update_column_config(
        category="host",
        data=prefs_api.ColumnConfigRequest(
            column_visibility={"cpu": True}, column_order=["name", "cpu"], version=6,
        ),
        db=db,
        current_user=user(id=3),
    )

    created = next(obj for obj in db.added if isinstance(obj, UserPreference))
    assert created.user_id == 3
    assert created.category == "host"
    assert created.version == 6
    assert response["data"]["column_visibility"] == {"cpu": True}
    assert db.commits == 1


@pytest.mark.asyncio
async def test_update_column_config_upserts_only_provided_fields():
    existing = _preference(column_visibility={"id": False}, column_order=["name"], version=5)
    db = FakeDB(FakeResult(scalar_one_or_none=existing))

    response = await prefs_api.update_column_config(
        category="all",
        data=prefs_api.ColumnConfigRequest(column_order=["name", "status"]),
        db=db,
        current_user=user(id=1),
    )

    # column_visibility untouched (not provided in this update), version bumped implicitly to unchanged
    assert existing.column_visibility == {"id": False}
    assert existing.column_order == ["name", "status"]
    assert response["data"]["column_order"] == ["name", "status"]
    assert db.added == []
    assert db.commits == 1


@pytest.mark.asyncio
async def test_update_column_config_updates_version_when_provided():
    existing = _preference(version=5)
    db = FakeDB(FakeResult(scalar_one_or_none=existing))

    await prefs_api.update_column_config(
        category="all",
        data=prefs_api.ColumnConfigRequest(version=6),
        db=db,
        current_user=user(id=1),
    )

    assert existing.version == 6
