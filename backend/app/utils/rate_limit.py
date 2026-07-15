"""Redis-backed per-second rate limiter for sensitive operations."""
import time
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis_client import get_redis
from app.core.settings_helper import get_int_setting

CREDENTIAL_DECRYPT_RATE_LIMIT_SETTING_KEY = "decrypt_rate_limit"
CREDENTIAL_DECRYPT_RATE_LIMIT_DEFAULT = 3


async def check_credential_decrypt_rate_limit(db: AsyncSession, user_id: int) -> None:
    """Raise 429 if user_id exceeds the configured credential-decrypt rate (default 3/秒)."""
    limit = await get_int_setting(
        db, CREDENTIAL_DECRYPT_RATE_LIMIT_SETTING_KEY, CREDENTIAL_DECRYPT_RATE_LIMIT_DEFAULT, 0, 100
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


MFA_VERIFY_RATE_LIMIT_WINDOW_SECONDS = 600  # matches login challenge TTL
MFA_VERIFY_RATE_LIMIT_MAX_ATTEMPTS = 5


async def check_mfa_verify_rate_limit(challenge_token: str) -> None:
    """Raise 429 if a given login challenge has already seen too many TOTP
    verification attempts (prevents brute-forcing a 6-digit code)."""
    redis_client = get_redis()
    key = f"ratelimit:mfa_verify:{challenge_token}"
    count = await redis_client.incr(key)
    if count == 1:
        await redis_client.expire(key, MFA_VERIFY_RATE_LIMIT_WINDOW_SECONDS)
    if count > MFA_VERIFY_RATE_LIMIT_MAX_ATTEMPTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="验证码错误次数过多，请重新登录",
        )


SECURITY_NOTIFICATION_EMAIL_RATE_LIMIT_WINDOW_SECONDS = 600  # 10 minutes
SECURITY_NOTIFICATION_EMAIL_RATE_LIMIT_MAX_SENDS = 3


async def check_security_notification_email_rate_limit(recipient_user_id: int) -> None:
    """Raise 429 if the recipient already received too many security
    notification emails recently (MFA reset/disable, etc.)."""
    redis_client = get_redis()
    key = f"ratelimit:security_notification_email:{recipient_user_id}"
    count = await redis_client.incr(key)
    if count == 1:
        await redis_client.expire(key, SECURITY_NOTIFICATION_EMAIL_RATE_LIMIT_WINDOW_SECONDS)
    if count > SECURITY_NOTIFICATION_EMAIL_RATE_LIMIT_MAX_SENDS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="该用户近期收到的安全通知邮件过多，请稍后再试",
        )
