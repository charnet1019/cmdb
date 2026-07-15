"""Tests for the network-device config-file feature (9 endpoints under
/assets/{asset_id}/config...): metadata, content view, download, version
history, version content, upload, save, rollback, and delete.
"""
from datetime import datetime
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.responses import StreamingResponse

from tests.factories import FakeDB, FakeResult, asset, user

from app.api import assets as asset_api
from app.models import AssetConfigFile, AssetConfigVersion


def _network_asset(**kwargs):
    data = {"category": "network", "name": "core-switch"}
    data.update(kwargs)
    return asset(**data)


def _config_file(**kwargs):
    data = {
        "id": 1,
        "asset_id": "asset-1",
        "filename": "switch.cfg",
        "current_version_id": 10,
        "created_by": 1,
        "updated_by": 1,
        "created_at": datetime(2026, 1, 1),
        "updated_at": datetime(2026, 1, 2),
    }
    data.update(kwargs)
    return AssetConfigFile(**data)


def _config_version(**kwargs):
    data = {
        "id": 10,
        "config_file_id": 1,
        "version_no": 1,
        "filename": "switch.cfg",
        "content_encrypted": asset_api.encrypt_value("interface eth0\n"),
        "size": 16,
        "checksum": asset_api._content_checksum("interface eth0\n"),
        "change_summary": "上传配置文件",
        "created_by": 1,
        "created_at": datetime(2026, 1, 1),
    }
    data.update(kwargs)
    return AssetConfigVersion(**data)


class FakeUploadFile:
    def __init__(self, filename="switch.cfg", content=b"interface eth0\n"):
        self.filename = filename
        self._content = content

    async def read(self):
        return self._content


def _request():
    return SimpleNamespace(client=SimpleNamespace(host="127.0.0.1"))


# ---- _get_network_asset_or_404 ----

@pytest.mark.asyncio
async def test_get_network_asset_404_when_missing():
    db = FakeDB(FakeResult(scalar_one_or_none=None))

    with pytest.raises(HTTPException) as exc:
        await asset_api._get_network_asset_or_404(db, "asset-1", user(is_superuser=True))

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_get_network_asset_rejects_non_network_category():
    db = FakeDB(FakeResult(scalar_one_or_none=asset(category="host")))

    with pytest.raises(HTTPException) as exc:
        await asset_api._get_network_asset_or_404(db, "asset-1", user(is_superuser=True))

    assert exc.value.status_code == 400
    assert "仅网络设备" in exc.value.detail


# ---- GET /{asset_id}/config (metadata) ----

@pytest.mark.asyncio
async def test_get_asset_config_meta_no_file_yet(monkeypatch):
    async def fake_get_network_asset(db, asset_id, current_user, permission="view"):
        return _network_asset()

    async def allow(*args, **kwargs):
        return None

    monkeypatch.setattr(asset_api, "_get_network_asset_or_404", fake_get_network_asset)
    monkeypatch.setattr(asset_api, "check_resource_permission", allow)

    db = FakeDB(FakeResult(scalar_one_or_none=None))  # config file lookup

    response = await asset_api.get_asset_config_meta(
        asset_id="asset-1", db=db, current_user=user(is_superuser=True),
    )

    assert response["data"]["id"] is None
    assert response["data"]["can_edit"] is True


@pytest.mark.asyncio
async def test_get_asset_config_meta_returns_current_version_info(monkeypatch):
    async def fake_get_network_asset(db, asset_id, current_user, permission="view"):
        return _network_asset()

    async def allow(*args, **kwargs):
        return None

    monkeypatch.setattr(asset_api, "_get_network_asset_or_404", fake_get_network_asset)
    monkeypatch.setattr(asset_api, "check_resource_permission", allow)

    config_file = _config_file()
    version = _config_version()
    db = FakeDB(
        FakeResult(scalar_one_or_none=config_file),  # _get_config_file
        FakeResult(scalar_one_or_none=version),      # _get_current_config_version (by current_version_id)
    )

    response = await asset_api.get_asset_config_meta(
        asset_id="asset-1", db=db, current_user=user(is_superuser=True),
    )

    assert response["data"]["filename"] == "switch.cfg"
    assert response["data"]["version_no"] == 1


# ---- GET /{asset_id}/config/content ----

@pytest.mark.asyncio
async def test_get_asset_config_content_403_without_view_permission(monkeypatch):
    async def fake_get_network_asset(db, asset_id, current_user, permission="view"):
        return _network_asset()

    async def deny_manage(*args, **kwargs):
        raise HTTPException(status_code=403, detail="缺少权限")

    async def fake_permissions(current_user, db):
        return []

    monkeypatch.setattr(asset_api, "_get_network_asset_or_404", fake_get_network_asset)
    monkeypatch.setattr(asset_api, "check_resource_permission", deny_manage)
    monkeypatch.setattr(asset_api, "get_user_permissions", fake_permissions)

    with pytest.raises(HTTPException) as exc:
        await asset_api.get_asset_config_content(
            asset_id="asset-1", db=FakeDB(), current_user=user(),
        )

    assert exc.value.status_code == 403
    assert "查看配置文件权限" in exc.value.detail


@pytest.mark.asyncio
async def test_get_asset_config_content_404_when_no_file(monkeypatch):
    async def fake_get_network_asset(db, asset_id, current_user, permission="view"):
        return _network_asset()

    async def allow(*args, **kwargs):
        return None

    monkeypatch.setattr(asset_api, "_get_network_asset_or_404", fake_get_network_asset)
    monkeypatch.setattr(asset_api, "check_resource_permission", allow)

    db = FakeDB(FakeResult(scalar_one_or_none=None))

    with pytest.raises(HTTPException) as exc:
        await asset_api.get_asset_config_content(
            asset_id="asset-1", db=db, current_user=user(is_superuser=True),
        )

    assert exc.value.status_code == 404
    assert exc.value.detail == "配置文件不存在"


@pytest.mark.asyncio
async def test_get_asset_config_content_returns_decrypted_text(monkeypatch):
    async def fake_get_network_asset(db, asset_id, current_user, permission="view"):
        return _network_asset()

    async def allow(*args, **kwargs):
        return None

    monkeypatch.setattr(asset_api, "_get_network_asset_or_404", fake_get_network_asset)
    monkeypatch.setattr(asset_api, "check_resource_permission", allow)

    config_file = _config_file()
    version = _config_version()
    db = FakeDB(
        FakeResult(scalar_one_or_none=config_file),
        FakeResult(scalar_one_or_none=version),
    )

    response = await asset_api.get_asset_config_content(
        asset_id="asset-1", db=db, current_user=user(is_superuser=True),
    )

    assert response["data"]["content"] == "interface eth0\n"


# ---- GET /{asset_id}/config/download ----

@pytest.mark.asyncio
async def test_download_asset_config_streams_file_and_logs(monkeypatch):
    async def fake_get_network_asset(db, asset_id, current_user, permission="view"):
        return _network_asset()

    async def allow(*args, **kwargs):
        return None

    audit_calls = []

    async def fake_log(*args, **kwargs):
        audit_calls.append((args, kwargs))

    monkeypatch.setattr(asset_api, "_get_network_asset_or_404", fake_get_network_asset)
    monkeypatch.setattr(asset_api, "check_resource_permission", allow)
    monkeypatch.setattr(asset_api, "log_operation", fake_log)

    config_file = _config_file()
    version = _config_version()
    db = FakeDB(
        FakeResult(scalar_one_or_none=config_file),
        FakeResult(scalar_one_or_none=version),
    )

    response = await asset_api.download_asset_config(
        asset_id="asset-1", request=_request(), db=db, current_user=user(is_superuser=True),
    )

    assert isinstance(response, StreamingResponse)
    assert "switch.cfg" in response.headers["content-disposition"]
    assert audit_calls[0][1]["details"]["action"] == "download_config"


# ---- GET /{asset_id}/config/versions ----

@pytest.mark.asyncio
async def test_list_asset_config_versions_empty_when_no_file(monkeypatch):
    async def fake_get_network_asset(db, asset_id, current_user, permission="view"):
        return _network_asset()

    async def allow(*args, **kwargs):
        return None

    monkeypatch.setattr(asset_api, "_get_network_asset_or_404", fake_get_network_asset)
    monkeypatch.setattr(asset_api, "check_resource_permission", allow)

    db = FakeDB(FakeResult(scalar_one_or_none=None))

    response = await asset_api.list_asset_config_versions(
        asset_id="asset-1", db=db, current_user=user(is_superuser=True),
    )

    assert response["data"] == []


@pytest.mark.asyncio
async def test_list_asset_config_versions_marks_current_version(monkeypatch):
    async def fake_get_network_asset(db, asset_id, current_user, permission="view"):
        return _network_asset()

    async def allow(*args, **kwargs):
        return None

    monkeypatch.setattr(asset_api, "_get_network_asset_or_404", fake_get_network_asset)
    monkeypatch.setattr(asset_api, "check_resource_permission", allow)

    config_file = _config_file(current_version_id=10)
    version = _config_version(id=10)
    db = FakeDB(
        FakeResult(scalar_one_or_none=config_file),
        FakeResult(all_rows=[(version, "alice")]),
    )

    response = await asset_api.list_asset_config_versions(
        asset_id="asset-1", db=db, current_user=user(is_superuser=True),
    )

    assert response["data"][0]["is_current"] is True
    assert response["data"][0]["created_by_username"] == "alice"


# ---- GET /{asset_id}/config/versions/{version_id} ----

@pytest.mark.asyncio
async def test_get_asset_config_version_content_404_when_not_found(monkeypatch):
    async def fake_get_network_asset(db, asset_id, current_user, permission="view"):
        return _network_asset()

    async def allow(*args, **kwargs):
        return None

    monkeypatch.setattr(asset_api, "_get_network_asset_or_404", fake_get_network_asset)
    monkeypatch.setattr(asset_api, "check_resource_permission", allow)

    config_file = _config_file()
    db = FakeDB(
        FakeResult(scalar_one_or_none=config_file),
        FakeResult(scalar_one_or_none=None),
    )

    with pytest.raises(HTTPException) as exc:
        await asset_api.get_asset_config_version_content(
            asset_id="asset-1", version_id=999, db=db, current_user=user(is_superuser=True),
        )

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_get_asset_config_version_content_returns_decrypted_text(monkeypatch):
    async def fake_get_network_asset(db, asset_id, current_user, permission="view"):
        return _network_asset()

    async def allow(*args, **kwargs):
        return None

    monkeypatch.setattr(asset_api, "_get_network_asset_or_404", fake_get_network_asset)
    monkeypatch.setattr(asset_api, "check_resource_permission", allow)

    config_file = _config_file(current_version_id=10)
    version = _config_version(id=10)
    db = FakeDB(
        FakeResult(scalar_one_or_none=config_file),
        FakeResult(scalar_one_or_none=version),
    )

    response = await asset_api.get_asset_config_version_content(
        asset_id="asset-1", version_id=10, db=db, current_user=user(is_superuser=True),
    )

    assert response["data"]["content"] == "interface eth0\n"
    assert response["data"]["is_current"] is True


# ---- POST /{asset_id}/config/upload ----

@pytest.mark.asyncio
async def test_upload_asset_config_file_rejects_bad_extension(monkeypatch):
    async def fake_get_network_asset(db, asset_id, current_user, permission="manage"):
        return _network_asset()

    monkeypatch.setattr(asset_api, "_get_network_asset_or_404", fake_get_network_asset)

    with pytest.raises(HTTPException) as exc:
        await asset_api.upload_asset_config_file(
            asset_id="asset-1", request=_request(),
            file=FakeUploadFile(filename="switch.txt"),
            db=FakeDB(), current_user=user(is_superuser=True),
        )

    assert exc.value.status_code == 400
    assert "仅支持" in exc.value.detail


@pytest.mark.asyncio
async def test_upload_asset_config_file_creates_file_and_first_version(monkeypatch):
    async def fake_get_network_asset(db, asset_id, current_user, permission="manage"):
        return _network_asset(id="asset-1")

    audit_calls = []

    async def fake_log(*args, **kwargs):
        audit_calls.append((args, kwargs))

    monkeypatch.setattr(asset_api, "_get_network_asset_or_404", fake_get_network_asset)
    monkeypatch.setattr(asset_api, "log_operation", fake_log)

    db = FakeDB(
        FakeResult(scalar_one_or_none=None),  # no existing config file
        FakeResult(scalar_one_or_none=None),  # _get_current_config_version: no version yet (fallback query)
        FakeResult(scalar=None),              # _next_config_version_no: max() -> None
    )

    response = await asset_api.upload_asset_config_file(
        asset_id="asset-1", request=_request(),
        file=FakeUploadFile(filename="switch.cfg", content=b"interface eth0\n"),
        db=db, current_user=user(id=1, is_superuser=True),
    )

    created_file = next(obj for obj in db.added if isinstance(obj, AssetConfigFile))
    created_version = next(obj for obj in db.added if isinstance(obj, AssetConfigVersion))
    assert created_file.filename == "switch.cfg"
    assert created_version.version_no == 1
    assert asset_api.decrypt_value(created_version.content_encrypted) == "interface eth0\n"
    assert response["message"] == "配置文件已上传"
    assert audit_calls[0][1]["details"]["action"] == "upload_config"


@pytest.mark.asyncio
async def test_upload_asset_config_file_reports_unchanged_when_identical(monkeypatch):
    async def fake_get_network_asset(db, asset_id, current_user, permission="manage"):
        return _network_asset(id="asset-1")

    async def fake_log(*args, **kwargs):
        return None

    monkeypatch.setattr(asset_api, "_get_network_asset_or_404", fake_get_network_asset)
    monkeypatch.setattr(asset_api, "log_operation", fake_log)

    config_file = _config_file(current_version_id=10)
    existing_version = _config_version(id=10, filename="switch.cfg")
    db = FakeDB(
        FakeResult(scalar_one_or_none=config_file),
        FakeResult(scalar_one_or_none=existing_version),
    )

    response = await asset_api.upload_asset_config_file(
        asset_id="asset-1", request=_request(),
        file=FakeUploadFile(filename="switch.cfg", content=b"interface eth0\n"),
        db=db, current_user=user(id=1, is_superuser=True),
    )

    assert response["message"] == "配置内容未变化"
    assert not any(isinstance(obj, AssetConfigVersion) for obj in db.added)


# ---- PUT /{asset_id}/config/content ----

@pytest.mark.asyncio
async def test_save_asset_config_content_rejects_oversized_content(monkeypatch):
    async def fake_get_network_asset(db, asset_id, current_user, permission="manage"):
        return _network_asset()

    monkeypatch.setattr(asset_api, "_get_network_asset_or_404", fake_get_network_asset)
    monkeypatch.setattr(asset_api, "MAX_CONFIG_FILE_SIZE", 10)

    with pytest.raises(HTTPException) as exc:
        await asset_api.save_asset_config_content(
            asset_id="asset-1",
            data=asset_api.AssetConfigContentSave(filename="switch.cfg", content="x" * 100),
            request=_request(),
            db=FakeDB(),
            current_user=user(is_superuser=True),
        )

    assert exc.value.status_code == 400
    assert "不能超过2MB" in exc.value.detail


@pytest.mark.asyncio
async def test_save_asset_config_content_creates_new_version(monkeypatch):
    async def fake_get_network_asset(db, asset_id, current_user, permission="manage"):
        return _network_asset(id="asset-1")

    async def fake_log(*args, **kwargs):
        return None

    monkeypatch.setattr(asset_api, "_get_network_asset_or_404", fake_get_network_asset)
    monkeypatch.setattr(asset_api, "log_operation", fake_log)

    config_file = _config_file(current_version_id=10)
    existing_version = _config_version(id=10, filename="switch.cfg", content_encrypted=asset_api.encrypt_value("old content"))
    db = FakeDB(
        FakeResult(scalar_one_or_none=config_file),
        FakeResult(scalar_one_or_none=existing_version),
        FakeResult(scalar=1),  # _next_config_version_no
    )

    response = await asset_api.save_asset_config_content(
        asset_id="asset-1",
        data=asset_api.AssetConfigContentSave(filename="switch.cfg", content="new content"),
        request=_request(),
        db=db,
        current_user=user(id=1, is_superuser=True),
    )

    created_version = next(obj for obj in db.added if isinstance(obj, AssetConfigVersion))
    assert asset_api.decrypt_value(created_version.content_encrypted) == "new content"
    assert response["message"] == "配置已保存"


# ---- POST /{asset_id}/config/rollback ----

@pytest.mark.asyncio
async def test_rollback_asset_config_404_when_no_file(monkeypatch):
    async def fake_get_network_asset(db, asset_id, current_user, permission="manage"):
        return _network_asset()

    monkeypatch.setattr(asset_api, "_get_network_asset_or_404", fake_get_network_asset)

    db = FakeDB(FakeResult(scalar_one_or_none=None))

    with pytest.raises(HTTPException) as exc:
        await asset_api.rollback_asset_config(
            asset_id="asset-1",
            data=asset_api.AssetConfigRollback(version_id=5),
            request=_request(),
            db=db,
            current_user=user(is_superuser=True),
        )

    assert exc.value.status_code == 404
    assert exc.value.detail == "配置文件不存在"


@pytest.mark.asyncio
async def test_rollback_asset_config_404_when_target_version_missing(monkeypatch):
    async def fake_get_network_asset(db, asset_id, current_user, permission="manage"):
        return _network_asset()

    monkeypatch.setattr(asset_api, "_get_network_asset_or_404", fake_get_network_asset)

    config_file = _config_file()
    db = FakeDB(
        FakeResult(scalar_one_or_none=config_file),
        FakeResult(scalar_one_or_none=None),
    )

    with pytest.raises(HTTPException) as exc:
        await asset_api.rollback_asset_config(
            asset_id="asset-1",
            data=asset_api.AssetConfigRollback(version_id=999),
            request=_request(),
            db=db,
            current_user=user(is_superuser=True),
        )

    assert exc.value.status_code == 404
    assert exc.value.detail == "配置版本不存在"


@pytest.mark.asyncio
async def test_rollback_asset_config_creates_new_version_from_target(monkeypatch):
    async def fake_get_network_asset(db, asset_id, current_user, permission="manage"):
        return _network_asset(id="asset-1")

    audit_calls = []

    async def fake_log(*args, **kwargs):
        audit_calls.append((args, kwargs))

    monkeypatch.setattr(asset_api, "_get_network_asset_or_404", fake_get_network_asset)
    monkeypatch.setattr(asset_api, "log_operation", fake_log)

    config_file = _config_file(current_version_id=20)
    target_version = _config_version(id=5, version_no=1, filename="switch.cfg", content_encrypted=asset_api.encrypt_value("old content"))
    current_version = _config_version(id=20, version_no=2, filename="switch.cfg", content_encrypted=asset_api.encrypt_value("newer content"))

    db = FakeDB(
        FakeResult(scalar_one_or_none=config_file),   # _get_config_file
        FakeResult(scalar_one_or_none=target_version),  # target version lookup
        FakeResult(scalar_one_or_none=current_version),  # _get_current_config_version (force_new path still checks current)
        FakeResult(scalar=2),  # _next_config_version_no
    )

    response = await asset_api.rollback_asset_config(
        asset_id="asset-1",
        data=asset_api.AssetConfigRollback(version_id=5),
        request=_request(),
        db=db,
        current_user=user(id=1, is_superuser=True),
    )

    created_version = next(obj for obj in db.added if isinstance(obj, AssetConfigVersion))
    assert asset_api.decrypt_value(created_version.content_encrypted) == "old content"
    assert response["message"] == "已回滚配置"
    assert audit_calls[0][1]["details"]["action"] == "rollback_config"
    assert audit_calls[0][1]["details"]["from_version_no"] == 1


# ---- DELETE /{asset_id}/config ----

@pytest.mark.asyncio
async def test_delete_asset_config_no_file_reports_not_deleted(monkeypatch):
    async def fake_get_network_asset(db, asset_id, current_user, permission="manage"):
        return _network_asset()

    monkeypatch.setattr(asset_api, "_get_network_asset_or_404", fake_get_network_asset)

    db = FakeDB(FakeResult(scalar_one_or_none=None))

    response = await asset_api.delete_asset_config(
        asset_id="asset-1", request=_request(), db=db, current_user=user(is_superuser=True),
    )

    assert response["data"]["deleted"] is False


@pytest.mark.asyncio
async def test_delete_asset_config_removes_existing_file(monkeypatch):
    async def fake_get_network_asset(db, asset_id, current_user, permission="manage"):
        return _network_asset(id="asset-1")

    audit_calls = []

    async def fake_log(*args, **kwargs):
        audit_calls.append((args, kwargs))

    monkeypatch.setattr(asset_api, "_get_network_asset_or_404", fake_get_network_asset)
    monkeypatch.setattr(asset_api, "log_operation", fake_log)

    config_file = _config_file()
    db = FakeDB(FakeResult(scalar_one_or_none=config_file))

    response = await asset_api.delete_asset_config(
        asset_id="asset-1", request=_request(), db=db, current_user=user(id=1, is_superuser=True),
    )

    assert response["data"]["deleted"] is True
    assert config_file in db.deleted
    assert audit_calls[0][1]["details"]["action"] == "delete_config"
