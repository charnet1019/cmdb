"""
Initialize CMDB with default admin user and settings
"""
import logging
import os
import secrets
import string
from sqlalchemy import select

from app.database import async_session_maker
from app.models import User, Group, Setting
from app.core.security import get_password_hash
from app.config import settings

logger = logging.getLogger(__name__)

# Default admin credentials
DEFAULT_ADMIN_USERNAME = "admin"
INITIAL_ADMIN_PASSWORD_ENV = "CMDB_INITIAL_ADMIN_PASSWORD"

def _generate_initial_admin_password() -> str:
    alphabet = string.ascii_letters + string.digits + "!@#%&*"
    return "".join(secrets.choice(alphabet) for _ in range(20))


def _ensure_session_timeout_setting(setting: Setting | None) -> Setting:
    if setting is None:
        return Setting(key="session_timeout", value={"value": 30}, description="会话超时时间(分钟)")
    setting.description = "会话超时时间(分钟)"
    return setting


async def seed_default_data() -> None:
    """Seed database with default admin user and settings (idempotent)."""
    # Validate encryption key is set
    if not settings.ENCRYPTION_KEY:
        logger.error(
            "ENCRYPTION_KEY environment variable not set! "
            "Generate one: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
        return

    async with async_session_maker() as session:
        setting_result = await session.execute(select(Setting).where(Setting.key == "session_timeout"))
        session_timeout_setting = _ensure_session_timeout_setting(setting_result.scalar_one_or_none())
        if session_timeout_setting.id is None:
            session.add(session_timeout_setting)

        # Check if admin user exists
        result = await session.execute(select(User).where(User.username == DEFAULT_ADMIN_USERNAME))
        existing_admin = result.scalar_one_or_none()

        if existing_admin:
            # If admin exists but never logged in, ensure must_change_password is set
            if existing_admin.last_login_at is None and not existing_admin.must_change_password:
                existing_admin.must_change_password = True
                logger.warning(
                    "Admin account exists but never logged in. "
                    "must_change_password flag has been set for username: %s",
                    DEFAULT_ADMIN_USERNAME,
                )
            await session.commit()
            return

        # Create admin group
        admin_group = Group(
            name="管理员",
            description="系统管理员组，拥有所有权限",
        )
        session.add(admin_group)
        await session.flush()

        initial_admin_password = os.getenv(INITIAL_ADMIN_PASSWORD_ENV) or _generate_initial_admin_password()

        # Create admin user with initial password
        admin_user = User(
            username=DEFAULT_ADMIN_USERNAME,
            email="admin@example.com",
            full_name="系统管理员",
            password_hash=get_password_hash(initial_admin_password),
            is_active=True,
            is_superuser=True,
            mfa_enabled=False,
            must_change_password=True,
        )
        session.add(admin_user)
        await session.flush()

        # Add admin user to admin group
        from app.models import UserGroup
        user_group = UserGroup(user_id=admin_user.id, group_id=admin_group.id)
        session.add(user_group)

        # Create default settings
        db_settings = [
            Setting(key="site_title", value={"value": "CMDB"}, description="站点标题"),
            Setting(key="login_subtitle", value={"value": "企业资产配置管理平台"}, description="登录页副标题"),
            Setting(key="logo_image", value={"value": ""}, description="登录页Logo图片"),
            Setting(key="login_background_image", value={"value": ""}, description="登录页背景图片"),
            Setting(key="password_min_length", value={"value": 8}, description="密码最小长度"),
            Setting(key="password_require_uppercase", value={"value": True}, description="密码要求大写字母"),
            Setting(key="password_require_lowercase", value={"value": True}, description="密码要求小写字母"),
            Setting(key="password_require_digit", value={"value": True}, description="密码要求数字"),
            Setting(key="password_require_special", value={"value": False}, description="密码要求特殊字符"),
            Setting(key="max_login_attempts", value={"value": 5}, description="最大登录尝试次数"),
            Setting(key="lockout_duration", value={"value": 30}, description="账户锁定时间(分钟)"),
            Setting(key="login_log_retention", value={"value": 30}, description="登录日志保留天数"),
            Setting(key="operation_log_retention", value={"value": 30}, description="操作日志保留天数"),
            Setting(key="password_log_retention", value={"value": 30}, description="改密日志保留天数"),
            Setting(key="smtp_host", value={"value": ""}, description="SMTP服务器地址"),
            Setting(key="smtp_port", value={"value": 465}, description="SMTP服务器端口"),
            Setting(key="smtp_use_ssl", value={"value": True}, description="SMTP是否使用SSL"),
            Setting(key="smtp_username", value={"value": ""}, description="SMTP用户名"),
            Setting(key="smtp_password", value={"value": ""}, description="SMTP密码"),
            Setting(key="smtp_from_email", value={"value": ""}, description="发件人邮箱"),
            Setting(key="smtp_from_name", value={"value": "CMDB"}, description="发件人名称"),
        ]
        for setting in db_settings:
            session.add(setting)

        await session.commit()

        if os.getenv(INITIAL_ADMIN_PASSWORD_ENV):
            logger.warning(
                "CMDB initialized. Admin account created for username: %s. "
                "Initial password came from %s. First login requires password change.",
                DEFAULT_ADMIN_USERNAME,
                INITIAL_ADMIN_PASSWORD_ENV,
            )
        else:
            logger.warning(
                "CMDB initialized. Admin account created for username: %s. "
                "Generated initial password: %s. First login requires password change.",
                DEFAULT_ADMIN_USERNAME,
                initial_admin_password,
            )
