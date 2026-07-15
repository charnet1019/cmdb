"""
Log Audit API
Login logs, operation logs, and password change logs
"""
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, cast, String, alias

from app.database import get_db
from app.models import User, LoginLog, OperationLog, PasswordChangeLog, Asset, Credential
from app.api.deps import PermissionChecker
from app.core.asset_categories import ASSET_CATEGORY_LABELS, asset_category_label
from app.utils.audit import log_operation
from app.utils.datetime_utils import format_datetime_utc
from app.utils.pagination import get_pagination_meta
from app.services.log_cleanup import cleanup_expired_logs


def _asset_operation_target_name(action: str | None, details: dict) -> str | None:
    target_name = details.get("target_name")
    if target_name:
        return str(target_name)

    category = details.get("category")
    scope = details.get("scope")
    name = details.get("name")

    if action == "export":
        if category:
            return f"{asset_category_label(str(category))}资产"
        if isinstance(name, str) and name.startswith("export_"):
            legacy = name.removeprefix("export_")
            if legacy in ASSET_CATEGORY_LABELS:
                return f"{asset_category_label(legacy)}资产"
            scope = legacy
        if scope == "selected":
            return "选中资产"
        if scope == "filtered":
            return "筛选资产"
        return "全部资产"

    if action == "import":
        if category:
            return f"{asset_category_label(str(category))}资产"
        if isinstance(name, str) and name.startswith("import_"):
            legacy = name.removeprefix("import_")
            if legacy in ASSET_CATEGORY_LABELS:
                return f"{asset_category_label(legacy)}资产"

    if details.get("action") == "download_import_template":
        if category:
            return f"{asset_category_label(str(category))}资产"
        return "资产"

    return None


def _get_resource_name(log: OperationLog) -> Optional[str]:
    """Resolve resource name from details or resource_id.

    The previous one-liner had a precedence bug: the ternary
    ``if log.resource_id else None`` applied to the entire
    expression, so when resource_id was 0 (falsy) the whole thing
    returned None — even though details.name might hold a real
    name.  This function checks details fields first, then falls
    back to resource_id only when details have nothing.
    """
    details = log.details or {}
    if not isinstance(details, dict):
        details = {}

    detail_action = details.get("action")
    if detail_action == "logout":
        return None

    if log.resource_type == "group":
        name = details.get("group_name") or details.get("name")
    elif log.resource_type == "asset":
        if detail_action in {"download_config", "upload_config", "save_config", "rollback_config", "delete_config"}:
            asset_name = details.get("asset_name")
            filename = details.get("filename")
            name = f"{asset_name} / {filename}" if asset_name and filename else asset_name or details.get("name")
        elif detail_action in {"download_import_template", "export_assets", "import_assets"} or log.action in {"export", "import"}:
            name = _asset_operation_target_name(log.action, details) or details.get("name") or details.get("asset_name")
        else:
            name = details.get("name") or details.get("asset_name")
    elif log.resource_type == "user":
        name = details.get("username") or details.get("name")
    elif log.resource_type == "setting":
        setting_name = details.get("name")
        if setting_name == "batch_update":
            keys = details.get("keys") if isinstance(details, dict) else None
            if isinstance(keys, list) and len(keys) > 1 and all(key in BRANDING_SETTING_KEYS for key in keys):
                return "品牌设置"
            if isinstance(keys, list) and len(keys) > 1 and all(key in SECURITY_SETTING_KEYS for key in keys):
                return "安全设置"
            if isinstance(keys, list) and len(keys) == 1:
                key = keys[0]
                return SETTING_FIELD_LABELS.get(key) or FIELD_LABELS.get(key, key)
            return "系统设置"
        name = SETTING_FIELD_LABELS.get(setting_name) or FIELD_LABELS.get(setting_name, setting_name)
    else:
        name = details.get("name") or details.get("username") or details.get("group_name")

    if name:
        return str(name)
    if log.resource_id not in (None, 0):
        return str(log.resource_id)
    return None


ACTION_LABELS = {
    "create": "创建",
    "update": "更新",
    "delete": "删除",
    "authorize": "授权",
    "download": "下载",
    "decrypt": "解密",
    "import": "导入",
    "export": "导出",
    "test": "测试",
    "add_group_members": "添加组成员",
    "remove_group_member": "移除组成员",
}

RESOURCE_TYPE_LABELS = {
    "asset": "资产",
    "authorization": "授权",
    "auth": "认证",
    "credential": "凭据",
    "group": "用户组",
    "log_cleanup": "日志清理",
    "organization": "组织节点",
    "setting": "系统设置",
    "user": "用户",
}

SETTING_FIELD_LABELS = {
    "beian_number": "备案号",
    "beian_url": "备案链接",
    "copyright_text": "版权信息",
    "login_background_image": "登录页背景图",
    "login_log_retention": "登录日志保留天数",
    "login_subtitle": "登录页副标题",
    "logo_image": "Logo 图片",
    "decrypt_rate_limit": "凭证解密频率限制",
    "lockout_duration": "锁定时长",
    "max_login_attempts": "最大登录尝试次数",
    "operation_log_retention": "操作日志保留天数",
    "otp_issuer_name": "OTP 验证器名称",
    "password_log_retention": "改密日志保留天数",
    "password_min_length": "密码最小长度",
    "password_history_count": "密码历史检查次数",
    "password_require_digit": "密码至少包含数字",
    "password_require_lowercase": "密码至少包含小写字母",
    "password_require_special": "密码至少包含特殊字符",
    "password_require_uppercase": "密码至少包含大写字母",
    "site_title": "站点标题",
}

BRANDING_SETTING_KEYS = {"site_title", "login_subtitle", "logo_image", "login_background_image", "copyright_text", "beian_number", "beian_url"}
SECURITY_SETTING_KEYS = {"login_log_retention", "operation_log_retention", "password_log_retention", "password_min_length", "password_require_uppercase", "password_require_lowercase", "password_require_digit", "password_require_special", "password_history_count", "max_login_attempts", "lockout_duration", "session_timeout", "decrypt_rate_limit", "otp_issuer_name"}

DETAIL_ACTION_LABELS = {
    "bulk_delete": "批量删除资产",
    "bulk_update": "批量更新资产",
    "delete_config": "删除配置文件",
    "delete_credential": "删除凭据",
    "delete_user_authorizations": "删除用户授权",
    "decrypt_credential": "解密凭据",
    "decrypt_oob_password": "解密OOB密码",
    "disable_mfa": "禁用MFA",
    "download_config": "下载配置文件",
    "download_import_template": "下载导入模板",
    "export_assets": "导出资产",
    "force_logout": "强制离线",
    "import_assets": "导入资产",
    "logout": "用户登出",
    "manual_log_cleanup": "手动清理日志",
    "mfa_bind": "绑定MFA",
    "mfa_disable": "禁用MFA",
    "mfa_reset": "重置MFA",
    "rollback_config": "回滚配置文件",
    "save_config": "保存配置文件",
    "create_organization": "创建组织节点",
    "rename_organization": "重命名组织节点",
    "delete_organization": "删除组织节点",
    "create_credential": "创建凭据",
    "update_credential": "更新凭据",
    "upload_config": "上传配置文件",
    "send_test_email": "发送测试邮件",
}

PERMISSION_LABELS = {
    "view": "查看资产",
    "manage": "管理资产",
    "authorize": "资产授权",
    "view_users": "查看用户",
    "user_mgmt": "用户管理",
    "sys_config": "系统设置",
    "audit_log": "日志审计",
    "view_pwd": "查看密码",
    "export": "导出资产",
    "export_pwd": "导出密码",
}


FIELD_LABELS = {
    "applicant": "申请人",
    "asset_code": "资产编码",
    "avatar_url": "头像",
    "category": "资产类型",
    "description": "描述",
    "credential_type": "凭据类型",
    "device_type": "设备类型",
    "email": "邮箱",
    "full_name": "姓名",
    "group_ids": "用户组",
    "initial_member_ids": "初始成员",
    "initial_member_names": "初始成员",
    "host_ids": "宿主机",
    "internal_address": "内网地址",
    "is_active": "用户状态",
    "is_superuser": "超级管理员",
    "mfa_bound": "MFA 绑定状态",
    "mfa_enabled": "MFA 状态",
    "metadata": "元数据",
    "model": "型号",
    "name": "名称",
    "namespace": "命名空间",
    "notes": "备注",
    "oob_address": "OOB 地址",
    "oob_password": "OOB 密码",
    "oob_username": "OOB 用户名",
    "owner_id": "负责人",
    "owner_name": "负责人",
    "password": "密码",
    "permissions": "权限",
    "requested_user_ids": "请求添加成员",
    "added_user_ids": "实际新增成员",
    "skipped_user_ids": "跳过成员",
    "phone": "手机号",
    "platform": "平台",
    "serial_number": "序列号",
    "session_timeout": "会话超时时间",
    "smtp_from_email": "发件人邮箱",
    "smtp_from_name": "发件人名称",
    "smtp_encryption": "SMTP 加密方式",
    "smtp_host": "SMTP 服务器",
    "smtp_password": "SMTP 密码",
    "smtp_port": "SMTP 端口",
    "smtp_username": "SMTP 用户名",
    "status": "状态",
    "storage_locations": "存储位置",
    "target_ids": "授权目标",
    "target_names": "授权目标",
    "before_target_names": "原授权目标",
    "after_target_names": "新授权目标",
    "valid_from": "生效时间",
    "valid_until": "失效时间",
}

BOOLEAN_FIELD_LABELS = {
    "is_active": {True: "启用", False: "禁用"},
    "is_superuser": {True: "是", False: "否"},
    "mfa_bound": {True: "已绑定", False: "未绑定"},
    "mfa_enabled": {True: "启用", False: "禁用"},
}


def _format_detail_value(field: str, value) -> str:
    if value is None:
        return "空"
    if field in BOOLEAN_FIELD_LABELS and isinstance(value, bool):
        return BOOLEAN_FIELD_LABELS[field][value]
    if isinstance(value, bool):
        return "是" if value else "否"
    if isinstance(value, list):
        return "、".join(_format_detail_value(field, item) for item in value) if value else "空"
    if isinstance(value, dict):
        return "、".join(f"{key}: {_format_detail_value(str(key), item)}" for key, item in value.items()) if value else "空"
    if field in {"permissions", "before_permissions", "after_permissions"} and isinstance(value, str):
        return PERMISSION_LABELS.get(value, value)
    return str(value)


def _build_change_items(details: dict) -> list[dict[str, str]]:
    changes = details.get("changes") if isinstance(details, dict) else None
    if not isinstance(changes, dict):
        return []

    items = []
    for field, value in changes.items():
        if isinstance(value, (list, tuple)) and len(value) == 2:
            before, after = value
        else:
            before, after = None, value
        label = SETTING_FIELD_LABELS.get(field, FIELD_LABELS.get(field, field))
        before_text = _format_detail_value(field, before)
        after_text = _format_detail_value(field, after)
        items.append({
            "field": field,
            "label": label,
            "before": before_text,
            "after": after_text,
            "summary": f"{label}: {before_text} -> {after_text}",
        })
    return items


def _change_after_bool(details: dict, field: str) -> bool | None:
    changes = details.get("changes") if isinstance(details, dict) else None
    if not isinstance(changes, dict) or field not in changes:
        return None
    value = changes[field]
    if isinstance(value, (list, tuple)) and len(value) == 2 and isinstance(value[1], bool):
        return value[1]
    if isinstance(value, bool):
        return value
    return None


def _promoted_user_action_summary(log: OperationLog, target: str | None, details: dict) -> str | None:
    if log.resource_type != "user" or not isinstance(details, dict):
        return None
    active_after = _change_after_bool(details, "is_active")
    if active_after is not None:
        return "启用用户" if active_after else "禁用用户"

    mfa_after = _change_after_bool(details, "mfa_enabled")
    if mfa_after is not None:
        return "启用MFA" if mfa_after else "禁用MFA"

    superuser_after = _change_after_bool(details, "is_superuser")
    if superuser_after is not None:
        return "授予超级管理员权限" if superuser_after else "移除超级管理员权限"

    return None


def _should_show_change_items(log: OperationLog, details: dict, detail_action: str | None) -> bool:
    if detail_action in {"force_logout", "logout", "mfa_bind", "mfa_disable", "mfa_reset", "disable_mfa"}:
        return False
    if log.resource_type == "user" and isinstance(details.get("changes"), dict):
        promoted_fields = {"is_active", "mfa_enabled", "is_superuser"}
        if promoted_fields.intersection(details["changes"].keys()):
            return False
    return True


def _build_operation_summary(log: OperationLog, resource_name: str | None, action_label: str, resource_type_label: str, detail_action_label: str | None, change_items: list[dict[str, str]]) -> str:
    details = log.details or {}
    if not isinstance(details, dict):
        details = {}
    detail_action = details.get("action")
    target = resource_name or (str(log.resource_id) if log.resource_id is not None else None)

    if detail_action == "logout":
        return "用户登出"
    if detail_action == "force_logout":
        return "强制离线"
    if detail_action in {"mfa_bind", "mfa_disable", "mfa_reset", "disable_mfa"}:
        return detail_action_label or DETAIL_ACTION_LABELS.get(detail_action, detail_action)
    if detail_action in {"download_config", "upload_config", "save_config", "rollback_config", "delete_config"}:
        label = detail_action_label or DETAIL_ACTION_LABELS.get(detail_action, detail_action)
        filename = details.get("filename")
        return f"{label} {filename}" if filename else label
    if log.resource_type == "asset" and log.action == "export":
        target_name = _asset_operation_target_name(log.action, details) or target or "资产"
        count = details.get("count")
        return f"导出{target_name}: {count}条" if count is not None else f"导出{target_name}"
    if log.resource_type == "asset" and log.action == "import":
        target_name = _asset_operation_target_name(log.action, details) or target or "资产"
        mode = details.get("mode")
        mode_label = "更新" if mode == "update" else "创建" if mode == "create" else None
        count = details.get("success_count")
        prefix = f"导入{mode_label}{target_name}" if mode_label else f"导入{target_name}"
        return f"{prefix}: 成功{count}条" if count is not None else prefix
    if detail_action == "download_import_template":
        target_name = _asset_operation_target_name(log.action, details) or target or "资产导入模板"
        mode = details.get("mode")
        mode_label = "更新" if mode == "update" else "创建" if mode == "create" else None
        return f"下载{target_name}{mode_label or ''}导入模板"
    if detail_action == "delete_user_authorizations":
        count = details.get("count")
        return f"删除用户授权 {target}: {count}条" if count is not None and target else f"删除用户授权: {count}条" if count is not None else "删除用户授权"
    if log.resource_type == "authorization" and log.action == "update":
        entity_name = details.get("entity_name") or target
        before_target_names = details.get("before_target_names")
        after_target_names = details.get("after_target_names")
        if before_target_names is not None and after_target_names is not None and before_target_names != after_target_names:
            return f"更新授权 {entity_name}: 授权目标从{before_target_names or '空'}修改为{after_target_names or '空'}"
        active_after = _change_after_bool(details, "is_active")
        if active_after is not None:
            return f"{'启用' if active_after else '禁用'}授权 {target}" if target else ("启用授权" if active_after else "禁用授权")
    if log.resource_type == "group" and log.action == "create":
        count = details.get("initial_member_count")
        if count:
            return f"创建用户组 {target}: 初始成员{count}名" if target else f"创建用户组: 初始成员{count}名"
    if detail_action in {"create_organization", "rename_organization", "delete_organization"}:
        label = detail_action_label or DETAIL_ACTION_LABELS.get(detail_action, detail_action)
        base = f"{label} {target}" if target else label
        if detail_action == "rename_organization" and change_items:
            return f"{base}；" + "；".join(f"将{item['label']}从{item['before']}修改为{item['after']}" for item in change_items)
        return base
    if detail_action in {"create_credential", "update_credential", "delete_credential", "decrypt_credential", "decrypt_oob_password"}:
        label = detail_action_label or DETAIL_ACTION_LABELS.get(detail_action, detail_action)
        asset_name = details.get("asset_name")
        credential_name = details.get("credential_username") or details.get("username")
        if asset_name and credential_name:
            base = f"{label} {asset_name} / {credential_name}"
        elif asset_name:
            base = f"{label} {asset_name}"
        else:
            base = f"{label} {target}" if target else label
        if detail_action == "update_credential" and change_items:
            return f"{base}；" + "；".join(f"将{item['label']}从{item['before']}修改为{item['after']}" for item in change_items)
        return base

    promoted_summary = _promoted_user_action_summary(log, target, details)
    if promoted_summary:
        return promoted_summary

    if log.resource_type == "setting" and isinstance(details, dict) and details.get("name") == "batch_update":
        keys = details.get("keys") if isinstance(details.get("keys"), list) else []
        if keys and len(keys) > 1 and all(key in BRANDING_SETTING_KEYS for key in keys):
            return "更新品牌设置"
        if keys and len(keys) > 1 and all(key in SECURITY_SETTING_KEYS for key in keys):
            return "更新安全设置"

    if detail_action_label:
        base = f"{detail_action_label} {target}" if target else detail_action_label
    elif log.action == "add_group_members":
        added = details.get("added") if isinstance(details, dict) else None
        added_names = details.get("added_user_names") if isinstance(details, dict) else None
        if isinstance(added_names, list) and added_names:
            shown = "、".join(str(name) for name in added_names[:3])
            suffix = f" 等{len(added_names)}人" if len(added_names) > 3 else ""
            base = f"添加组成员: {shown}{suffix}"
        else:
            base = f"添加组成员: {added} 名" if added is not None else "添加组成员"
    elif log.action == "remove_group_member":
        username = details.get("username") if isinstance(details, dict) else None
        base = f"移除组成员 {username}" if username else "移除组成员"
    else:
        target_text = f" {target}" if target else ""
        base = f"{action_label}{resource_type_label}{target_text}"

    if change_items:
        return "；".join(f"将{item['label']}从{item['before']}修改为{item['after']}" for item in change_items)

    if isinstance(details, dict):
        if details.get("count") is not None:
            base = f"{base}: {details['count']}条"
        elif details.get("keys"):
            base = f"{base}: {', '.join(str(key) for key in details['keys'])}"
        elif details.get("deleted_counts"):
            counts = details["deleted_counts"]
            if isinstance(counts, dict):
                base = f"{base}: " + "，".join(f"{key} {value} 条" for key, value in counts.items())
    return base


def _format_operation_log(log: OperationLog, username: str) -> dict:
    resource_name = _get_resource_name(log)
    details = log.details or {}
    detail_action = details.get("action") if isinstance(details, dict) else None
    action_label = ACTION_LABELS.get(log.action, log.action)
    resource_type_label = RESOURCE_TYPE_LABELS.get(log.resource_type, log.resource_type or "资源")
    detail_action_label = DETAIL_ACTION_LABELS.get(detail_action) if detail_action else None
    all_change_items = _build_change_items(details if isinstance(details, dict) else {})
    change_items = all_change_items if _should_show_change_items(log, details if isinstance(details, dict) else {}, detail_action) else []

    return {
        "id": log.id,
        "user_id": log.user_id,
        "username": username,
        "action": log.action,
        "action_label": action_label,
        "resource_type": log.resource_type,
        "resource_type_label": resource_type_label,
        "resource_id": log.resource_id,
        "resource_name": resource_name,
        "details": log.details,
        "detail_action": detail_action,
        "detail_action_label": detail_action_label,
        "operation_summary": _build_operation_summary(log, resource_name, action_label, resource_type_label, detail_action_label, change_items),
        "change_items": change_items,
        "ip_address": log.ip_address,
        "status": log.status,
        "created_at": format_datetime_utc(log.created_at),
    }


router = APIRouter(prefix="/logs", tags=["日志审计"])


# ============== Login Logs ==============
@router.get("/login")
async def list_login_logs(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("audit_log")),
):
    """List login logs with pagination and filters"""
    query = select(LoginLog)

    # Apply filters
    if search:
        query = query.where(
            or_(
                LoginLog.username.ilike(f"%{search}%"),
                LoginLog.ip_address.ilike(f"%{search}%"),
            )
        )

    if status:
        query = query.where(LoginLog.status == status)

    if date_from:
        try:
            from_date = datetime.fromisoformat(date_from)
            query = query.where(LoginLog.created_at >= from_date)
        except ValueError:
            pass

    if date_to:
        try:
            to_date = datetime.fromisoformat(date_to) + timedelta(days=1)
            query = query.where(LoginLog.created_at < to_date)
        except ValueError:
            pass

    meta = await get_pagination_meta(db, query, page, limit)

    # Calculate stats with single query using case aggregation
    # Use UTC datetime without timezone for compatibility with database
    today = datetime.utcnow().date()
    today_start = datetime.combine(today, datetime.min.time())

    stats_query = select(
        func.count().filter(LoginLog.created_at >= today_start).label("today_count"),
        func.count().filter(LoginLog.status == "success").label("success_count"),
        func.count().filter(LoginLog.status == "failed").label("failed_count"),
    ).select_from(LoginLog)

    stats_result = await db.execute(stats_query)
    stats_row = stats_result.one()
    today_count = stats_row.today_count or 0
    success_count = stats_row.success_count or 0
    failed_count = stats_row.failed_count or 0

    total_logins = success_count + failed_count
    success_rate = round((success_count / total_logins * 100), 1) if total_logins > 0 else 0

    # Apply pagination
    query = query.offset((page - 1) * limit).limit(limit)
    query = query.order_by(LoginLog.created_at.desc())

    result = await db.execute(query)
    logs = result.scalars().all()

    return {
        "code": 0,
        "message": "success",
        "data": [
            {
                "id": log.id,
                "user_id": log.user_id,
                "username": log.username,
                "ip_address": log.ip_address,
                "user_agent": log.user_agent,
                "status": log.status,
                "failure_reason": log.failure_reason,
                "created_at": format_datetime_utc(log.created_at),
            }
            for log in logs
        ],
        "meta": meta,
        "stats": {
            "today_total": today_count,
            "success_rate": success_rate,
            "failed_count": failed_count,
        }
    }


# ============== Operation Logs ==============
@router.get("/operation")
async def list_operation_logs(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    user_id: Optional[int] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("audit_log")),
):
    """List operation logs with pagination and filters"""
    query = select(OperationLog).outerjoin(
        User, User.id == OperationLog.user_id
    )

    # Apply filters
    if search:
        query = query.where(
            or_(
                OperationLog.action.ilike(f"%{search}%"),
                OperationLog.resource_type.ilike(f"%{search}%"),
                cast(OperationLog.resource_id, String).ilike(f"%{search}%"),
                User.username.ilike(f"%{search}%"),
                cast(OperationLog.details["username"], String).ilike(f"%{search}%"),
                cast(OperationLog.details["name"], String).ilike(f"%{search}%"),
                cast(OperationLog.details["group_name"], String).ilike(f"%{search}%"),
            )
        )

    if action:
        query = query.where(OperationLog.action == action)

    if user_id:
        query = query.where(OperationLog.user_id == user_id)

    if date_from:
        try:
            from_date = datetime.fromisoformat(date_from)
            query = query.where(OperationLog.created_at >= from_date)
        except ValueError:
            pass

    if date_to:
        try:
            to_date = datetime.fromisoformat(date_to) + timedelta(days=1)
            query = query.where(OperationLog.created_at < to_date)
        except ValueError:
            pass

    meta = await get_pagination_meta(db, query, page, limit)

    # Apply pagination
    query = query.offset((page - 1) * limit).limit(limit)
    query = query.order_by(OperationLog.created_at.desc())

    result = await db.execute(query)
    logs = result.scalars().all()

    # Get usernames
    user_ids = list(set(log.user_id for log in logs if log.user_id))
    users_map = {}
    if user_ids:
        users_result = await db.execute(
            select(User).where(User.id.in_(user_ids))
        )
        users = users_result.scalars().all()
        users_map = {u.id: u.username for u in users}

    return {
        "code": 0,
        "message": "success",
        "data": [
            _format_operation_log(log, users_map.get(log.user_id, "Unknown"))
            for log in logs
        ],
        "meta": meta,
    }


# ============== Password Change Logs ==============
@router.get("/password")
async def list_password_logs(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    user_id: Optional[int] = Query(None),
    change_type: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("audit_log")),
):
    """List password change logs with pagination and filters"""
    # Aliases for multiple User joins
    UserAlias = alias(User)
    ChangerAlias = alias(User)

    query = select(PasswordChangeLog)

    # Apply filters
    if search:
        query = (
            query
            .outerjoin(UserAlias, UserAlias.c.id == PasswordChangeLog.user_id)
            .outerjoin(Credential, Credential.id == PasswordChangeLog.credential_id)
            .outerjoin(Asset, Asset.id == Credential.asset_id)
            .outerjoin(ChangerAlias, ChangerAlias.c.id == PasswordChangeLog.changed_by)
            .where(
                or_(
                    UserAlias.c.username.ilike(f"%{search}%"),
                    Credential.username.ilike(f"%{search}%"),
                    Asset.name.ilike(f"%{search}%"),
                    ChangerAlias.c.username.ilike(f"%{search}%"),
                )
            )
        )

    if user_id:
        query = query.where(PasswordChangeLog.user_id == user_id)

    if change_type:
        query = query.where(PasswordChangeLog.change_type == change_type)

    if date_from:
        try:
            from_date = datetime.fromisoformat(date_from)
            query = query.where(PasswordChangeLog.created_at >= from_date)
        except ValueError:
            pass

    if date_to:
        try:
            to_date = datetime.fromisoformat(date_to) + timedelta(days=1)
            query = query.where(PasswordChangeLog.created_at < to_date)
        except ValueError:
            pass

    meta = await get_pagination_meta(db, query, page, limit)

    # Apply pagination
    query = query.offset((page - 1) * limit).limit(limit)
    query = query.order_by(PasswordChangeLog.created_at.desc())

    result = await db.execute(query)
    logs = result.scalars().all()

    # Get usernames
    user_ids = list(set(log.user_id for log in logs if log.user_id))
    user_ids.extend(list(set(log.changed_by for log in logs if log.changed_by)))
    user_ids = list(set(user_ids))

    users_map = {}
    if user_ids:
        users_result = await db.execute(
            select(User).where(User.id.in_(user_ids))
        )
        users = users_result.scalars().all()
        users_map = {u.id: u.username for u in users}

    # Resolve credential_id → asset name + credential username
    credential_ids = list(set(log.credential_id for log in logs if log.credential_id))
    asset_names_map = {}
    cred_usernames_map = {}
    if credential_ids:
        creds_result = await db.execute(
            select(Credential.id, Credential.asset_id, Credential.username).where(Credential.id.in_(credential_ids))
        )
        cred_to_asset = {}
        for row in creds_result.all():
            cred_id, asset_id, cred_username = row
            cred_to_asset[cred_id] = asset_id
            cred_usernames_map[cred_id] = cred_username
        cred_asset_ids = list(cred_to_asset.values())

        if cred_asset_ids:
            assets_result = await db.execute(
                select(Asset.id, Asset.name).where(Asset.id.in_(cred_asset_ids))
            )
            assets_map = {row[0]: row[1] for row in assets_result.all()}
            for cred_id, asset_id in cred_to_asset.items():
                asset_names_map[cred_id] = assets_map.get(asset_id, asset_id)

    return {
        "code": 0,
        "message": "success",
        "data": [
            {
                "id": log.id,
                "user_id": log.user_id,
                "username": users_map.get(log.user_id, "Unknown") if log.user_id else cred_usernames_map.get(log.credential_id) if log.credential_id else None,
                "credential_id": log.credential_id,
                "asset_name": asset_names_map.get(log.credential_id) if log.credential_id else None,
                "change_type": log.change_type,
                "changed_by": log.changed_by,
                "changed_by_name": users_map.get(log.changed_by, "Unknown"),
                "ip_address": log.ip_address,
                "status": log.status,
                "created_at": format_datetime_utc(log.created_at),
            }
            for log in logs
        ],
        "meta": meta,
    }


# ============== Manual Cleanup ==============
@router.post("/cleanup")
async def trigger_cleanup(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("sys_config")),
    request: Request = None,
):
    """Manually trigger log cleanup based on retention settings.

    Requires sys_config permission.
    """
    ip = request.client.host if request and request.client else None
    deleted = await cleanup_expired_logs(db)

    # Audit log
    await log_operation(
        db, current_user.id, "update", "log_cleanup", 0,
        details={
            "name": "manual_log_cleanup",
            "deleted_counts": deleted,
        },
        ip_address=ip,
    )

    return {
        "code": 0,
        "message": "success",
        "data": deleted,
    }