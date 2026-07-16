"""Tests for _encrypt_oob_password, the shared helper used by both
create_asset and update_asset to encrypt-or-clear the OOB password field."""
from app.api import assets as asset_api
from app.core.encryption import decrypt_value


def test_encrypt_oob_password_encrypts_nonempty_value():
    encrypted = asset_api._encrypt_oob_password("secret123")
    assert encrypted is not None
    assert encrypted != "secret123"
    assert decrypt_value(encrypted) == "secret123"


def test_encrypt_oob_password_returns_none_for_empty_string():
    assert asset_api._encrypt_oob_password("") is None


def test_encrypt_oob_password_returns_none_for_none():
    assert asset_api._encrypt_oob_password(None) is None
