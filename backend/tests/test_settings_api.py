"""Tests for GET/PUT /settings, POST /settings/email/test, and POST /settings/smtp-password/reveal."""
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, Response

from tests.factories import FakeDB, FakeResult, user

from app.api import settings as settings_api
from app.models import Setting


def _setting(key, value, description=None):
    return Setting(id=1, key=key, value={"value": value}, description=description)


def _request():
    return SimpleNamespace(client=SimpleNamespace(host="127.0.0.1"))


@pytest.mark.asyncio
async def test_get_settings_masks_smtp_password_and_returns_raw():
    db = FakeDB(
        FakeResult(scalars=[
            _setting("site_title", "CMDB"),
            _setting("smtp_password", "gAAAA-encrypted"),
        ])
    )

    response = await settings_api.get_settings(db=db, current_user=user(is_superuser=True))

    assert response["data"]["site_title"] == "CMDB"
    assert response["data"]["smtp_password"] == settings_api.SMTP_PASSWORD_MASK
    assert len(response["raw"]) == 2


@pytest.mark.asyncio
async def test_get_public_settings_only_returns_branding_keys():
    db = FakeDB(
        FakeResult(scalars=[
            _setting("site_title", "CMDB"),
            _setting("max_login_attempts", 5),
        ])
    )

    response = await settings_api.get_public_settings(db=db)

    assert response["data"] == {"site_title": "CMDB"}


@pytest.mark.asyncio
async def test_update_settings_rejects_unknown_key():
    db = FakeDB(FakeResult(scalar_one_or_none=None))

    with pytest.raises(HTTPException) as exc:
        await settings_api.update_settings(
            settings_data={"not_a_real_setting": "x"},
            response=Response(),
            db=db,
            current_user=user(is_superuser=True),
            request=_request(),
        )

    assert exc.value.status_code == 400
    assert "不允许的设置项" in exc.value.detail


@pytest.mark.asyncio
async def test_update_settings_rejects_out_of_range_int():
    db = FakeDB(FakeResult(scalar_one_or_none=None))

    with pytest.raises(HTTPException) as exc:
        await settings_api.update_settings(
            settings_data={"max_login_attempts": 999},
            response=Response(),
            db=db,
            current_user=user(is_superuser=True),
            request=_request(),
        )

    assert exc.value.status_code == 400
    assert "范围内" in exc.value.detail


@pytest.mark.asyncio
async def test_update_settings_creates_new_setting_and_logs_change(monkeypatch):
    audit_calls = []

    async def fake_log(*args, **kwargs):
        audit_calls.append((args, kwargs))

    monkeypatch.setattr(settings_api, "log_operation", fake_log)

    db = FakeDB(FakeResult(scalar_one_or_none=None))  # no existing "site_title" row

    response = await settings_api.update_settings(
        settings_data={"site_title": "New CMDB"},
        response=Response(),
        db=db,
        current_user=user(is_superuser=True),
        request=_request(),
    )

    assert response["data"]["updated"] == ["site_title"]
    created = next(obj for obj in db.added if isinstance(obj, Setting))
    assert created.key == "site_title"
    assert created.value == {"value": "New CMDB"}
    assert db.commits == 1
    changes = audit_calls[0][1]["details"]["changes"]
    assert changes == {"site_title": [None, "New CMDB"]}


@pytest.mark.asyncio
async def test_update_settings_updates_existing_setting_value(monkeypatch):
    async def fake_log(*args, **kwargs):
        return None

    monkeypatch.setattr(settings_api, "log_operation", fake_log)

    existing = _setting("site_title", "Old CMDB")
    db = FakeDB(FakeResult(scalar_one_or_none=existing))

    await settings_api.update_settings(
        settings_data={"site_title": "New CMDB"},
        response=Response(),
        db=db,
        current_user=user(is_superuser=True),
        request=_request(),
    )

    assert existing.value == {"value": "New CMDB"}
    assert db.added == []


@pytest.mark.asyncio
async def test_update_settings_redacts_sensitive_keys_in_audit_log(monkeypatch):
    audit_calls = []

    async def fake_log(*args, **kwargs):
        audit_calls.append((args, kwargs))

    monkeypatch.setattr(settings_api, "log_operation", fake_log)

    db = FakeDB(FakeResult(scalar_one_or_none=None))

    await settings_api.update_settings(
        settings_data={"smtp_password": "super-secret"},
        response=Response(),
        db=db,
        current_user=user(is_superuser=True),
        request=_request(),
    )

    changes = audit_calls[0][1]["details"]["changes"]
    assert changes["smtp_password"] == ["<redacted>", "<redacted>"]


@pytest.mark.asyncio
async def test_send_test_email_rejects_invalid_recipient():
    with pytest.raises(HTTPException) as exc:
        await settings_api.send_test_email(
            data=settings_api.TestEmailRequest(recipient="not-an-email"),
            request=_request(),
            db=FakeDB(),
            current_user=user(is_superuser=True),
        )

    assert exc.value.status_code == 400
    assert "有效的收件人邮箱地址" in exc.value.detail


@pytest.mark.asyncio
async def test_send_test_email_rejects_incomplete_config(monkeypatch):
    async def no_rate_limit(*args, **kwargs):
        return None

    async def empty_config(db):
        return {"host": "", "port": 465, "encryption": "ssl", "username": "", "password": "", "from_email": "", "from_name": "CMDB"}

    monkeypatch.setattr(settings_api, "check_smtp_test_email_rate_limit", no_rate_limit)
    monkeypatch.setattr(settings_api, "load_smtp_config", empty_config)

    with pytest.raises(HTTPException) as exc:
        await settings_api.send_test_email(
            data=settings_api.TestEmailRequest(recipient="ok@example.com"),
            request=_request(),
            db=FakeDB(),
            current_user=user(is_superuser=True),
        )

    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_send_test_email_success_logs_and_returns_recipient(monkeypatch):
    async def no_rate_limit(*args, **kwargs):
        return None

    async def full_config(db):
        return {
            "host": "smtp.example.com", "port": 465, "encryption": "ssl",
            "username": "user", "password": "pass",
            "from_email": "noreply@example.com", "from_name": "CMDB",
        }

    audit_calls = []

    async def fake_log(*args, **kwargs):
        audit_calls.append((args, kwargs))

    monkeypatch.setattr(settings_api, "check_smtp_test_email_rate_limit", no_rate_limit)
    monkeypatch.setattr(settings_api, "load_smtp_config", full_config)
    monkeypatch.setattr(settings_api, "send_smtp_message", lambda config, msg: None)
    monkeypatch.setattr(settings_api, "log_operation", fake_log)

    response = await settings_api.send_test_email(
        data=settings_api.TestEmailRequest(recipient="ok@example.com"),
        request=_request(),
        db=FakeDB(),
        current_user=user(is_superuser=True),
    )

    assert response["data"]["recipient"] == "ok@example.com"
    assert audit_calls[0][1]["details"]["action"] == "send_test_email"


@pytest.mark.asyncio
async def test_reveal_smtp_password_returns_decrypted_value(monkeypatch):
    from app.core.encryption import encrypt_value

    async def no_rate_limit(*args, **kwargs):
        return None

    async def fake_log(*args, **kwargs):
        return None

    monkeypatch.setattr(settings_api, "check_credential_decrypt_rate_limit", no_rate_limit)
    monkeypatch.setattr(settings_api, "log_operation", fake_log)

    encrypted = encrypt_value("mail-secret")
    db = FakeDB(FakeResult(scalar_one_or_none=_setting("smtp_password", encrypted)))

    response = await settings_api.reveal_smtp_password(
        request=_request(),
        db=db,
        current_user=user(is_superuser=True),
    )

    assert response["data"]["password"] == "mail-secret"


@pytest.mark.asyncio
async def test_reveal_smtp_password_returns_empty_when_unset(monkeypatch):
    async def no_rate_limit(*args, **kwargs):
        return None

    monkeypatch.setattr(settings_api, "check_credential_decrypt_rate_limit", no_rate_limit)

    db = FakeDB(FakeResult(scalar_one_or_none=None))

    response = await settings_api.reveal_smtp_password(
        request=_request(),
        db=db,
        current_user=user(is_superuser=True),
    )

    assert response["data"]["password"] == ""


@pytest.mark.asyncio
async def test_send_test_email_reports_502_on_smtp_failure(monkeypatch):
    async def no_rate_limit(*args, **kwargs):
        return None

    async def full_config(db):
        return {
            "host": "smtp.example.com", "port": 465, "encryption": "ssl",
            "username": "user", "password": "pass",
            "from_email": "noreply@example.com", "from_name": "CMDB",
        }

    def failing_send(config, msg):
        raise ConnectionError("smtp down")

    async def fake_log(*args, **kwargs):
        return None

    monkeypatch.setattr(settings_api, "check_smtp_test_email_rate_limit", no_rate_limit)
    monkeypatch.setattr(settings_api, "load_smtp_config", full_config)
    monkeypatch.setattr(settings_api, "send_smtp_message", failing_send)
    monkeypatch.setattr(settings_api, "log_operation", fake_log)

    with pytest.raises(HTTPException) as exc:
        await settings_api.send_test_email(
            data=settings_api.TestEmailRequest(recipient="ok@example.com"),
            request=_request(),
            db=FakeDB(),
            current_user=user(is_superuser=True),
        )

    assert exc.value.status_code == 502
