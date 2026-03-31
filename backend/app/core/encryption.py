"""
Encryption Module
Fernet symmetric encryption for sensitive data (credentials)
"""
import base64
import hashlib
from cryptography.fernet import Fernet
from app.config import settings


def _get_fernet_key() -> bytes:
    """
    Get Fernet key from environment

    The key must be a valid Fernet key (32 bytes, url-safe base64-encoded)
    Generate one with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    """
    key = settings.ENCRYPTION_KEY

    if not key:
        raise ValueError(
            "ENCRYPTION_KEY environment variable is not set. "
            "Generate a key with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )

    # If the key is a valid Fernet key, use it directly
    try:
        # Fernet keys are 44 character base64 strings
        if len(key) == 44:
            return key.encode()
        # Otherwise derive a key from the secret
        derived = hashlib.sha256(key.encode()).digest()
        return base64.urlsafe_b64encode(derived)
    except Exception as e:
        raise ValueError(f"Invalid ENCRYPTION_KEY: {e}")


_fernet: Fernet | None = None


def get_fernet() -> Fernet:
    """Get Fernet instance (singleton)"""
    global _fernet
    if _fernet is None:
        key = _get_fernet_key()
        _fernet = Fernet(key)
    return _fernet


def encrypt_value(plain_text: str) -> str:
    """
    Encrypt a plain text value
    Returns encrypted string
    """
    if not plain_text:
        return ""
    fernet = get_fernet()
    encrypted = fernet.encrypt(plain_text.encode())
    return encrypted.decode()


def decrypt_value(encrypted_text: str) -> str:
    """
    Decrypt an encrypted value
    Returns plain text string
    """
    if not encrypted_text:
        return ""
    fernet = get_fernet()
    decrypted = fernet.decrypt(encrypted_text.encode())
    return decrypted.decode()


def generate_encryption_key() -> str:
    """
    Generate a new Fernet-compatible encryption key
    Run this once and store in environment variables
    """
    return Fernet.generate_key().decode()