"""Tests for app.api.asset_import_export: import_assets and export_assets
route handlers (dispatch to batch_create/update_assets, permission-filtered
update mode, file-magic-byte validation, password-inclusion authorization)."""
from io import BytesIO
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from tests.factories import FakeDB, FakeResult, asset, asset_with_credentials, user

from app.api import asset_import_export as asset_api
from app.core.encryption import encrypt_value
from app.models import Credential


class FakeUploadFile:
    def __init__(self, filename="assets.xlsx", content=b"PK\x03\x04data"):
        self.filename = filename
        self._content = content

    async def read(self):
        return self._content


@pytest.mark.asyncio
async def test_import_assets_create_mode_dispatches_batch_and_audits(monkeypatch):
    audit_calls = []

    async def fake_parse(content, category, mode, db):
        return ([{"name": "web-1"}, {"name": "web-2"}], [{"row": 3, "error": "bad"}])

    async def fake_batch(category, records, db, user_id):
        assert category == "host"
        assert records == [{"name": "web-1"}, {"name": "web-2"}]
        assert user_id == 1
        return 2, []

    async def fake_log(*args, **kwargs):
        audit_calls.append((args, kwargs))

    monkeypatch.setattr(asset_api, "parse_import_file", fake_parse)
    monkeypatch.setattr(asset_api, "batch_create_assets", fake_batch)
    monkeypatch.setattr(asset_api, "get_created_orgs", lambda: {"Default / Ops"})
    monkeypatch.setattr(asset_api, "log_operation", fake_log)

    response = await asset_api.import_assets(
        category="host",
        mode="create",
        file=FakeUploadFile(),
        db=FakeDB(),
        current_user=user(is_superuser=True),
    )

    assert response.data.total_rows == 3
    assert response.data.success_count == 2
    assert response.data.failed_count == 1
    assert response.data.errors == [{"row": 3, "error": "bad"}]
    assert audit_calls
    assert audit_calls[0][1]["action"] == "import"
    assert audit_calls[0][1]["resource_type"] == "asset"


@pytest.mark.asyncio
async def test_import_assets_update_mode_filters_by_type_and_manage_permission(monkeypatch):
    allowed_records_seen = []
    audit_calls = []

    async def fake_parse(content, category, mode, db):
        return ([{"id": "asset-1"}, {"id": "asset-2"}, {"id": "missing"}], [])

    async def allow(current_user, permission, target_type, resource_id, db, organization_id=None):
        if resource_id == "asset-1":
            return True
        raise AssertionError("unexpected permission check")

    async def fake_batch(category, records, db):
        allowed_records_seen.extend(records)
        return len(records), []

    monkeypatch.setattr(asset_api, "parse_import_file", fake_parse)
    monkeypatch.setattr(asset_api, "check_resource_permission", allow)
    monkeypatch.setattr(asset_api, "batch_update_assets", fake_batch)
    monkeypatch.setattr(asset_api, "get_created_orgs", lambda: set())

    async def fake_log(*args, **kwargs):
        audit_calls.append((args, kwargs))

    monkeypatch.setattr(asset_api, "log_operation", fake_log)
    db = FakeDB(
        FakeResult(scalar_one_or_none=asset(id="asset-1", category="host")),
        FakeResult(scalar_one_or_none=asset(id="asset-2", category="database")),
        FakeResult(scalar_one_or_none=None),
    )

    response = await asset_api.import_assets(
        category="host",
        mode="update",
        file=FakeUploadFile(),
        db=db,
        current_user=user(is_superuser=True),
    )

    assert allowed_records_seen == [{"id": "asset-1"}, {"id": "missing"}]
    assert response.data.success_count == 2
    assert response.data.failed_count == 1
    assert response.data.errors == [{"id": "asset-2", "error": "资产类型不匹配"}]
    assert audit_calls
    assert audit_calls[0][1]["action"] == "import"
    assert audit_calls[0][1]["details"]["mode"] == "update"


@pytest.mark.asyncio
async def test_import_assets_rejects_invalid_file_magic_bytes():
    with pytest.raises(HTTPException) as exc:
        await asset_api.import_assets(
            category="host",
            mode="create",
            file=FakeUploadFile(content=b"not-xlsx"),
            db=FakeDB(),
            current_user=user(is_superuser=True),
        )

    assert exc.value.status_code == 400
    assert "文件格式不正确" in exc.value.detail


@pytest.mark.asyncio
async def test_export_assets_selected_csv_includes_passwords_when_authorized(monkeypatch):
    exported_rows = []
    audit_calls = []

    async def fake_authorized_ids(current_user, db, permission="view"):
        assert permission in {"view", "export_pwd"}
        return {"asset-1"}

    async def fake_permissions(current_user, db):
        return ["export", "export_pwd"]

    async def fake_csv_stream(row_gen, columns):
        async for row in row_gen:
            exported_rows.append(row)
        return BytesIO(b"csv"), len(exported_rows)

    async def fake_log(*args, **kwargs):
        audit_calls.append((args, kwargs))

    item = asset_with_credentials(category="host", created_by_id=1)
    item.oob_password_encrypted = encrypt_value("oob-secret")
    item.credentials = [
        Credential(
            id=1,
            asset_id="asset-1",
            username="root",
            password_encrypted=encrypt_value("cred-secret"),
            credential_type="password",
        )
    ]

    monkeypatch.setattr(asset_api, "get_authorized_asset_ids", fake_authorized_ids)
    monkeypatch.setattr(asset_api, "get_user_permissions", fake_permissions)
    monkeypatch.setattr(asset_api, "_export_csv_stream", fake_csv_stream)
    monkeypatch.setattr(asset_api, "log_operation", fake_log)

    db = FakeDB(
        FakeResult(scalar=1),
        FakeResult(scalars=[item]),
        FakeResult(all_rows=[SimpleNamespace(id=7, name="Ops", parent_id=None)]),
        FakeResult(all_rows=[SimpleNamespace(id=1, username="alice")]),
        FakeResult(scalars=[]),
    )

    response = await asset_api.export_assets(
        format="csv",
        scope="selected",
        ids="asset-1",
        include_passwords=True,
        db=db,
        current_user=user(is_superuser=True),
    )

    assert response.media_type == "text/csv"
    assert exported_rows[0]["credentials"] == [{"username": "root", "password": "cred-secret"}]
    assert exported_rows[0]["oob_password"] == "oob-secret"
    assert exported_rows[0]["creator_name"] == "alice"
    assert audit_calls
    assert audit_calls[0][1]["action"] == "export"
    assert audit_calls[0][1]["resource_type"] == "asset"


@pytest.mark.asyncio
async def test_export_assets_rejects_password_export_without_export_pwd(monkeypatch):
    async def all_authorized(current_user, db, permission="view"):
        return None

    async def missing_password_permission(current_user, db):
        return ["export"]

    monkeypatch.setattr(asset_api, "get_authorized_asset_ids", all_authorized)
    monkeypatch.setattr(asset_api, "get_user_permissions", missing_password_permission)

    with pytest.raises(HTTPException) as exc:
        await asset_api.export_assets(
            format="csv",
            scope="all",
            organization_id=None,
            include_passwords=True,
            db=FakeDB(),
            current_user=user(is_superuser=True),
        )

    assert exc.value.status_code == 403
    assert "export_pwd" in exc.value.detail
