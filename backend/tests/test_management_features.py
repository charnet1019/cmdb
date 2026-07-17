from datetime import datetime
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, Response

from tests.factories import FakeDB, FakeRedisSessionStore, FakeResult, asset, auth, group, organization, user

from app.api import assets as asset_api
from app.api import auth as auth_api
from app.api import auth_mfa as auth_mfa_api
from app.api import authorizations as authz_api
from app.api import deps
from app.api import dashboard as dashboard_api
from app.api import logs_operation as logs_operation_api
from app.api import settings as settings_api
from app.api import notifications as notifications_api
from app.api import users as users_api
from app.api import groups as groups_api
from app.api import user_account as account_api
from app.models import Asset, Authorization, Notification, NotificationReceipt, OperationLog, Setting, User
from app.schemas import AuthorizationCreate, GroupCreate, UserCreate, PasswordResetRequest, UserUpdate


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

    monkeypatch.setattr(groups_api, "log_operation", fake_log)
    db = FakeDB(FakeResult(scalar_one_or_none=None))

    response = await groups_api.create_group(
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
        await groups_api.delete_group(
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
    monkeypatch.setattr(authz_api, "resolve_target_names", fake_target_names)
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


def test_operation_log_formatter_uses_concise_mfa_action_summary():
    log = OperationLog(
        id=1,
        user_id=1,
        action="update",
        resource_type="user",
        resource_id=2,
        details={
            "action": "mfa_disable",
            "username": "bob",
            "changes": {
                "mfa_enabled": [True, False],
                "mfa_bound": [True, False],
            },
        },
        ip_address="127.0.0.1",
        status="success",
        created_at=datetime(2026, 1, 1, 12, 0, 0),
    )

    formatted = logs_operation_api._format_operation_log(log, "admin")

    assert formatted["action_label"] == "更新"
    assert formatted["resource_type_label"] == "用户"
    assert formatted["detail_action_label"] == "禁用MFA"
    assert formatted["operation_summary"] == "禁用MFA"
    assert formatted["change_items"] == []


def test_operation_log_formatter_promotes_user_enable_disable_summary():
    log = OperationLog(
        id=3,
        user_id=1,
        action="update",
        resource_type="user",
        resource_id=2,
        details={
            "username": "test",
            "changes": {
                "group_ids": [None, [6]],
                "is_active": [False, True],
            },
        },
        ip_address="127.0.0.1",
        status="success",
        created_at=datetime(2026, 1, 1, 12, 0, 0),
    )

    formatted = logs_operation_api._format_operation_log(log, "admin")

    assert formatted["operation_summary"] == "启用用户"
    assert formatted["change_items"] == []


def test_operation_log_formatter_promotes_user_disable_summary():
    log = OperationLog(
        id=8,
        user_id=1,
        action="update",
        resource_type="user",
        resource_id=2,
        details={
            "username": "test",
            "changes": {"is_active": [True, False]},
        },
        ip_address="127.0.0.1",
        status="success",
        created_at=datetime(2026, 1, 1, 12, 0, 0),
    )

    formatted = logs_operation_api._format_operation_log(log, "admin")

    assert formatted["operation_summary"] == "禁用用户"
    assert formatted["change_items"] == []


def test_operation_log_formatter_promotes_mfa_enable_summary():
    log = OperationLog(
        id=9,
        user_id=1,
        action="update",
        resource_type="user",
        resource_id=2,
        details={
            "username": "test",
            "changes": {"mfa_enabled": [False, True]},
        },
        ip_address="127.0.0.1",
        status="success",
        created_at=datetime(2026, 1, 1, 12, 0, 0),
    )

    formatted = logs_operation_api._format_operation_log(log, "admin")

    assert formatted["operation_summary"] == "启用MFA"
    assert formatted["change_items"] == []


def test_operation_log_formatter_names_logout_cleanly():
    log = OperationLog(
        id=4,
        user_id=1,
        action="update",
        resource_type="auth",
        resource_id=0,
        details={"name": "logout", "action": "logout"},
        ip_address="127.0.0.1",
        status="success",
        created_at=datetime(2026, 1, 1, 12, 0, 0),
    )

    formatted = logs_operation_api._format_operation_log(log, "alice")

    assert formatted["resource_type_label"] == "认证"
    assert formatted["detail_action_label"] == "用户登出"
    assert formatted["operation_summary"] == "用户登出"


def test_operation_log_formatter_omits_group_target_from_summary():
    log = OperationLog(
        id=5,
        user_id=1,
        action="add_group_members",
        resource_type="group",
        resource_id=6,
        details={"name": "ops", "user_ids": [2, 3], "added": 2},
        ip_address="127.0.0.1",
        status="success",
        created_at=datetime(2026, 1, 1, 12, 0, 0),
    )

    formatted = logs_operation_api._format_operation_log(log, "admin")

    assert formatted["resource_name"] == "ops"
    assert formatted["operation_summary"] == "添加组成员: 2 名"


def test_operation_log_formatter_omits_config_target_and_resolves_resource_name():
    log = OperationLog(
        id=6,
        user_id=1,
        action="update",
        resource_type="asset",
        resource_id=0,
        details={
            "action": "upload_config",
            "asset_name": "network-1",
            "filename": "network.cfg",
        },
        ip_address="127.0.0.1",
        status="success",
        created_at=datetime(2026, 1, 1, 12, 0, 0),
    )

    formatted = logs_operation_api._format_operation_log(log, "admin")

    assert formatted["resource_name"] == "network-1 / network.cfg"
    assert formatted["operation_summary"] == "上传配置文件 network.cfg"


def test_operation_log_formatter_describes_group_description_change_naturally():
    log = OperationLog(
        id=7,
        user_id=1,
        action="update",
        resource_type="group",
        resource_id=6,
        details={
            "name": "rd",
            "changes": {"description": ["测试qq", "测试qq55"]},
        },
        ip_address="127.0.0.1",
        status="success",
        created_at=datetime(2026, 1, 1, 12, 0, 0),
    )

    formatted = logs_operation_api._format_operation_log(log, "admin")

    assert formatted["resource_name"] == "rd"
    assert formatted["operation_summary"] == "将描述从测试qq修改为测试qq55"


def test_operation_log_formatter_summarizes_setting_changes():
    log = OperationLog(
        id=2,
        user_id=1,
        action="update",
        resource_type="setting",
        resource_id=0,
        details={
            "name": "batch_update",
            "keys": ["session_timeout"],
            "changes": {"session_timeout": [30, 120]},
        },
        ip_address="127.0.0.1",
        status="success",
        created_at=datetime(2026, 1, 1, 12, 0, 0),
    )

    formatted = logs_operation_api._format_operation_log(log, "admin")

    assert formatted["resource_type_label"] == "系统设置"
    assert formatted["resource_name"] == "会话超时时间"
    assert formatted["operation_summary"] == "将会话超时时间从30修改为120"
    assert formatted["change_items"] == [
        {
            "field": "session_timeout",
            "label": "会话超时时间",
            "before": "30",
            "after": "120",
            "summary": "会话超时时间: 30 -> 120",
        }
    ]


def test_operation_log_formatter_uses_setting_labels_for_login_log_retention():
    log = OperationLog(
        id=10,
        user_id=1,
        action="update",
        resource_type="setting",
        resource_id=0,
        details={
            "name": "login_log_retention",
            "changes": {"login_log_retention": [30, 29]},
        },
        ip_address="127.0.0.1",
        status="success",
        created_at=datetime(2026, 1, 1, 12, 0, 0),
    )

    formatted = logs_operation_api._format_operation_log(log, "admin")

    assert formatted["resource_name"] == "登录日志保留天数"
    assert formatted["operation_summary"] == "将登录日志保留天数从30修改为29"


def test_operation_log_formatter_uses_setting_labels_for_password_complexity():
    log = OperationLog(
        id=11,
        user_id=1,
        action="update",
        resource_type="setting",
        resource_id=0,
        details={
            "name": "password_require_special",
            "changes": {"password_require_special": [False, True]},
        },
        ip_address="127.0.0.1",
        status="success",
        created_at=datetime(2026, 1, 1, 12, 0, 0),
    )

    formatted = logs_operation_api._format_operation_log(log, "admin")

    assert formatted["resource_name"] == "密码至少包含特殊字符"
    assert formatted["operation_summary"] == "将密码至少包含特殊字符从否修改为是"


def test_operation_log_formatter_uses_setting_labels_for_otp_issuer_name():
    log = OperationLog(
        id=12,
        user_id=1,
        action="update",
        resource_type="setting",
        resource_id=0,
        details={
            "name": "otp_issuer_name",
            "changes": {"otp_issuer_name": ["CMDB智昌", "CMDB"]},
        },
        ip_address="127.0.0.1",
        status="success",
        created_at=datetime(2026, 1, 1, 12, 0, 0),
    )

    formatted = logs_operation_api._format_operation_log(log, "admin")

    assert formatted["resource_name"] == "OTP 验证器名称"
    assert formatted["operation_summary"] == "将OTP 验证器名称从CMDB智昌修改为CMDB"


def test_operation_log_formatter_groups_brand_settings_batch_updates():
    log = OperationLog(
        id=13,
        user_id=1,
        action="update",
        resource_type="setting",
        resource_id=0,
        details={
            "name": "batch_update",
            "keys": ["site_title", "login_subtitle", "logo_image"],
            "changes": {
                "site_title": ["CMDB智昌", "CMDB"],
                "login_subtitle": ["企业资产配置管理平台", "资产管理平台"],
                "logo_image": ["/uploads/old.png", "/uploads/new.png"],
            },
        },
        ip_address="127.0.0.1",
        status="success",
        created_at=datetime(2026, 1, 1, 12, 0, 0),
    )

    formatted = logs_operation_api._format_operation_log(log, "admin")

    assert formatted["resource_name"] == "品牌设置"
    assert formatted["operation_summary"] == "更新品牌设置"


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
async def test_create_asset_auto_authorize_query_excludes_time_boxed_authorizations(monkeypatch):
    """Reusing a time-boxed 'manage' authorization to host a brand-new asset would make the
    asset silently inherit an unrelated expiry window. The lookup query must only match
    permanent (valid_from/valid_until both NULL) authorizations."""
    monkeypatch.setattr(asset_api, "log_operation", lambda *a, **k: _noop())

    db = FakeDB(
        FakeResult(scalar_one_or_none="Bob"),
        # No permanent authorization exists — even though a time-boxed one might, the
        # real DB query (with the IS NULL filters) would not return it here.
        FakeResult(scalar_one_or_none=None),
    )

    await asset_api.create_asset(
        data=asset_api.AssetCreate(
            name="web-2",
            category="host",
            owner_id=2,
            internal_address="10.0.0.21",
            status="active",
        ),
        db=db,
        current_user=user(id=3, username="creator", is_superuser=False),
        request=SimpleNamespace(client=SimpleNamespace(host="127.0.0.1")),
    )

    lookup_query = db.executed[1]
    compiled = str(lookup_query)
    assert "valid_from IS NULL" in compiled
    assert "valid_until IS NULL" in compiled

    created_auth = next(obj for obj in db.added if isinstance(obj, Authorization))
    assert created_auth.target_ids == [created_auth.target_ids[0]]  # fresh row, not appended to an existing one


async def _noop():
    return None


# test_update_asset_success_updates_fields_encrypts_oob_and_checks_manage and
# test_delete_asset_success_checks_manage_and_deletes live in
# tests/test_asset_detail.py (update_asset/delete_asset moved to
# app.api.asset_detail during the router split).


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


from datetime import timedelta
import app.core.session as session_core


@pytest.mark.asyncio
async def test_redis_session_create_delete_and_force_logout(monkeypatch):
    redis_store = FakeRedisSessionStore()
    monkeypatch.setattr(session_core, "get_redis", lambda: redis_store)
    request = SimpleNamespace(
        client=SimpleNamespace(host="10.0.0.10"),
        headers={"user-agent": "pytest"},
    )

    session_id_1, expires_at = await session_core.create_user_session(7, request, timedelta(minutes=30))
    session_id_2, _ = await session_core.create_user_session(7, request, timedelta(minutes=30))

    payload = await session_core.load_user_session(session_id_1)
    assert payload["user_id"] == 7
    assert payload["ip_address"] == "10.0.0.10"
    assert expires_at.tzinfo is not None
    assert set(await session_core.get_active_user_session_ids(7)) == {session_id_1, session_id_2}

    assert await session_core.delete_user_session(session_id_1, 7) is True
    assert not await redis_store.exists(f"{session_core.SESSION_KEY_PREFIX}{session_id_1}")
    assert await redis_store.exists(f"{session_core.ONLINE_KEY_PREFIX}7")
    assert await session_core.get_active_user_session_ids(7) == [session_id_2]

    assert await session_core.force_logout_user(7) == 1
    assert await session_core.get_active_user_session_ids(7) == []
    assert not await redis_store.exists(f"{session_core.ONLINE_KEY_PREFIX}7")


@pytest.mark.asyncio
async def test_get_current_user_loads_redis_session(monkeypatch):
    async def load_session(session_id):
        assert session_id == "session-1"
        return {"session_id": session_id, "user_id": 2}

    monkeypatch.setattr(deps, "load_user_session", load_session)
    request = SimpleNamespace(cookies={}, state=SimpleNamespace())
    current = user(id=2, username="bob")

    result = await deps.get_current_user(
        request=request,
        response=Response(),
        credentials=SimpleNamespace(credentials="session-1"),
        db=FakeDB(FakeResult(scalar_one_or_none=current)),
    )

    assert result is current
    assert request.state.session_id == "session-1"
    assert request.state.session["user_id"] == 2


@pytest.mark.asyncio
async def test_get_current_user_extends_active_business_request_session(monkeypatch):
    extend_calls = []

    async def load_session(session_id):
        assert session_id == "session-1"
        return {
            "session_id": session_id,
            "user_id": 2,
            "timeout_seconds": 1800,
            "expires_at": "2026-01-01T00:10:00Z",
        }

    async def extend_session(session_id):
        extend_calls.append(session_id)
        return {
            "session_id": session_id,
            "user_id": 2,
            "timeout_seconds": 1800,
            "expires_at": "2026-01-01T00:30:00Z",
        }

    monkeypatch.setattr(deps, "load_user_session", load_session)
    monkeypatch.setattr(deps, "extend_user_session", extend_session)
    request = SimpleNamespace(
        cookies={},
        headers={"x-cmdb-user-active": "1"},
        state=SimpleNamespace(),
        url=SimpleNamespace(path="/api/v1/assets", scheme="http"),
    )
    response = Response()
    current = user(id=2, username="bob")

    result = await deps.get_current_user(
        request=request,
        response=response,
        credentials=SimpleNamespace(credentials="session-1"),
        db=FakeDB(FakeResult(scalar_one_or_none=current)),
    )

    assert result is current
    assert extend_calls == ["session-1"]
    assert request.state.session["expires_at"] == "2026-01-01T00:30:00Z"
    assert response.headers[deps.SESSION_EXPIRES_HEADER] == "2026-01-01T00:30:00Z"
    assert "cmdb_access_token=session-1" in response.headers["set-cookie"]
    assert "Max-Age=1800" in response.headers["set-cookie"]


@pytest.mark.asyncio
async def test_get_current_user_info_includes_session_expires_at(monkeypatch):
    async def fake_permissions(current_user, db):
        return ["view"]

    monkeypatch.setattr(auth_api, "get_user_permissions", fake_permissions)
    request = SimpleNamespace(
        cookies={},
        state=SimpleNamespace(session={"expires_at": "2026-01-01T00:10:00Z"}),
    )
    current = user(id=2, username="bob")

    response = await auth_api.get_current_user_info(
        request=request,
        current_user=current,
        db=FakeDB(),
    )

    assert response.data.username == "bob"
    assert response.data.session_expires_at is not None
    assert response.data.session_expires_at.tzinfo is not None
    assert response.data.session_expires_at.isoformat().startswith("2026-01-01T00:10:00")


@pytest.mark.asyncio
async def test_get_current_user_forces_logout_when_user_disabled(monkeypatch):
    force_calls = []

    async def load_session(session_id):
        return {"session_id": session_id, "user_id": 2}

    async def force_logout(user_id):
        force_calls.append(user_id)
        return 2

    monkeypatch.setattr(deps, "load_user_session", load_session)
    monkeypatch.setattr(deps, "force_logout_user", force_logout)

    with pytest.raises(HTTPException) as exc:
        await deps.get_current_user(
            request=SimpleNamespace(cookies={}, state=SimpleNamespace()),
            response=Response(),
            credentials=SimpleNamespace(credentials="session-1"),
            db=FakeDB(FakeResult(scalar_one_or_none=user(id=2, is_active=False))),
        )

    assert exc.value.status_code == 403
    assert exc.value.detail == "用户已被禁用"
    assert force_calls == [2]


@pytest.mark.asyncio
async def test_update_user_disabling_active_user_forces_logout(monkeypatch):
    force_calls = []

    async def force_logout(user_id):
        force_calls.append(user_id)
        return 2

    async def fake_log(*args, **kwargs):
        return None

    monkeypatch.setattr(users_api, "force_logout_user", force_logout)
    monkeypatch.setattr(users_api, "log_operation", fake_log)
    target = user(id=2, username="bob", is_active=True)
    db = FakeDB(FakeResult(scalar_one_or_none=target), FakeResult(scalars=[]))

    response = await users_api.update_user(
        user_id=2,
        data=UserUpdate(is_active=False),
        request=SimpleNamespace(client=SimpleNamespace(host="127.0.0.1")),
        db=db,
        current_user=user(id=1, is_superuser=True),
    )

    assert response.data.is_active is False
    assert force_calls == [2]
    assert db.commits == 1


@pytest.mark.asyncio
async def test_update_user_ignores_unchanged_group_ids_in_audit(monkeypatch):
    audit_calls = []

    async def fake_log(*args, **kwargs):
        audit_calls.append((args, kwargs))

    monkeypatch.setattr(users_api, "log_operation", fake_log)
    target = user(id=2, username="bob", full_name="test66")
    existing_membership = SimpleNamespace(group_id=6)
    db = FakeDB(
        FakeResult(scalar_one_or_none=target),
        FakeResult(scalars=[existing_membership]),
        FakeResult(scalars=[group(id=6, name="rd")]),
    )

    response = await users_api.update_user(
        user_id=2,
        data=UserUpdate(full_name="test77", group_ids=[6]),
        request=SimpleNamespace(client=SimpleNamespace(host="127.0.0.1")),
        db=db,
        current_user=user(id=1, is_superuser=True),
    )

    assert response.data.full_name == "test77"
    assert db.deleted == []
    assert db.added == []
    changes = audit_calls[0][1]["details"]["changes"]
    assert changes == {"full_name": ["test66", "test77"]}


@pytest.mark.asyncio
async def test_update_user_disabling_mfa_logs_bound_state(monkeypatch):
    audit_calls = []

    async def fake_log(*args, **kwargs):
        audit_calls.append((args, kwargs))

    monkeypatch.setattr(users_api, "log_operation", fake_log)
    target = user(id=2, username="bob", mfa_enabled=True, mfa_secret="secret")
    db = FakeDB(FakeResult(scalar_one_or_none=target), FakeResult(scalars=[]))

    response = await users_api.update_user(
        user_id=2,
        data=UserUpdate(mfa_enabled=False),
        request=SimpleNamespace(client=SimpleNamespace(host="127.0.0.1")),
        db=db,
        current_user=user(id=1, is_superuser=True),
    )

    assert response.data.mfa_enabled is False
    assert response.data.mfa_bound is False
    changes = audit_calls[0][1]["details"]["changes"]
    assert changes["mfa_enabled"] == [True, False]
    assert changes["mfa_bound"] == [True, False]


@pytest.mark.asyncio
async def test_reset_mfa_logs_target_and_state(monkeypatch):
    audit_calls = []

    async def fake_log(*args, **kwargs):
        audit_calls.append((args, kwargs))

    monkeypatch.setattr(auth_mfa_api, "log_operation", fake_log)
    target = user(id=2, username="bob", mfa_enabled=True, mfa_secret="secret")

    response = await auth_mfa_api.reset_mfa(
        request=SimpleNamespace(client=SimpleNamespace(host="127.0.0.1")),
        user_id=2,
        db=FakeDB(FakeResult(scalar_one_or_none=target)),
        current_user=user(id=1, is_superuser=True),
    )

    assert response.message == "MFA 已重置，用户下次登录需重新绑定"
    details = audit_calls[0][1]["details"]
    assert details["username"] == "bob"
    assert details["changes"]["mfa_bound"] == [True, False]
    assert details["changes"]["mfa_enabled"] == [True, True]


@pytest.mark.asyncio
async def test_disable_mfa_logs_target_and_state(monkeypatch):
    audit_calls = []

    async def fake_log(*args, **kwargs):
        audit_calls.append((args, kwargs))

    monkeypatch.setattr(auth_mfa_api, "log_operation", fake_log)
    target = user(id=2, username="bob", mfa_enabled=True, mfa_secret="secret")

    response = await auth_mfa_api.disable_mfa(
        request=SimpleNamespace(client=SimpleNamespace(host="127.0.0.1")),
        user_id=2,
        db=FakeDB(FakeResult(scalar_one_or_none=target)),
        current_user=user(id=1, is_superuser=True),
    )

    assert response.message == "MFA 已禁用"
    details = audit_calls[0][1]["details"]
    assert details["username"] == "bob"
    assert details["changes"]["mfa_enabled"] == [True, False]
    assert details["changes"]["mfa_bound"] == [True, False]


@pytest.mark.asyncio
async def test_login_mfa_setup_logs_bind_without_secret(monkeypatch):
    audit_calls = []
    target = user(id=2, username="bob", mfa_enabled=True, mfa_secret=None)

    class FakeRedis:
        async def get(self, key):
            return "totp-secret"

        async def delete(self, key):
            return 1

    async def fake_load_challenge(challenge_token, request):
        return {"user_id": target.id, "remember": False}

    async def fake_get_challenge_user(payload, db):
        return target

    async def fake_delete_challenge(challenge_token):
        return None

    async def fake_complete_login(*args, **kwargs):
        return SimpleNamespace(ok=True)

    async def fake_log(*args, **kwargs):
        audit_calls.append((args, kwargs))

    async def no_rate_limit(*args, **kwargs):
        return None

    monkeypatch.setattr(auth_mfa_api, "get_redis", lambda: FakeRedis())
    monkeypatch.setattr(auth_mfa_api, "check_mfa_verify_rate_limit", no_rate_limit)
    monkeypatch.setattr(auth_mfa_api, "_load_login_challenge", fake_load_challenge)
    monkeypatch.setattr(auth_mfa_api, "_get_challenge_user", fake_get_challenge_user)
    monkeypatch.setattr(auth_mfa_api, "_delete_login_challenge", fake_delete_challenge)
    monkeypatch.setattr(auth_mfa_api, "verify_totp", lambda secret, code: True)
    monkeypatch.setattr(auth_mfa_api, "_complete_login", fake_complete_login)
    monkeypatch.setattr(auth_mfa_api, "log_operation", fake_log)

    response = await auth_mfa_api.login_mfa_verify(
        request=SimpleNamespace(client=SimpleNamespace(host="127.0.0.1"), headers={}),
        response=SimpleNamespace(),
        data=auth_mfa_api.MFAVerifyRequest(challenge_token="challenge", code="123456", setup=True),
        db=FakeDB(),
    )

    assert response.ok is True
    assert auth_mfa_api._decrypt_mfa_secret(target.mfa_secret) == "totp-secret"
    details = audit_calls[0][1]["details"]
    assert details["action"] == "mfa_bind"
    assert details["username"] == "bob"
    assert details["changes"]["mfa_bound"] == [False, True]
    assert "totp-secret" not in str(details)


@pytest.mark.asyncio
async def test_force_logout_user_sessions_endpoint(monkeypatch):
    force_calls = []
    audit_calls = []

    async def force_logout(user_id):
        force_calls.append(user_id)
        return 3

    async def fake_log(*args, **kwargs):
        audit_calls.append((args, kwargs))

    monkeypatch.setattr(account_api, "force_logout_user", force_logout)
    monkeypatch.setattr(account_api, "log_operation", fake_log)

    response = await account_api.force_logout_user_sessions(
        user_id=2,
        request=SimpleNamespace(client=SimpleNamespace(host="127.0.0.1")),
        db=FakeDB(FakeResult(scalar_one_or_none=user(id=2, username="bob"))),
        current_user=user(id=1, is_superuser=True),
    )

    assert response.message == "用户已强制离线"
    assert response.data == {"terminated_sessions": 3}
    assert force_calls == [2]
    assert audit_calls


@pytest.mark.asyncio
async def test_force_logout_user_sessions_rejects_self():
    with pytest.raises(HTTPException) as exc:
        await account_api.force_logout_user_sessions(
            user_id=1,
            request=SimpleNamespace(client=SimpleNamespace(host="127.0.0.1")),
            db=FakeDB(),
            current_user=user(id=1, is_superuser=True),
        )

    assert exc.value.status_code == 400
    assert exc.value.detail == "不能强制离线自己"


def setting(key, value):
    return Setting(key=key, value={"value": value})


def test_smtp_password_setting_is_encrypted_and_masked():
    encrypted = settings_api._normalize_setting("smtp_password", "mail-secret")

    assert encrypted != "mail-secret"
    assert encrypted.startswith("gAAAA")
    assert settings_api._response_setting_value("smtp_password", encrypted) == settings_api.SMTP_PASSWORD_MASK
    assert settings_api._normalize_setting("smtp_password", settings_api.SMTP_PASSWORD_MASK, encrypted) == encrypted
    assert settings_api._normalize_setting("smtp_password", "", encrypted) == ""


@pytest.mark.asyncio
async def test_create_user_auto_password_sends_email_before_commit(monkeypatch):
    sent = []

    async def fake_send(db, target_user, temp_password, action):
        sent.append((target_user.email, target_user.username, temp_password, action))

    audit_calls = []

    async def fake_log(*args, **kwargs):
        audit_calls.append((args, kwargs))

    monkeypatch.setattr(users_api, "send_user_password_email", fake_send)
    monkeypatch.setattr(users_api, "log_operation", fake_log)

    db = FakeDB(
        FakeResult(scalar_one_or_none=None),
        FakeResult(scalar_one_or_none=None),
        FakeResult(scalar_one_or_none=setting("password_min_length", 12)),
        FakeResult(scalar_one_or_none=setting("password_min_length", 12)),
        FakeResult(scalar_one_or_none=setting("password_require_uppercase", True)),
        FakeResult(scalar_one_or_none=setting("password_require_lowercase", True)),
        FakeResult(scalar_one_or_none=setting("password_require_digit", True)),
        FakeResult(scalar_one_or_none=setting("password_require_special", False)),
        FakeResult(scalar_one_or_none=None),  # password_history_count -> default
        FakeResult(),  # stale password_history ids to prune -> none
        FakeResult(scalars=[]),
    )

    response = await users_api.create_user(
        data=UserCreate(
            username="new-user",
            email="new-user@example.com",
            password_method="auto",
            send_email=True,
        ),
        request=SimpleNamespace(client=SimpleNamespace(host="127.0.0.1")),
        db=db,
        current_user=user(is_superuser=True),
    )

    created = next(obj for obj in db.added if isinstance(obj, User))
    assert response.data.username == "new-user"
    assert created.password_hash != sent[0][2]
    assert sent[0][0] == "new-user@example.com"
    assert sent[0][3] == "create"
    assert db.commits >= 1
    audit_details = audit_calls[0][1]["details"]
    assert audit_details["is_active"] is True
    assert audit_details["mfa_enabled"] is False
    assert audit_details["mfa_bound"] is False
    assert audit_details["group_ids"] == []


@pytest.mark.asyncio
async def test_reset_user_password_auto_sends_email_and_hides_temp_password(monkeypatch):
    sent = []

    async def fake_send(db, target_user, temp_password, action):
        sent.append((target_user.email, temp_password, action))

    monkeypatch.setattr(account_api, "send_user_password_email", fake_send)
    target = user(id=2, username="bob", email="bob@example.com", password_hash="old-hash")
    db = FakeDB(
        FakeResult(scalar_one_or_none=target),
        FakeResult(scalar_one_or_none=setting("password_min_length", 12)),
        FakeResult(scalar_one_or_none=None),  # password_history_count -> default
        FakeResult(),  # stale password_history ids to prune -> none
    )

    response = await account_api.reset_user_password(
        user_id=2,
        data=PasswordResetRequest(method="auto", force_change=True, send_email=True),
        request=SimpleNamespace(client=SimpleNamespace(host="127.0.0.1")),
        db=db,
        current_user=user(id=1, is_superuser=True),
    )

    assert response.data == {"email_sent": True, "temp_password": None}
    assert target.must_change_password is True
    assert sent[0][0] == "bob@example.com"
    assert sent[0][2] == "reset"
    assert any(getattr(obj, "change_type", None) == "user_password" for obj in db.added)



@pytest.mark.asyncio
async def test_notification_send_permission_allows_superuser_and_asset_permissions(monkeypatch):
    assert await notifications_api._can_send_notifications(user(is_superuser=True), FakeDB()) is True

    async def manage_permissions(current_user, db):
        return ["view", "manage"]

    async def view_permissions(current_user, db):
        return ["view"]

    monkeypatch.setattr(notifications_api, "get_user_permissions", manage_permissions)
    assert await notifications_api._can_send_notifications(user(id=2), FakeDB()) is True

    monkeypatch.setattr(notifications_api, "get_user_permissions", view_permissions)
    assert await notifications_api._can_send_notifications(user(id=2), FakeDB()) is False


@pytest.mark.asyncio
async def test_create_notification_persists_receipts_and_publishes_events(monkeypatch):
    published = []

    async def publish(user_id, event_type, data):
        published.append((user_id, event_type, data))
        return 1

    monkeypatch.setattr(notifications_api, "publish_user_event", publish)
    db = FakeDB(FakeResult(all_rows=[(2,), (3,)]))

    response = await notifications_api.create_notification(
        data=notifications_api.NotificationCreate(
            title="维护通知",
            content="今晚 22:00 维护",
            recipient_scope="users",
            user_ids=[2, 3],
        ),
        db=db,
        current_user=user(id=1, username="admin", is_superuser=True),
    )

    assert response["message"] == "站内信已发送"
    assert response["data"]["recipient_count"] == 2
    added_notifications = [obj for obj in db.added if isinstance(obj, Notification)]
    added_receipts = [obj for obj in db.added if isinstance(obj, NotificationReceipt)]
    assert len(added_notifications) == 1
    assert {receipt.user_id for receipt in added_receipts} == {2, 3}
    assert [(user_id, event_type) for user_id, event_type, _ in published] == [(2, "notification"), (3, "notification")]
    assert all(event_data["receipt_id"] for _, _, event_data in published)
    assert db.commits == 1


@pytest.mark.asyncio
async def test_notification_unread_count_and_mark_read():
    receipt = NotificationReceipt(id=7, notification_id=20, user_id=2, read_at=None)
    count_response = await notifications_api.unread_count(
        db=FakeDB(FakeResult(scalar=3)),
        current_user=user(id=2),
    )
    assert count_response["data"] == {"count": 3}

    read_response = await notifications_api.mark_notification_read(
        receipt_id=7,
        db=FakeDB(FakeResult(scalar_one_or_none=receipt)),
        current_user=user(id=2),
    )
    assert read_response["data"] == {"id": 7}
    assert receipt.read_at is not None


@pytest.mark.asyncio
async def test_force_logout_user_sessions_publishes_sse_event(monkeypatch):
    published = []

    async def force_logout(user_id):
        return 1

    async def publish(user_id, event_type, data):
        published.append((user_id, event_type, data))
        return 1

    async def fake_log(*args, **kwargs):
        return None

    monkeypatch.setattr(account_api, "force_logout_user", force_logout)
    monkeypatch.setattr(users_api, "publish_user_event", publish)
    monkeypatch.setattr(account_api, "log_operation", fake_log)

    response = await account_api.force_logout_user_sessions(
        user_id=2,
        request=SimpleNamespace(client=SimpleNamespace(host="127.0.0.1")),
        db=FakeDB(FakeResult(scalar_one_or_none=user(id=2, username="bob"))),
        current_user=user(id=1, is_superuser=True),
    )

    assert response.data == {"terminated_sessions": 1}
    assert published == [(2, "force_logout", {"reason": "admin_forced", "message": "账号已被管理员强制离线"})]


