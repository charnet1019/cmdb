"""
Security Module
Password hashing, JWT token management, and TOTP MFA
"""
from io import BytesIO
from typing import Optional
import secrets
import bcrypt
import pyotp
import qrcode
from app.config import settings


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash"""
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))


def get_password_hash(password: str) -> str:
    """Hash a password"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


_dummy_password_hash: Optional[str] = None


def get_dummy_password_hash() -> str:
    """Return a fixed, process-lifetime bcrypt hash with no matching password.

    Used to run a bcrypt comparison for unknown usernames during login, so the
    response time is similar to a real wrong-password attempt and can't be
    used to enumerate valid usernames via timing.
    """
    global _dummy_password_hash
    if _dummy_password_hash is None:
        _dummy_password_hash = get_password_hash(secrets.token_hex(32))
    return _dummy_password_hash


def generate_totp_secret() -> str:
    """Generate a random base32 TOTP secret"""
    return pyotp.random_base32()


def verify_totp(secret: str, code: str) -> bool:
    """Verify a 6-digit TOTP code against the given secret"""
    totp = pyotp.TOTP(secret)
    return totp.verify(code)


def generate_totp_qr(secret: str, username: str, issuer: Optional[str] = None) -> str:
    """Generate QR code data URI for TOTP enrollment"""
    if issuer is None:
        issuer = settings.OTP_ISSUER_NAME
    totp = pyotp.TOTP(secret)
    uri = totp.provisioning_uri(name=username, issuer_name=issuer)
    qr = qrcode.make(uri)
    buffer = BytesIO()
    qr.save(buffer, format="PNG")
    import base64
    b64 = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{b64}"