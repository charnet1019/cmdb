"""Shared SMTP configuration loading and message sending."""
import logging
import smtplib
from email.message import EmailMessage
from email.utils import formataddr

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.encryption import decrypt_value
from app.models import Setting

logger = logging.getLogger(__name__)

SMTP_SETTING_KEYS = (
    "smtp_host",
    "smtp_port",
    "smtp_encryption",
    "smtp_username",
    "smtp_password",
    "smtp_from_email",
    "smtp_from_name",
)

SMTP_ENCRYPTION_MODES = {"ssl", "starttls", "none"}


def _setting_plain_value(setting: Setting | None, default=None):
    if not setting or not isinstance(setting.value, dict):
        return default
    return setting.value.get("value", default)


def _decrypt_smtp_password(value: str | None) -> str:
    if not value:
        return ""
    if isinstance(value, str) and value.startswith("gAAAA"):
        return decrypt_value(value)
    return str(value)


async def load_smtp_config(db: AsyncSession) -> dict:
    result = await db.execute(select(Setting).where(Setting.key.in_(SMTP_SETTING_KEYS)))
    setting_map = {setting.key: _setting_plain_value(setting, "") for setting in result.scalars().all()}
    encryption = str(setting_map.get("smtp_encryption") or "ssl").strip().lower()
    if encryption not in SMTP_ENCRYPTION_MODES:
        encryption = "ssl"
    return {
        "host": str(setting_map.get("smtp_host") or "").strip(),
        "port": int(setting_map.get("smtp_port") or 465),
        "encryption": encryption,
        "username": str(setting_map.get("smtp_username") or "").strip(),
        "password": _decrypt_smtp_password(setting_map.get("smtp_password")),
        "from_email": str(setting_map.get("smtp_from_email") or "").strip(),
        "from_name": str(setting_map.get("smtp_from_name") or "CMDB").strip() or "CMDB",
    }


def send_smtp_message(config: dict, msg: EmailMessage) -> None:
    """Connect to the SMTP server using the configured encryption mode and send msg.

    encryption modes:
      - ssl: implicit TLS from the start of the connection (typically port 465)
      - starttls: plaintext connection upgraded to TLS via STARTTLS (typically port 587)
      - none: plaintext, no encryption (not recommended)
    """
    server_cls = smtplib.SMTP_SSL if config["encryption"] == "ssl" else smtplib.SMTP

    with server_cls(config["host"], config["port"], timeout=10) as server:
        if config["encryption"] == "starttls":
            server.starttls()
        if config["username"]:
            server.login(config["username"], config["password"])
        server.send_message(msg)


def build_password_email(config: dict, recipient_email: str, username: str, temp_password: str, action: str) -> EmailMessage:
    action_label = "创建" if action == "create" else "重置"
    msg = EmailMessage()
    msg["Subject"] = f"CMDB 账号密码已{action_label}"
    msg["From"] = formataddr((config["from_name"], config["from_email"]))
    msg["To"] = recipient_email
    msg.set_content(
        f"您好，\n\n"
        f"您的 CMDB 账号密码已{action_label}。\n\n"
        f"用户名：{username}\n"
        f"临时密码：{temp_password}\n\n"
        f"请登录后立即修改密码。\n"
    )
    return msg


def build_test_email(config: dict, recipient_email: str) -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = "CMDB 邮件服务器测试"
    msg["From"] = formataddr((config["from_name"], config["from_email"]))
    msg["To"] = recipient_email
    msg.set_content(
        "您好，\n\n"
        "这是一封来自 CMDB 系统设置页面的测试邮件。\n"
        "如果您收到此邮件，说明当前 SMTP 配置可以正常发送邮件。\n"
    )
    return msg


def raise_smtp_config_incomplete() -> None:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="邮件服务器未配置完整，请先在系统设置中配置 SMTP 服务器和发件人邮箱")
