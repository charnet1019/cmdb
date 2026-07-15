"""Tests for POST /auth/change-password and POST /auth/force-change-password."""
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, Response

from tests.factories import FakeDB, FakeRedisSessionStore, FakeResult, user

from app.api import auth as auth_api
from app.core import session as session_core
from app.schemas import ForcePasswordChangeRequest, PasswordChangeRequest


def _request():
    return SimpleNamespace(
        client=SimpleNamespace(host="127.0.0.1"),
        headers={"user-agent": "pytest"},
        url=SimpleNamespace(scheme="http"),
    )


async def _always_valid(*args, **kwargs):
    return True, []


async def _no_reuse_check(*args, **kwargs):
    return None


@pytest.mark.asyncio
async def test_change_password_rejects_wrong_old_password():
    current = user(password_hash=auth_api.get_password_hash("Original123!"))

    with pytest.raises(HTTPException) as exc:
        await auth_api.change_password(
            request=_request(),
            data=PasswordChangeRequest(
                old_password="WrongOld!", new_password="NewPass123!", confirm_password="NewPass123!",
            ),
            current_user=current,
            db=FakeDB(),
        )

    assert exc.value.status_code == 400
    assert exc.value.detail == "原密码错误"


@pytest.mark.asyncio
async def test_change_password_rejects_mismatched_confirmation():
    current = user(password_hash=auth_api.get_password_hash("Original123!"))

    with pytest.raises(HTTPException) as exc:
        await auth_api.change_password(
            request=_request(),
            data=PasswordChangeRequest(
                old_password="Original123!", new_password="NewPass123!", confirm_password="Different!",
            ),
            current_user=current,
            db=FakeDB(),
        )

    assert exc.value.status_code == 400
    assert exc.value.detail == "新密码与确认密码不一致"


@pytest.mark.asyncio
async def test_change_password_rejects_same_as_current():
    current = user(password_hash=auth_api.get_password_hash("Original123!"))

    with pytest.raises(HTTPException) as exc:
        await auth_api.change_password(
            request=_request(),
            data=PasswordChangeRequest(
                old_password="Original123!", new_password="Original123!", confirm_password="Original123!",
            ),
            current_user=current,
            db=FakeDB(),
        )

    assert exc.value.status_code == 400
    assert exc.value.detail == "新密码不能与当前密码相同"


@pytest.mark.asyncio
async def test_change_password_rejects_weak_password(monkeypatch):
    async def fake_validate(password, db):
        return False, ["密码长度不能少于 8 个字符"]

    monkeypatch.setattr(auth_api, "validate_password_strength_from_settings", fake_validate)

    current = user(password_hash=auth_api.get_password_hash("Original123!"))

    with pytest.raises(HTTPException) as exc:
        await auth_api.change_password(
            request=_request(),
            data=PasswordChangeRequest(
                old_password="Original123!", new_password="weak", confirm_password="weak",
            ),
            current_user=current,
            db=FakeDB(),
        )

    assert exc.value.status_code == 400
    assert "密码长度不能少于" in exc.value.detail


@pytest.mark.asyncio
async def test_change_password_rejects_reused_password(monkeypatch):
    monkeypatch.setattr(auth_api, "validate_password_strength_from_settings", _always_valid)

    async def fake_reused(password, user_id, db):
        raise HTTPException(status_code=400, detail="新密码不能与最近使用过的 3 次密码相同")

    monkeypatch.setattr(auth_api, "check_password_not_reused", fake_reused)

    current = user(password_hash=auth_api.get_password_hash("Original123!"))

    with pytest.raises(HTTPException) as exc:
        await auth_api.change_password(
            request=_request(),
            data=PasswordChangeRequest(
                old_password="Original123!", new_password="ReusedPass123!", confirm_password="ReusedPass123!",
            ),
            current_user=current,
            db=FakeDB(),
        )

    assert exc.value.status_code == 400
    assert "最近使用过" in exc.value.detail


@pytest.mark.asyncio
async def test_change_password_success_updates_hash_and_logs(monkeypatch):
    monkeypatch.setattr(auth_api, "validate_password_strength_from_settings", _always_valid)
    monkeypatch.setattr(auth_api, "check_password_not_reused", _no_reuse_check)
    monkeypatch.setattr(auth_api, "record_password_history", _no_reuse_check)

    current = user(password_hash=auth_api.get_password_hash("Original123!"))
    db = FakeDB()

    response = await auth_api.change_password(
        request=_request(),
        data=PasswordChangeRequest(
            old_password="Original123!", new_password="NewPass123!", confirm_password="NewPass123!",
        ),
        current_user=current,
        db=db,
    )

    assert response.message == "密码修改成功"
    assert auth_api.verify_password("NewPass123!", current.password_hash)
    assert db.commits == 1
    assert any(getattr(obj, "change_type", None) == "user_password" for obj in db.added)


@pytest.mark.asyncio
async def test_force_change_password_rejects_when_not_required(monkeypatch):
    target = user(must_change_password=False)

    async def fake_load_challenge(token, request):
        return {"user_id": target.id}

    async def fake_get_challenge_user(payload, db):
        return target

    async def fake_delete_challenge(token):
        return None

    monkeypatch.setattr(auth_api, "_load_login_challenge", fake_load_challenge)
    monkeypatch.setattr(auth_api, "_get_challenge_user", fake_get_challenge_user)
    monkeypatch.setattr(auth_api, "_delete_login_challenge", fake_delete_challenge)

    with pytest.raises(HTTPException) as exc:
        await auth_api.force_change_password(
            request=_request(),
            response=Response(),
            data=ForcePasswordChangeRequest(
                challenge_token="tok", new_password="NewPass123!", confirm_password="NewPass123!",
            ),
            db=FakeDB(),
        )

    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_force_change_password_rejects_mismatched_confirmation(monkeypatch):
    target = user(must_change_password=True)

    async def fake_load_challenge(token, request):
        return {"user_id": target.id}

    async def fake_get_challenge_user(payload, db):
        return target

    monkeypatch.setattr(auth_api, "_load_login_challenge", fake_load_challenge)
    monkeypatch.setattr(auth_api, "_get_challenge_user", fake_get_challenge_user)

    with pytest.raises(HTTPException) as exc:
        await auth_api.force_change_password(
            request=_request(),
            response=Response(),
            data=ForcePasswordChangeRequest(
                challenge_token="tok", new_password="NewPass123!", confirm_password="Different!",
            ),
            db=FakeDB(),
        )

    assert exc.value.status_code == 400
    assert exc.value.detail == "两次输入的密码不一致"


@pytest.mark.asyncio
async def test_force_change_password_success_completes_login_when_no_mfa(monkeypatch):
    redis_store = FakeRedisSessionStore()
    monkeypatch.setattr(auth_api, "get_redis", lambda: redis_store)
    monkeypatch.setattr(session_core, "get_redis", lambda: redis_store)

    target = user(id=9, username="bob", is_superuser=True, must_change_password=True, mfa_enabled=False, password_hash=auth_api.get_password_hash("OldPass123!"))

    async def fake_load_challenge(token, request):
        return {"user_id": target.id, "remember": False}

    async def fake_get_challenge_user(payload, db):
        return target

    async def fake_delete_challenge(token):
        return None

    monkeypatch.setattr(auth_api, "_load_login_challenge", fake_load_challenge)
    monkeypatch.setattr(auth_api, "_get_challenge_user", fake_get_challenge_user)
    monkeypatch.setattr(auth_api, "_delete_login_challenge", fake_delete_challenge)
    monkeypatch.setattr(auth_api, "validate_password_strength_from_settings", _always_valid)
    monkeypatch.setattr(auth_api, "check_password_not_reused", _no_reuse_check)
    monkeypatch.setattr(auth_api, "record_password_history", _no_reuse_check)

    db = FakeDB(FakeResult(scalar_one_or_none=None))  # session_timeout setting lookup

    response = await auth_api.force_change_password(
        request=_request(),
        response=Response(),
        data=ForcePasswordChangeRequest(
            challenge_token="tok", new_password="NewPass123!", confirm_password="NewPass123!",
        ),
        db=db,
    )

    assert target.must_change_password is False
    assert auth_api.verify_password("NewPass123!", target.password_hash)
    assert response.data.user.username == "bob"


@pytest.mark.asyncio
async def test_force_change_password_requires_mfa_after_change(monkeypatch):
    target = user(id=9, username="bob", must_change_password=True, mfa_enabled=True, mfa_secret=None, password_hash=auth_api.get_password_hash("OldPass123!"))

    async def fake_load_challenge(token, request):
        return {"user_id": target.id, "remember": False}

    async def fake_get_challenge_user(payload, db):
        return target

    async def fake_save_challenge(token, payload):
        return None

    monkeypatch.setattr(auth_api, "_load_login_challenge", fake_load_challenge)
    monkeypatch.setattr(auth_api, "_get_challenge_user", fake_get_challenge_user)
    monkeypatch.setattr(auth_api, "_save_login_challenge", fake_save_challenge)
    monkeypatch.setattr(auth_api, "validate_password_strength_from_settings", _always_valid)
    monkeypatch.setattr(auth_api, "check_password_not_reused", _no_reuse_check)
    monkeypatch.setattr(auth_api, "record_password_history", _no_reuse_check)

    db = FakeDB()

    response = await auth_api.force_change_password(
        request=_request(),
        response=Response(),
        data=ForcePasswordChangeRequest(
            challenge_token="tok", new_password="NewPass123!", confirm_password="NewPass123!",
        ),
        db=db,
    )

    assert target.must_change_password is False
    assert response.data.requires_mfa is True
    assert response.data.setup is True
