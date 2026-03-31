"""
Initialize CMDB with default admin user and settings
"""
import asyncio
import secrets
import string
from sqlalchemy import select
from app.database import async_session_maker
from app.models import User, Group, Setting
from app.core.security import get_password_hash
from app.config import settings


def generate_random_password(length: int = 16) -> str:
    """Generate a secure random password"""
    chars = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(secrets.choice(chars) for _ in range(length))


async def init_db():
    """Initialize database with default data"""
    # Validate encryption key is set
    if not settings.ENCRYPTION_KEY:
        print("[ERROR] ENCRYPTION_KEY environment variable not set!")
        print("        Generate encryption key and set environment variable:")
        print("        python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\"")
        return

    async with async_session_maker() as session:
        # Check if admin user exists
        result = await session.execute(select(User).where(User.username == "admin"))
        if result.scalar_one_or_none():
            print("Admin user already exists")
            return

        # Create admin group
        admin_group = Group(
            name="管理员",
            description="系统管理员组，拥有所有权限"
        )
        session.add(admin_group)
        await session.flush()

        # Generate random password for admin
        temp_password = generate_random_password()

        # Create admin user
        admin_user = User(
            username="admin",
            email="admin@example.com",
            full_name="系统管理员",
            password_hash=get_password_hash(temp_password),
            is_active=True,
            is_superuser=True,
            mfa_enabled=False,
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
            Setting(key="session_timeout", value={"value": 24}, description="会话超时时间(小时)"),
            Setting(key="max_login_attempts", value={"value": 5}, description="最大登录尝试次数"),
        ]
        for setting in db_settings:
            session.add(setting)

        await session.commit()
        print("=" * 60)
        print("[OK] Initialization complete!")
        print("=" * 60)
        print("     Admin account: admin")
        print(f"     Temporary password: {temp_password}")
        print("=" * 60)
        print("[WARNING] Please save the password and change it immediately after login!")
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(init_db())