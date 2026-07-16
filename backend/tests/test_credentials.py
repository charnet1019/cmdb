"""Tests for app.api.credentials: per-asset credential creation and
OOB password decryption (moved out of app.api.assets during the router split)."""
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from tests.factories import FakeDB, FakeResult, asset, user

from app.api import credentials as credentials_api
from app.models import Credential
from app.schemas import CredentialCreate


@pytest.mark.asyncio
async def test_decrypt_oob_password_returns_decrypted_value(monkeypatch):
    checked = {}

    async def allow(user_obj, permission, target_type, resource_id, db, organization_id=None):
        checked.update(
            permission=permission,
            target_type=target_type,
            resource_id=resource_id,
            organization_id=organization_id,
        )

    monkeypatch.setattr(credentials_api, "check_resource_permission", allow)

    async def no_rate_limit(*args, **kwargs):
        return None

    monkeypatch.setattr(credentials_api, "check_credential_decrypt_rate_limit", no_rate_limit)
    monkeypatch.setattr(credentials_api, "decrypt_value", lambda v: "oob-pass")

    encrypted_asset = asset(oob_password_encrypted="gAAAA-fake-ciphertext")
    db = FakeDB(FakeResult(scalar_one_or_none=encrypted_asset))

    response = await credentials_api.decrypt_oob_password("asset-1", db=db, current_user=user())

    assert response.oob_password == "oob-pass"
    assert checked == {
        "permission": "view_pwd",
        "target_type": "asset",
        "resource_id": "asset-1",
        "organization_id": 7,
    }


@pytest.mark.asyncio
async def test_decrypt_oob_password_404_when_not_set(monkeypatch):
    async def allow(*args, **kwargs):
        return None

    async def no_rate_limit(*args, **kwargs):
        return None

    monkeypatch.setattr(credentials_api, "check_resource_permission", allow)
    monkeypatch.setattr(credentials_api, "check_credential_decrypt_rate_limit", no_rate_limit)

    no_oob_asset = asset(oob_password_encrypted=None)
    db = FakeDB(FakeResult(scalar_one_or_none=no_oob_asset))

    with pytest.raises(HTTPException) as exc:
        await credentials_api.decrypt_oob_password("asset-1", db=db, current_user=user())

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_create_credential_encrypts_password_and_logs_change(monkeypatch):
    async def allow(*args, **kwargs):
        return True

    monkeypatch.setattr(credentials_api, "check_resource_permission", allow)
    db = FakeDB(FakeResult(scalar_one_or_none=asset(category="host")))

    response = await credentials_api.create_credential(
        request=SimpleNamespace(client=SimpleNamespace(host="127.0.0.1")),
        data=CredentialCreate(username="root", password="plain-pass", credential_type="password"),
        asset_id="asset-1",
        db=db,
        current_user=user(),
    )

    created = next(obj for obj in db.added if isinstance(obj, Credential))
    assert response.username == "root"
    assert created.password_encrypted != "plain-pass"
    assert created.password_encrypted.startswith("gAAAA")
    assert any(getattr(obj, "change_type", None) == "asset_credential" for obj in db.added)
