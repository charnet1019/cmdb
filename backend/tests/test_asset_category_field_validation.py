"""Tests for _validate_category_fields: rejecting fields that don't belong
to an asset's category (e.g. network hardware fields on a web asset)."""
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from tests.factories import FakeDB, FakeResult, asset, user

from app.api import assets as asset_api


def test_validate_category_fields_allows_host_specific_fields():
    asset_api._validate_category_fields("host", {"cpu": "8核", "memory": "16GB"})  # no raise


def test_validate_category_fields_allows_network_specific_fields():
    asset_api._validate_category_fields("network", {"device_type": "switch", "vendor": "Cisco"})  # no raise


def test_validate_category_fields_rejects_network_fields_on_web_asset():
    with pytest.raises(HTTPException) as exc:
        asset_api._validate_category_fields("web", {"device_type": "switch"})
    assert exc.value.status_code == 400
    assert "device_type" in exc.value.detail


def test_validate_category_fields_rejects_host_hardware_fields_on_gpt_asset():
    with pytest.raises(HTTPException) as exc:
        asset_api._validate_category_fields("gpt", {"cpu": "8核", "memory": "16GB"})
    assert "cpu" in exc.value.detail
    assert "memory" in exc.value.detail


def test_validate_category_fields_rejects_database_relations_on_host_asset():
    with pytest.raises(HTTPException) as exc:
        asset_api._validate_category_fields("host", {"host_ids": ["host-2"]})
    assert "host_ids" in exc.value.detail


def test_validate_category_fields_rejects_oob_fields_on_non_host_asset():
    with pytest.raises(HTTPException) as exc:
        asset_api._validate_category_fields("network", {"oob_password": "secret"})
    assert "oob_password" in exc.value.detail


def test_validate_category_fields_ignores_falsy_values():
    # An explicitly-set but empty/None field is not a violation — only a
    # truthy value in the wrong category is rejected.
    asset_api._validate_category_fields("web", {"device_type": None, "cpu": ""})  # no raise


@pytest.mark.asyncio
async def test_create_asset_rejects_network_field_on_web_category():
    db = FakeDB()

    with pytest.raises(HTTPException) as exc:
        await asset_api.create_asset(
            data=asset_api.AssetCreate(
                name="web-1",
                category="web",
                device_type="switch",
                status="active",
            ),
            db=db,
            current_user=user(is_superuser=True),
            request=SimpleNamespace(client=SimpleNamespace(host="127.0.0.1")),
        )

    assert exc.value.status_code == 400
    assert db.executed == []
    assert db.added == []


@pytest.mark.asyncio
async def test_update_asset_rejects_field_not_matching_existing_category(monkeypatch):
    async def allow(*args, **kwargs):
        return True

    monkeypatch.setattr(asset_api, "check_resource_permission", allow)

    existing = asset(category="gpt")
    db = FakeDB(FakeResult(scalar_one_or_none=existing))

    with pytest.raises(HTTPException) as exc:
        await asset_api.update_asset(
            asset_id="asset-1",
            data=asset_api.AssetUpdate(vendor="Cisco"),
            db=db,
            current_user=user(is_superuser=True),
            request=SimpleNamespace(client=SimpleNamespace(host="127.0.0.1")),
        )

    assert exc.value.status_code == 400
    assert "vendor" in exc.value.detail
