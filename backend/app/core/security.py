"""
Security Module
Password hashing, JWT token management, and TOTP MFA
"""
from datetime import datetime, timedelta
from io import BytesIO
from typing import Any, Optional
from jose import jwt, JWTError
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


def create_access_token(
    subject: str | int,
    expires_delta: Optional[timedelta] = None,
    additional_data: Optional[dict[str, Any]] = None,
) -> str:
    """Create a JWT access token"""
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(hours=settings.JWT_ACCESS_TOKEN_EXPIRE_HOURS)

    to_encode = {
        "sub": str(subject),
        "exp": expire,
        "iat": datetime.utcnow(),
    }
    if additional_data:
        to_encode.update(additional_data)

    encoded_jwt = jwt.encode(
        to_encode,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM
    )
    return encoded_jwt


def decode_access_token(token: str) -> Optional[dict[str, Any]]:
    """Decode and validate a JWT access token"""
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
        return payload
    except JWTError:
        return None


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