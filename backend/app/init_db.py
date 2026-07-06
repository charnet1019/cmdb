"""
Initialize CMDB with default admin user and settings
"""
import logging
from sqlalchemy import select

from app.database import async_session_maker
from app.models import User, Group, Setting
from app.core.security import get_password_hash
from app.config import settings

logger = logging.getLogger(__name__)

# Default admin credentials
DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "Admin123"


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
        # Check if admin user exists
        result = await session.execute(select(User).where(User.username == DEFAULT_ADMIN_USERNAME))
        existing_admin = result.scalar_one_or_none()

        if existing_admin:
            # If admin exists but never logged in, ensure must_change_password is set
            if existing_admin.last_login_at is None and not existing_admin.must_change_password:
                existing_admin.must_change_password = True
                await session.commit()
                logger.warning(
                    "Admin account exists but never logged in. "
                    "must_change_password flag has been set. "
                    "username: %s, password: %s",
                    DEFAULT_ADMIN_USERNAME,
                    DEFAULT_ADMIN_PASSWORD,
                )
            return

        # Create admin group
        admin_group = Group(
            name="管理员",
            description="系统管理员组，拥有所有权限",
        )
        session.add(admin_group)
        await session.flush()

        # Create admin user with default password
        admin_user = User(
            username=DEFAULT_ADMIN_USERNAME,
            email="admin@example.com",
            full_name="系统管理员",
            password_hash=get_password_hash(DEFAULT_ADMIN_PASSWORD),
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
            Setting(key="site_logo", value={"value": ""}, description="站点Logo"),
            Setting(key="password_min_length", value={"value": 8}, description="密码最小长度"),
            Setting(key="password_require_uppercase", value={"value": True}, description="密码要求大写字母"),
            Setting(key="password_require_lowercase", value={"value": True}, description="密码要求小写字母"),
            Setting(key="password_require_digit", value={"value": True}, description="密码要求数字"),
            Setting(key="password_require_special", value={"value": False}, description="密码要求特殊字符"),
            Setting(key="session_timeout", value={"value": 1}, description="会话超时时间(小时)"),
            Setting(key="max_login_attempts", value={"value": 5}, description="最大登录尝试次数"),
            Setting(key="lockout_duration", value={"value": 30}, description="账户锁定时间(分钟)"),
            Setting(key="login_log_retention", value={"value": 30}, description="登录日志保留天数"),
            Setting(key="operation_log_retention", value={"value": 30}, description="操作日志保留天数"),
            Setting(key="password_log_retention", value={"value": 30}, description="改密日志保留天数"),
        ]
        for setting in db_settings:
            session.add(setting)

        await session.commit()

        # Log admin credentials to backend logs
        logger.warning(
            "CMDB initialized. Admin account created — "
            "username: %s, password: %s. First login requires password change.",
            DEFAULT_ADMIN_USERNAME,
            DEFAULT_ADMIN_PASSWORD,
        )
