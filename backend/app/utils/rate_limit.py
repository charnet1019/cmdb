"""Redis-backed per-second rate limiter for sensitive operations."""
import time
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis_client import get_redis
from app.models import Setting

CREDENTIAL_DECRYPT_RATE_LIMIT_SETTING_KEY = "decrypt_rate_limit"
CREDENTIAL_DECRYPT_RATE_LIMIT_DEFAULT = 3


async def _get_limit_per_second(db: AsyncSession, setting_key: str, default: int) -> int:
    result = await db.execute(select(Setting).where(Setting.key == setting_key))
    setting = result.scalar_one_or_none()
    if not setting or not isinstance(setting.value, dict):
        return default
    try:
        return int(setting.value.get("value", default))
    except (TypeError, ValueError):
        return default


async def check_credential_decrypt_rate_limit(db: AsyncSession, user_id: int) -> None:
    """Raise 429 if user_id exceeds the configured credential-decrypt rate (default 3/秒)."""
    limit = await _get_limit_per_second(
        db, CREDENTIAL_DECRYPT_RATE_LIMIT_SETTING_KEY, CREDENTIAL_DECRYPT_RATE_LIMIT_DEFAULT
    )
    if limit <= 0:
        return
    redis_client = get_redis()
    window = int(time.time())
    key = f"ratelimit:credential_decrypt:{user_id}:{window}"
    count = await redis_client.incr(key)
    if count == 1:
        await redis_client.expire(key, 2)
    if count > limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="解密请求过于频繁，请稍后再试",
        )


PASSWORD_EMAIL_RATE_LIMIT_WINDOW_SECONDS = 600  # 10 minutes
PASSWORD_EMAIL_RATE_LIMIT_MAX_SENDS = 3


async def check_password_email_rate_limit(recipient_user_id: int) -> None:
    """Raise 429 if the recipient's mailbox already received too many password
    emails recently (prevents email-bombing a single user via repeated resets)."""
    redis_client = get_redis()
    key = f"ratelimit:password_email:{recipient_user_id}"
    count = await redis_client.incr(key)
    if count == 1:
        await redis_client.expire(key, PASSWORD_EMAIL_RATE_LIMIT_WINDOW_SECONDS)
    if count > PASSWORD_EMAIL_RATE_LIMIT_MAX_SENDS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="该用户近期收到的密码邮件过多，请稍后再试",
        )


SMTP_TEST_EMAIL_RATE_LIMIT_WINDOW_SECONDS = 60  # 1 minute
SMTP_TEST_EMAIL_RATE_LIMIT_MAX_SENDS = 3


async def check_smtp_test_email_rate_limit(actor_user_id: int) -> None:
    """Raise 429 if the admin has requested too many test emails recently.
    This also limits how often smtp_host can be probed via the test-email endpoint."""
    redis_client = get_redis()
    key = f"ratelimit:smtp_test_email:{actor_user_id}"
    count = await redis_client.incr(key)
    if count == 1:
        await redis_client.expire(key, SMTP_TEST_EMAIL_RATE_LIMIT_WINDOW_SECONDS)
    if count > SMTP_TEST_EMAIL_RATE_LIMIT_MAX_SENDS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="测试邮件发送过于频繁，请稍后再试",
        )
