"""Tests for GET /assets (list_assets) and the bulk update/delete endpoints.

list_assets previously had zero test coverage, which is exactly why a missing
import (`get_pagination_meta`) shipped as a runtime 500 that no test caught.
"""
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from tests.factories import FakeDB, FakeResult, asset, user

from app.api import assets as asset_api
from app.schemas import BulkDeleteRequest, BulkUpdateRequest


@pytest.mark.asyncio
async def test_list_assets_returns_items_and_pagination_meta(monkeypatch):
    async def fake_authorized_ids(current_user, db, permission="view"):
        return None  # superuser / unrestricted

    monkeypatch.setattr(asset_api, "get_authorized_asset_ids", fake_authorized_ids)

    items = [asset(id="asset-1"), asset(id="asset-2", category="host")]
    db = FakeDB(
        FakeResult(scalar=2),          # get_pagination_meta count query
        FakeResult(scalars=items),     # paginated asset fetch
        FakeResult(all_rows=[SimpleNamespace(id=7, name="Ops")]),   # org names
        FakeResult(all_rows=[SimpleNamespace(id=1, username="alice")]),  # creator names
    )

    response = await asset_api.list_assets(
        response=SimpleNamespace(),
        page=1,
        limit=15,
        db=db,
        current_user=user(is_superuser=True),
    )

    assert response["code"] == 0
    assert len(response["data"]) == 2
    assert response["data"][0]["id"] == "asset-1"
    assert response["meta"]["total"] == 2
    assert response["meta"]["page"] == 1
    assert response["meta"]["limit"] == 15
    assert response["meta"]["pages"] == 1


@pytest.mark.asyncio
async def test_list_assets_returns_empty_when_no_authorized_assets(monkeypatch):
    async def fake_authorized_ids(current_user, db, permission="view"):
        return set()  # authorizations exist but none match this user

    monkeypatch.setattr(asset_api, "get_authorized_asset_ids", fake_authorized_ids)

    db = FakeDB()  # no db.execute calls should happen on this short-circuit path

    response = await asset_api.list_assets(
        response=SimpleNamespace(),
        page=1,
        limit=15,
        db=db,
        current_user=user(),
    )

    assert response["data"]["items"] == []
    assert response["data"]["total"] == 0
    assert db.executed == []


@pytest.mark.asyncio
async def test_list_assets_filters_by_authorized_ids(monkeypatch):
    async def fake_authorized_ids(current_user, db, permission="view"):
        return {"asset-1"}

    monkeypatch.setattr(asset_api, "get_authorized_asset_ids", fake_authorized_ids)

    items = [asset(id="asset-1")]
    db = FakeDB(
        FakeResult(scalar=1),
        FakeResult(scalars=items),
        FakeResult(all_rows=[SimpleNamespace(id=7, name="Ops")]),
        FakeResult(all_rows=[SimpleNamespace(id=1, username="alice")]),
    )

    response = await asset_api.list_assets(
        response=SimpleNamespace(),
        page=1,
        limit=15,
        db=db,
        current_user=user(),
    )

    assert len(response["data"]) == 1
    assert response["data"][0]["id"] == "asset-1"


@pytest.mark.asyncio
async def test_bulk_update_assets_rejects_empty_ids():
    with pytest.raises(HTTPException) as exc:
        await asset_api.bulk_update_assets(
            body=BulkUpdateRequest(ids=[], data={"status": "running"}),
            db=FakeDB(),
            current_user=user(is_superuser=True),
            request=SimpleNamespace(client=SimpleNamespace(host="127.0.0.1")),
        )

    assert exc.value.status_code == 400
    assert "请选择要操作的资产" in exc.value.detail


@pytest.mark.asyncio
async def test_bulk_update_assets_rejects_unsupported_fields():
    """Only 'status' is supported. Other fields must be rejected with 400
    instead of silently doing nothing, which would look like success."""
    items = [asset(id="asset-1")]
    db = FakeDB(FakeResult(scalars=items))

    with pytest.raises(HTTPException) as exc:
        await asset_api.bulk_update_assets(
            body=BulkUpdateRequest(ids=["asset-1"], data={"organization_id": 7}),
            db=db,
            current_user=user(is_superuser=True),
            request=SimpleNamespace(client=SimpleNamespace(host="127.0.0.1")),
        )

    assert exc.value.status_code == 400
    assert "organization_id" in exc.value.detail
    assert db.commits == 0


@pytest.mark.asyncio
async def test_bulk_update_assets_rejects_empty_data():
    items = [asset(id="asset-1")]
    db = FakeDB(FakeResult(scalars=items))

    with pytest.raises(HTTPException) as exc:
        await asset_api.bulk_update_assets(
            body=BulkUpdateRequest(ids=["asset-1"], data={}),
            db=db,
            current_user=user(is_superuser=True),
            request=SimpleNamespace(client=SimpleNamespace(host="127.0.0.1")),
        )

    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_bulk_update_assets_404_when_no_assets_found():
    db = FakeDB(FakeResult(scalars=[]))

    with pytest.raises(HTTPException) as exc:
        await asset_api.bulk_update_assets(
            body=BulkUpdateRequest(ids=["asset-1"], data={"status": "running"}),
            db=db,
            current_user=user(is_superuser=True),
            request=SimpleNamespace(client=SimpleNamespace(host="127.0.0.1")),
        )

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_bulk_update_assets_checks_permission_and_updates_status(monkeypatch):
    checked_ids = []

    async def fake_permission(current_user, permission, target_type, resource_id, db, organization_id=None):
        checked_ids.append(resource_id)

    audit_calls = []

    async def fake_log(*args, **kwargs):
        audit_calls.append((args, kwargs))

    monkeypatch.setattr(asset_api, "check_resource_permission", fake_permission)
    monkeypatch.setattr(asset_api, "log_operation", fake_log)

    items = [asset(id="asset-1", status="running"), asset(id="asset-2", status="running")]
    db = FakeDB(FakeResult(scalars=items))

    response = await asset_api.bulk_update_assets(
        body=BulkUpdateRequest(ids=["asset-1", "asset-2"], data={"status": "deactivated"}),
        db=db,
        current_user=user(is_superuser=True),
        request=SimpleNamespace(client=SimpleNamespace(host="127.0.0.1")),
    )

    assert checked_ids == ["asset-1", "asset-2"]
    assert items[0].status == "deactivated"
    assert items[1].status == "deactivated"
    assert db.commits == 1
    assert "已更新 2 个资产" in response.message
    details = audit_calls[0][1]["details"]
    assert details["action"] == "bulk_update"
    assert details["count"] == 2


@pytest.mark.asyncio
async def test_bulk_update_assets_silently_excludes_unauthorized_ids(monkeypatch):
    """An asset the caller isn't authorized for is dropped from the batch the
    same way a nonexistent ID would be — not surfaced as a distinct 403 —
    so the two cases aren't distinguishable by response shape (ID enumeration)."""
    from fastapi import HTTPException as FastAPIHTTPException

    async def fake_permission(current_user, permission, target_type, resource_id, db, organization_id=None):
        if resource_id == "asset-2":
            raise FastAPIHTTPException(status_code=403, detail="缺少资源 'manage' 权限")

    monkeypatch.setattr(asset_api, "check_resource_permission", fake_permission)
    monkeypatch.setattr(asset_api, "log_operation", lambda *a, **k: _noop())

    items = [asset(id="asset-1", status="running"), asset(id="asset-2", status="running")]
    db = FakeDB(FakeResult(scalars=items))

    response = await asset_api.bulk_update_assets(
        body=BulkUpdateRequest(ids=["asset-1", "asset-2"], data={"status": "deactivated"}),
        db=db,
        current_user=user(is_superuser=True),
        request=SimpleNamespace(client=SimpleNamespace(host="127.0.0.1")),
    )

    assert items[0].status == "deactivated"
    assert items[1].status == "running"  # unauthorized asset left untouched
    assert "已更新 1 个资产" in response.message


@pytest.mark.asyncio
async def test_bulk_update_assets_404_when_all_ids_unauthorized(monkeypatch):
    from fastapi import HTTPException as FastAPIHTTPException

    async def deny(*args, **kwargs):
        raise FastAPIHTTPException(status_code=403, detail="缺少资源 'manage' 权限")

    monkeypatch.setattr(asset_api, "check_resource_permission", deny)

    items = [asset(id="asset-1")]
    db = FakeDB(FakeResult(scalars=items))

    with pytest.raises(HTTPException) as exc:
        await asset_api.bulk_update_assets(
            body=BulkUpdateRequest(ids=["asset-1"], data={"status": "deactivated"}),
            db=db,
            current_user=user(is_superuser=True),
            request=SimpleNamespace(client=SimpleNamespace(host="127.0.0.1")),
        )

    assert exc.value.status_code == 404


async def _noop():
    return None


@pytest.mark.asyncio
async def test_bulk_delete_assets_rejects_empty_ids():
    with pytest.raises(HTTPException) as exc:
        await asset_api.bulk_delete_assets(
            body=BulkDeleteRequest(ids=[]),
            db=FakeDB(),
            current_user=user(is_superuser=True),
            request=SimpleNamespace(client=SimpleNamespace(host="127.0.0.1")),
        )

    assert exc.value.status_code == 400
    assert "请选择要删除的资产" in exc.value.detail


@pytest.mark.asyncio
async def test_bulk_delete_assets_checks_permission_and_deletes(monkeypatch):
    async def fake_permission(*args, **kwargs):
        return None

    audit_calls = []

    async def fake_log(*args, **kwargs):
        audit_calls.append((args, kwargs))

    monkeypatch.setattr(asset_api, "check_resource_permission", fake_permission)
    monkeypatch.setattr(asset_api, "log_operation", fake_log)

    items = [asset(id="asset-1"), asset(id="asset-2")]
    db = FakeDB(
        FakeResult(scalars=items),
        FakeResult(scalars=[]),  # cleanup_authorization_targets: no matching authorizations
    )

    response = await asset_api.bulk_delete_assets(
        body=BulkDeleteRequest(ids=["asset-1", "asset-2"]),
        db=db,
        current_user=user(is_superuser=True),
        request=SimpleNamespace(client=SimpleNamespace(host="127.0.0.1")),
    )

    assert set(db.deleted) == set(items)
    assert db.commits == 1
    assert "已删除 2 个资产" in response.message
    details = audit_calls[0][1]["details"]
    assert details["action"] == "bulk_delete"
    assert details["count"] == 2


@pytest.mark.asyncio
async def test_bulk_delete_assets_silently_excludes_unauthorized_ids(monkeypatch):
    """Same ID-enumeration concern as bulk_update: an unauthorized asset must
    be dropped from the batch, not surfaced as a distinct 403."""
    async def fake_permission(current_user, permission, target_type, resource_id, db, organization_id=None):
        if resource_id == "asset-2":
            raise HTTPException(status_code=403, detail="缺少资源 'manage' 权限")

    monkeypatch.setattr(asset_api, "check_resource_permission", fake_permission)
    monkeypatch.setattr(asset_api, "log_operation", lambda *a, **k: _noop())

    items = [asset(id="asset-1"), asset(id="asset-2")]
    db = FakeDB(
        FakeResult(scalars=items),
        FakeResult(scalars=[]),  # cleanup_authorization_targets: no matching authorizations
    )

    response = await asset_api.bulk_delete_assets(
        body=BulkDeleteRequest(ids=["asset-1", "asset-2"]),
        db=db,
        current_user=user(is_superuser=True),
        request=SimpleNamespace(client=SimpleNamespace(host="127.0.0.1")),
    )

    assert db.deleted == [items[0]]
    assert "已删除 1 个资产" in response.message


@pytest.mark.asyncio
async def test_bulk_delete_assets_404_when_all_ids_unauthorized(monkeypatch):
    async def deny(*args, **kwargs):
        raise HTTPException(status_code=403, detail="缺少资源 'manage' 权限")

    monkeypatch.setattr(asset_api, "check_resource_permission", deny)

    items = [asset(id="asset-1")]
    db = FakeDB(FakeResult(scalars=items))

    with pytest.raises(HTTPException) as exc:
        await asset_api.bulk_delete_assets(
            body=BulkDeleteRequest(ids=["asset-1"]),
            db=db,
            current_user=user(is_superuser=True),
            request=SimpleNamespace(client=SimpleNamespace(host="127.0.0.1")),
        )

    assert exc.value.status_code == 404
