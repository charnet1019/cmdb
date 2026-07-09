from datetime import datetime
from io import BytesIO
import importlib.util
import sys
import types
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

# app.api.__init__ imports the auth router, whose avatar helpers import Pillow.
# These tests do not exercise avatar image processing, so provide a minimal
# import stub when Pillow is not installed in the local test environment.
if importlib.util.find_spec("PIL") is None:
    pil_module = types.ModuleType("PIL")
    image_module = types.ModuleType("PIL.Image")
    pil_module.Image = image_module
    pil_module.UnidentifiedImageError = ValueError
    sys.modules["PIL"] = pil_module
    sys.modules["PIL.Image"] = image_module

if importlib.util.find_spec("pyotp") is None:
    pyotp_module = types.ModuleType("pyotp")
    class _TOTP:
        def __init__(self, secret):
            self.secret = secret
        def verify(self, code):
            return code == "123456"
        def provisioning_uri(self, name, issuer_name=None):
            return f"otpauth://totp/{name}"
    pyotp_module.TOTP = _TOTP
    pyotp_module.random_base32 = lambda: "JBSWY3DPEHPK3PXP"
    sys.modules["pyotp"] = pyotp_module

if importlib.util.find_spec("qrcode") is None:
    qrcode_module = types.ModuleType("qrcode")
    class _QR:
        def save(self, buffer, format=None):
            buffer.write(b"png")
    qrcode_module.make = lambda uri: _QR()
    sys.modules["qrcode"] = qrcode_module

from app.api import assets as asset_api
from app.api import authorizations as authz_api
from app.api import deps
from app.api import dashboard as dashboard_api
from app.api import users as users_api
from app.models import Asset, Authorization, Credential, Group, Organization, User
from app.schemas import AuthorizationCreate, CredentialCreate, GroupCreate, UserUpdate


class ScalarList:
    def __init__(self, values):
        self.values = values

    def all(self):
        return self.values

    def first(self):
        return self.values[0] if self.values else None


class FakeResult:
    def __init__(self, *, scalar=None, scalar_one=None, scalar_one_or_none=None, scalars=None, all_rows=None):
        self._scalar = scalar
        self._scalar_one = scalar_one if scalar_one is not None else scalar
        self._scalar_one_or_none = scalar_one_or_none if scalar_one_or_none is not None else scalar
        self._scalars = scalars if scalars is not None else []
        self._all_rows = all_rows if all_rows is not None else []

    def scalar(self):
        return self._scalar

    def scalar_one(self):
        return self._scalar_one

    def scalar_one_or_none(self):
        return self._scalar_one_or_none

    def scalars(self):
        return ScalarList(self._scalars)

    def all(self):
        return self._all_rows

    def first(self):
        return self._all_rows[0] if self._all_rows else None

    def fetchall(self):
        return self._all_rows

    def __iter__(self):
        return iter(self._all_rows)


class FakeDB:
    def __init__(self, *results):
        self.results = list(results)
        self.added = []
        self.deleted = []
        self.commits = 0
        self.flushes = 0
        self.rollbacks = 0
        self.executed = []
        self._next_id = 100

    async def execute(self, statement):
        self.executed.append(statement)
        if not self.results:
            raise AssertionError(f"Unexpected execute: {statement}")
        return self.results.pop(0)

    async def scalar(self, statement):
        result = await self.execute(statement)
        return result.scalar()

    def add(self, obj):
        self.added.append(obj)

    async def delete(self, obj):
        self.deleted.append(obj)

    async def flush(self):
        self.flushes += 1
        self._hydrate_added()

    async def commit(self):
        self.commits += 1
        self._hydrate_added()

    async def rollback(self):
        self.rollbacks += 1

    async def refresh(self, obj):
        self._hydrate(obj)

    def _hydrate_added(self):
        for obj in self.added:
            self._hydrate(obj)

    def _hydrate(self, obj):
        if getattr(obj, "id", None) is None:
            if obj.__class__.__name__ == "Asset":
                obj.id = f"asset-{self._next_id}"
            else:
                obj.id = self._next_id
            self._next_id += 1
        now = datetime(2026, 1, 1, 0, 0, 0)
        for field in ("created_at", "updated_at"):
            if hasattr(obj, field) and getattr(obj, field, None) is None:
                setattr(obj, field, now)


def user(**kwargs):
    data = {
        "id": 1,
        "username": "alice",
        "email": "alice@example.com",
        "full_name": "Alice",
        "phone": None,
        "password_hash": "hash",
        "is_active": True,
        "is_superuser": False,
        "mfa_enabled": False,
        "mfa_secret": None,
        "must_change_password": False,
        "avatar_url": None,
        "last_login_at": None,
        "created_at": datetime(2026, 1, 1, 0, 0, 0),
    }
    data.update(kwargs)
    return User(**data)


def group(**kwargs):
    data = {
        "id": 10,
        "name": "ops",
        "description": "Operations",
        "is_default": False,
        "created_at": datetime(2026, 1, 1, 0, 0, 0),
    }
    data.update(kwargs)
    return Group(**data)


def asset(**kwargs):
    data = {
        "id": "asset-1",
        "name": "db-primary",
        "category": "database",
        "internal_address": "10.0.0.10",
        "external_address": None,
        "platform": "PostgreSQL",
        "db_type": "postgres",
        "organization_id": 7,
        "notes": "primary",
        "extra_data": {"version": "16", "oob_password": "secret"},
        "created_at": datetime(2026, 1, 1, 0, 0, 0),
        "updated_at": datetime(2026, 1, 2, 0, 0, 0),
        "applicant": "team-a",
        "namespace": "public",
        "owner_id": 1,
        "owner_name": "Alice",
        "status": "active",
    }
    data.update(kwargs)
    return Asset(**data)


def organization(**kwargs):
    data = {
        "id": 7,
        "name": "Database Team",
        "parent_id": None,
        "path": "7",
        "level": 0,
        "created_at": datetime(2026, 1, 1, 0, 0, 0),
    }
    data.update(kwargs)
    return Organization(**data)


def auth(**kwargs):
    data = {
        "id": 50,
        "entity_type": "user",
        "entity_id": 1,
        "target_type": "asset",
        "target_ids": ["asset-1"],
        "permissions": ["view"],
        "valid_from": None,
        "valid_until": None,
        "is_active": True,
        "created_by": 1,
        "created_at": datetime(2026, 1, 1, 0, 0, 0),
    }
    data.update(kwargs)
    return Authorization(**data)


@pytest.mark.asyncio
async def test_permission_checker_allows_implied_permission(monkeypatch):
    async def manage_permission(current_user, db):
        return ["manage"]

    monkeypatch.setattr(deps, "get_user_permissions", manage_permission)

    current_user = user()
    assert await deps.PermissionChecker("view")(current_user=current_user, db=FakeDB()) is current_user


@pytest.mark.asyncio
async def test_permission_checker_rejects_missing_permission(monkeypatch):
    async def no_permissions(current_user, db):
        return []

    monkeypatch.setattr(deps, "get_user_permissions", no_permissions)

    with pytest.raises(HTTPException) as exc:
        await deps.PermissionChecker("authorize")(current_user=user(), db=FakeDB())

    assert exc.value.status_code == 403
    assert "authorize" in exc.value.detail


@pytest.mark.asyncio
async def test_get_user_permissions_merges_direct_and_group_permissions():
    db = FakeDB(
        FakeResult(scalars=[auth(permissions=["manage"])]),
        FakeResult(all_rows=[(10,)]),
        FakeResult(scalars=[auth(entity_type="group", entity_id=10, permissions=["view_users"])]),
    )

    permissions = set(await deps.get_user_permissions(user(), db))

    assert {"manage", "view", "view_users"}.issubset(permissions)


@pytest.mark.asyncio
async def test_check_resource_permission_accepts_manage_for_view():
    db = FakeDB(FakeResult(scalar_one_or_none=auth(permissions=["manage"])))

    assert await deps.check_resource_permission(user(), "view", "asset", "asset-1", db)


@pytest.mark.asyncio
async def test_check_resource_permission_raises_when_no_resource_match():
    db = FakeDB(FakeResult(scalar_one_or_none=None))

    with pytest.raises(HTTPException) as exc:
        await deps.check_resource_permission(user(), "manage", "organization", "7", db)

    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_get_authorized_asset_ids_returns_empty_when_authorizations_exist_but_no_match():
    db = FakeDB(
        FakeResult(scalar=1),
        FakeResult(all_rows=[]),
        FakeResult(scalars=[]),
        FakeResult(scalars=[]),
    )

    assert await deps.get_authorized_asset_ids(user(), db, "view") == set()


def test_build_asset_response_filters_sensitive_metadata_and_includes_expected_fields():
    response = asset_api.build_asset_response(
        asset(),
        org_name="Database Team",
        credentials_data=[{"id": 1, "username": "root", "credential_type": "password"}],
        creator_name="admin",
    )

    assert response["id"] == "asset-1"
    assert response["organization_name"] == "Database Team"
    assert response["credentials"] == [{"id": 1, "username": "root", "credential_type": "password"}]
    assert response["extra_data"] == {"version": "16"}
    assert response["version"] == "16"
    assert "oob_password" not in response


@pytest.mark.asyncio
async def test_create_asset_rejects_invalid_category_without_db_write():
    with pytest.raises(HTTPException) as exc:
        await asset_api.create_asset(
            data=asset_api.AssetCreate(name="bad", category="invalid"),
            db=FakeDB(),
            current_user=user(is_superuser=True),
        )

    assert exc.value.status_code == 400
    assert "无效的资产类型" in exc.value.detail


@pytest.mark.asyncio
async def test_decrypt_oob_password_migrates_legacy_plaintext(monkeypatch):
    checked = {}

    async def allow(user_obj, permission, target_type, resource_id, db, organization_id=None):
        checked.update(
            permission=permission,
            target_type=target_type,
            resource_id=resource_id,
            organization_id=organization_id,
        )

    monkeypatch.setattr(asset_api, "check_resource_permission", allow)

    legacy_asset = asset(oob_password_encrypted=None, extra_data={"oob_password": "legacy-pass"})
    db = FakeDB(FakeResult(scalar_one_or_none=legacy_asset))

    response = await asset_api.decrypt_oob_password("asset-1", db=db, current_user=user())

    assert response.oob_password == "legacy-pass"
    assert legacy_asset.oob_password_encrypted.startswith("gAAAA")
    assert db.flushes == 1
    assert checked == {
        "permission": "view_pwd",
        "target_type": "asset",
        "resource_id": "asset-1",
        "organization_id": 7,
    }


@pytest.mark.asyncio
async def test_create_credential_encrypts_password_and_logs_change(monkeypatch):
    async def allow(*args, **kwargs):
        return True

    monkeypatch.setattr(asset_api, "check_resource_permission", allow)
    db = FakeDB(FakeResult(scalar_one_or_none=asset(category="host")))

    response = await asset_api.create_credential(
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


@pytest.mark.asyncio
async def test_update_user_self_cannot_change_admin_only_fields(monkeypatch):
    async def no_permissions(current_user, db):
        return []

    monkeypatch.setattr(users_api, "get_user_permissions", no_permissions)

    with pytest.raises(HTTPException) as exc:
        await users_api.update_user(
            user_id=1,
            data=UserUpdate(is_active=False),
            request=SimpleNamespace(client=SimpleNamespace(host="127.0.0.1")),
            db=FakeDB(),
            current_user=user(),
        )

    assert exc.value.status_code == 403
    assert exc.value.detail == "缺少 user_mgmt 权限"


@pytest.mark.asyncio
async def test_create_group_adds_initial_members_and_audit_log(monkeypatch):
    audit_calls = []

    async def fake_log(*args, **kwargs):
        audit_calls.append((args, kwargs))

    monkeypatch.setattr(users_api, "log_operation", fake_log)
    db = FakeDB(FakeResult(scalar_one_or_none=None))

    response = await users_api.create_group(
        data=GroupCreate(name="dba", description="DBA", initial_member_ids=[1, 2]),
        request=SimpleNamespace(client=SimpleNamespace(host="127.0.0.1")),
        db=db,
        current_user=user(is_superuser=True),
    )

    assert response.data.name == "dba"
    assert response.data.member_count == 2
    assert sum(obj.__class__.__name__ == "UserGroup" for obj in db.added) == 2
    assert audit_calls


@pytest.mark.asyncio
async def test_delete_group_rejects_default_group():
    db = FakeDB(FakeResult(scalar_one_or_none=group(is_default=True)))

    with pytest.raises(HTTPException) as exc:
        await users_api.delete_group(
            group_id=10,
            request=SimpleNamespace(client=SimpleNamespace(host="127.0.0.1")),
            db=db,
            current_user=user(is_superuser=True),
        )

    assert exc.value.status_code == 400
    assert "默认用户组" in exc.value.detail


@pytest.mark.asyncio
async def test_create_authorization_validates_and_persists(monkeypatch):
    audit_calls = []

    async def fake_log(*args, **kwargs):
        audit_calls.append((args, kwargs))

    monkeypatch.setattr(authz_api, "log_operation", fake_log)
    db = FakeDB(
        FakeResult(scalar_one_or_none=user()),
        FakeResult(scalar_one_or_none=asset(category="host")),
        FakeResult(scalar_one_or_none=None),
        FakeResult(scalar_one_or_none=user(username="target-user")),
        FakeResult(scalars=[asset(category="host", name="web-1")]),
    )

    response = await authz_api.create_authorization(
        data=AuthorizationCreate(
            entity_type="user",
            entity_id=1,
            target_type="asset",
            target_ids=["asset-1"],
            permissions=["view", "manage"],
        ),
        db=db,
        current_user=user(is_superuser=True),
        request=SimpleNamespace(client=SimpleNamespace(host="127.0.0.1")),
    )

    created = next(obj for obj in db.added if isinstance(obj, Authorization))
    assert response["message"] == "授权创建成功"
    assert response["data"]["permissions"] == ["view", "manage"]
    assert created.created_by == 1
    assert audit_calls


@pytest.mark.asyncio
async def test_create_authorization_rejects_duplicate():
    db = FakeDB(
        FakeResult(scalar_one_or_none=user()),
        FakeResult(scalar_one_or_none=asset(category="host")),
        FakeResult(scalar_one_or_none=auth()),
    )

    with pytest.raises(HTTPException) as exc:
        await authz_api.create_authorization(
            data=AuthorizationCreate(
                entity_type="user",
                entity_id=1,
                target_type="asset",
                target_ids=["asset-1"],
                permissions=["view"],
            ),
            db=db,
            current_user=user(is_superuser=True),
        )

    assert exc.value.status_code == 400
    assert exc.value.detail == "授权已存在"


@pytest.mark.asyncio
async def test_update_authorization_changes_permissions_and_active_state(monkeypatch):
    async def fake_log(*args, **kwargs):
        return None

    async def fake_entity_name(db, entity_type, entity_id):
        return "alice"

    async def fake_target_names(db, target_type, target_ids):
        return "db-primary"

    existing = auth(permissions=["view"], is_active=True)
    monkeypatch.setattr(authz_api, "log_operation", fake_log)
    monkeypatch.setattr(authz_api, "_resolve_entity_name", fake_entity_name)
    monkeypatch.setattr(authz_api, "_resolve_target_names", fake_target_names)
    db = FakeDB(FakeResult(scalar_one_or_none=existing))

    response = await authz_api.update_authorization(
        auth_id=50,
        data=authz_api.AuthorizationUpdate(permissions=["manage"], is_active=False),
        db=db,
        current_user=user(is_superuser=True),
    )

    assert existing.permissions == ["manage"]
    assert existing.is_active is False
    assert response["message"] == "授权更新成功"
    assert db.commits == 1


def test_authorization_datetime_format_uses_utc_z_suffix():
    assert authz_api.format_datetime_utc(datetime(2026, 1, 1, 12, 30, 0)) == "2026-01-01T12:30:00Z"
    assert authz_api.format_datetime_utc(None) is None


def test_permission_variant_helpers_include_transitive_implied_permissions():
    assert deps._satisfies_permission("manage", "view")
    assert deps._permission_variants("view") == {"view", "manage"}
    assert deps._permission_variants("view_users") == {"view_users", "user_mgmt"}


@pytest.mark.asyncio
async def test_get_authorized_asset_ids_superuser_gets_all_assets():
    assert await deps.get_authorized_asset_ids(user(is_superuser=True), FakeDB(), "view") is None


@pytest.mark.asyncio
async def test_get_authorized_asset_ids_no_authorizations_means_non_superuser_sees_none():
    assert await deps.get_authorized_asset_ids(user(), FakeDB(FakeResult(scalar=0)), "view") == set()


@pytest.mark.asyncio
async def test_get_user_permissions_superuser_has_management_permissions():
    permissions = set(await deps.get_user_permissions(user(is_superuser=True), FakeDB()))

    assert {"view", "manage", "authorize", "view_users", "user_mgmt", "view_pwd"}.issubset(permissions)


@pytest.mark.asyncio
async def test_check_resource_permission_allows_superuser_without_query():
    db = FakeDB()

    assert await deps.check_resource_permission(user(is_superuser=True), "manage", "asset", "asset-1", db)
    assert db.executed == []


class FakeUploadFile:
    def __init__(self, filename="assets.xlsx", content=b"PK\x03\x04data"):
        self.filename = filename
        self._content = content

    async def read(self):
        return self._content


def asset_with_credentials(**kwargs):
    item = asset(**kwargs)
    item.credentials = []
    return item


@pytest.mark.asyncio
async def test_create_asset_success_encrypts_oob_and_auto_authorizes_creator(monkeypatch):
    audit_calls = []

    async def fake_log(*args, **kwargs):
        audit_calls.append((args, kwargs))

    monkeypatch.setattr(asset_api, "log_operation", fake_log)
    db = FakeDB(
        FakeResult(scalar_one_or_none="Bob"),
        FakeResult(scalar_one_or_none=None),
    )

    response = await asset_api.create_asset(
        data=asset_api.AssetCreate(
            name="web-1",
            category="host",
            owner_id=2,
            internal_address="10.0.0.20",
            oob_address="10.0.1.20",
            oob_username="admin",
            oob_password="oob-pass",
            status="active",
        ),
        db=db,
        current_user=user(id=3, username="creator", is_superuser=False),
        request=SimpleNamespace(client=SimpleNamespace(host="127.0.0.1")),
    )

    created_asset = next(obj for obj in db.added if isinstance(obj, Asset))
    created_auth = next(obj for obj in db.added if isinstance(obj, Authorization))
    assert response["name"] == "web-1"
    assert response["creator_name"] == "creator"
    assert created_asset.owner_name == "Bob"
    assert created_asset.oob_password_encrypted.startswith("gAAAA")
    assert created_auth.entity_type == "user"
    assert created_auth.entity_id == 3
    assert created_auth.target_type == "asset"
    assert created_auth.permissions == ["manage"]
    assert audit_calls


@pytest.mark.asyncio
async def test_update_asset_success_updates_fields_encrypts_oob_and_checks_manage(monkeypatch):
    checked = {}
    audit_calls = []

    async def allow(current_user, permission, target_type, resource_id, db, organization_id=None):
        checked.update(
            permission=permission,
            target_type=target_type,
            resource_id=resource_id,
            organization_id=organization_id,
        )
        return True

    async def fake_log(*args, **kwargs):
        audit_calls.append((args, kwargs))

    existing = asset_with_credentials(category="host", name="old", owner_id=None, owner_name=None)
    reloaded = existing
    db = FakeDB(
        FakeResult(scalar_one_or_none=existing),
        FakeResult(scalar_one_or_none=2),
        FakeResult(scalar_one=reloaded),
    )
    monkeypatch.setattr(asset_api, "check_resource_permission", allow)
    monkeypatch.setattr(asset_api, "log_operation", fake_log)

    response = await asset_api.update_asset(
        asset_id="asset-1",
        data=asset_api.AssetUpdate(
            name="new-name",
            owner_name="bob",
            oob_password="new-oob",
            status="maintenance",
        ),
        db=db,
        current_user=user(is_superuser=True),
        request=SimpleNamespace(client=SimpleNamespace(host="127.0.0.1")),
    )

    assert response["name"] == "new-name"
    assert existing.owner_id == 2
    assert existing.oob_password_encrypted.startswith("gAAAA")
    assert existing.status == "maintenance"
    assert checked == {
        "permission": "manage",
        "target_type": "asset",
        "resource_id": "asset-1",
        "organization_id": 7,
    }
    assert audit_calls


@pytest.mark.asyncio
async def test_delete_asset_success_checks_manage_and_deletes(monkeypatch):
    checked = {}
    audit_calls = []

    async def allow(current_user, permission, target_type, resource_id, db, organization_id=None):
        checked["permission"] = permission
        checked["resource_id"] = resource_id
        checked["organization_id"] = organization_id
        return True

    async def fake_log(*args, **kwargs):
        audit_calls.append((args, kwargs))

    existing = asset(category="host", asset_code="CI-001")
    db = FakeDB(FakeResult(scalar_one_or_none=existing))
    monkeypatch.setattr(asset_api, "check_resource_permission", allow)
    monkeypatch.setattr(asset_api, "log_operation", fake_log)

    response = await asset_api.delete_asset(
        asset_id="asset-1",
        db=db,
        current_user=user(is_superuser=True),
        request=SimpleNamespace(client=SimpleNamespace(host="127.0.0.1")),
    )

    assert response.message == "资产已删除"
    assert db.deleted == [existing]
    assert checked == {"permission": "manage", "resource_id": "asset-1", "organization_id": 7}
    assert audit_calls


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


@pytest.mark.asyncio
async def test_import_assets_update_mode_filters_by_type_and_manage_permission(monkeypatch):
    allowed_records_seen = []

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
    monkeypatch.setattr(asset_api, "log_operation", lambda *args, **kwargs: None)

    async def fake_log(*args, **kwargs):
        return None

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
        return None

    item = asset_with_credentials(category="host", created_by_id=1)
    item.oob_password_encrypted = asset_api.encrypt_value("oob-secret")
    item.credentials = [
        Credential(
            id=1,
            asset_id="asset-1",
            username="root",
            password_encrypted=asset_api.encrypt_value("cred-secret"),
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


@pytest.mark.asyncio
async def test_create_authorization_group_to_organization_with_permission_combo(monkeypatch):
    audit_calls = []

    async def fake_log(*args, **kwargs):
        audit_calls.append((args, kwargs))

    monkeypatch.setattr(authz_api, "log_operation", fake_log)
    db = FakeDB(
        FakeResult(scalar_one_or_none=group(id=10, name="ops")),
        FakeResult(scalar_one_or_none=organization(id=7, name="Ops Node")),
        FakeResult(scalar_one_or_none=None),
        FakeResult(scalar_one_or_none=group(id=10, name="ops")),
        FakeResult(scalars=[organization(id=7, name="Ops Node")]),
    )

    response = await authz_api.create_authorization(
        data=AuthorizationCreate(
            entity_type="group",
            entity_id=10,
            target_type="organization",
            target_ids=["7"],
            permissions=["view", "manage", "export_pwd"],
        ),
        db=db,
        current_user=user(is_superuser=True),
        request=SimpleNamespace(client=SimpleNamespace(host="127.0.0.1")),
    )

    created = next(obj for obj in db.added if isinstance(obj, Authorization))
    assert response["data"]["entity_type"] == "group"
    assert response["data"]["target_type"] == "organization"
    assert created.permissions == ["view", "manage", "export_pwd"]
    assert audit_calls


@pytest.mark.asyncio
async def test_create_authorization_user_to_root_node_skips_org_lookup(monkeypatch):
    async def fake_log(*args, **kwargs):
        return None

    monkeypatch.setattr(authz_api, "log_operation", fake_log)
    db = FakeDB(
        FakeResult(scalar_one_or_none=user(id=2, username="bob")),
        FakeResult(scalar_one_or_none=None),
        FakeResult(scalar_one_or_none=user(id=2, username="bob")),
    )

    response = await authz_api.create_authorization(
        data=AuthorizationCreate(
            entity_type="user",
            entity_id=2,
            target_type="organization",
            target_ids=["__all__"],
            permissions=["view"],
        ),
        db=db,
        current_user=user(is_superuser=True),
    )

    assert response["data"]["target_ids"] == ["__all__"]
    assert len(db.executed) == 3


@pytest.mark.asyncio
async def test_check_resource_permission_falls_back_to_organization_node_grant():
    db = FakeDB(
        FakeResult(scalar_one_or_none=None),
        FakeResult(scalar_one_or_none=auth(target_type="organization", target_ids=["7"], permissions=["manage"])),
    )

    assert await deps.check_resource_permission(user(), "view", "asset", "asset-1", db, organization_id=7)


@pytest.mark.asyncio
async def test_get_authorized_asset_ids_expands_organization_node_descendants():
    db = FakeDB(
        FakeResult(scalar=1),
        FakeResult(all_rows=[]),
        FakeResult(scalars=[]),
        FakeResult(scalars=["7"]),
        FakeResult(all_rows=[(7, "1/7")]),
        FakeResult(all_rows=[(7,), (8,)]),
        FakeResult(scalars=["asset-a", "asset-b"]),
    )

    assert await deps.get_authorized_asset_ids(user(), db, "view") == {"asset-a", "asset-b"}


@pytest.mark.asyncio
async def test_get_authorized_asset_ids_group_asset_all_sentinel_grants_full_access():
    db = FakeDB(
        FakeResult(scalar=1),
        FakeResult(all_rows=[(10,)]),
        FakeResult(scalars=[]),
        FakeResult(scalars=["__all__"]),
    )

    assert await deps.get_authorized_asset_ids(user(), db, "manage") is None


@pytest.mark.asyncio
async def test_dashboard_recent_logins_include_date_and_time(monkeypatch):
    class Row:
        def __init__(self, value, count):
            self.value = value
            self.category = value
            self.count = count

        def __getitem__(self, index):
            if index == 0:
                return self.value
            if index == 1:
                return self.count
            raise IndexError(index)

    class FakeRedis:
        async def keys(self, pattern):
            return ["cmdb:online:1"]

    async def all_assets(current_user, db, permission="view"):
        return None

    async def view_users(current_user, db):
        return ["view_users"]

    monkeypatch.setattr(dashboard_api, "get_authorized_asset_ids", all_assets)
    monkeypatch.setattr(dashboard_api, "get_user_permissions", view_users)
    monkeypatch.setattr(dashboard_api, "get_redis", lambda: FakeRedis())

    login_log = SimpleNamespace(
        created_at=datetime(2026, 7, 8, 9, 5, 30),
        ip_address="10.0.0.1",
        user_id=1,
        username="alice",
    )
    login_user = SimpleNamespace(username="alice", full_name="Alice")
    db = FakeDB(
        FakeResult(scalar=12),
        FakeResult(all_rows=[Row("host", 7)]),
        FakeResult(all_rows=[Row("running", 5)]),
        FakeResult(all_rows=[]),
        FakeResult(all_rows=[]),
        FakeResult(all_rows=[]),
        FakeResult(all_rows=[]),
        FakeResult(all_rows=[]),
        FakeResult(all_rows=[]),
        FakeResult(scalar=3),
        FakeResult(scalar=2),
        FakeResult(all_rows=[(login_log, login_user)]),
    )

    response = await dashboard_api.get_dashboard_stats(db=db, current_user=user())

    assert any("row_number" in str(statement) and "PARTITION BY" in str(statement) for statement in db.executed)
    assert response["data"]["recent_logins"] == [
        {
            "user": "Alice",
            "time": "2026-07-08T09:05:30Z",
            "ip": "10.0.0.1",
            "user_id": 1,
            "is_online": True,
        }
    ]
