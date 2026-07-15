"""Tests for POST /auth/login and its lockout/must-change-password/MFA branching.

This is core authentication logic (credential check, timing-safe unknown-user
handling, brute-force lockout, forced-password-change and MFA gating) that
previously had zero direct test coverage.
"""
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, Response

from tests.factories import FakeDB, FakeRedisSessionStore, FakeResult, user

from app.api import auth as auth_api
from app.core import session as session_core
from app.schemas import LoginRequest


def _request(ip="127.0.0.1", ua="pytest"):
    return SimpleNamespace(
        client=SimpleNamespace(host=ip),
        headers={"user-agent": ua},
        url=SimpleNamespace(scheme="http"),
    )


@pytest.mark.asyncio
async def test_login_rejects_unknown_username_without_leaking_existence(monkeypatch):
    redis_store = FakeRedisSessionStore()
    monkeypatch.setattr(auth_api, "get_redis", lambda: redis_store)

    db = FakeDB(
        FakeResult(scalar_one_or_none=None),  # user lookup -> not found
        FakeResult(scalar_one_or_none=None),  # max_login_attempts setting lookup
        FakeResult(scalar_one_or_none=None),  # lockout_duration setting lookup
    )

    with pytest.raises(HTTPException) as exc:
        await auth_api.login(
            request=_request(),
            response=Response(),
            data=LoginRequest(username="ghost", password="whatever"),
            db=db,
        )

    assert exc.value.status_code == 401
    assert exc.value.detail == "用户名或密码错误"
    # A failed-login log row must still be recorded for the unknown username.
    assert any(getattr(obj, "failure_reason", None) == "用户不存在" for obj in db.added)


@pytest.mark.asyncio
async def test_login_rejects_disabled_user():
    target = user(username="bob", is_active=False, password_hash=auth_api.get_password_hash("Secret123!"))
    db = FakeDB(FakeResult(scalar_one_or_none=target))

    with pytest.raises(HTTPException) as exc:
        await auth_api.login(
            request=_request(),
            response=Response(),
            data=LoginRequest(username="bob", password="Secret123!"),
            db=db,
        )

    assert exc.value.status_code == 401
    assert exc.value.detail == "用户已被禁用"


@pytest.mark.asyncio
async def test_login_rejects_wrong_password(monkeypatch):
    redis_store = FakeRedisSessionStore()
    monkeypatch.setattr(auth_api, "get_redis", lambda: redis_store)

    target = user(username="bob", password_hash=auth_api.get_password_hash("Secret123!"))
    db = FakeDB(
        FakeResult(scalar_one_or_none=target),
        FakeResult(scalar_one_or_none=None),  # max_login_attempts setting lookup
        FakeResult(scalar_one_or_none=None),  # lockout_duration setting lookup
    )

    with pytest.raises(HTTPException) as exc:
        await auth_api.login(
            request=_request(),
            response=Response(),
            data=LoginRequest(username="bob", password="WrongPass!"),
            db=db,
        )

    assert exc.value.status_code == 401
    assert exc.value.detail == "用户名或密码错误"


@pytest.mark.asyncio
async def test_login_locks_account_after_max_attempts(monkeypatch):
    redis_store = FakeRedisSessionStore()
    monkeypatch.setattr(auth_api, "get_redis", lambda: redis_store)

    # Pre-seed the failure counters one below the (default) lockout threshold
    # for both the ip-scoped and username-scoped guard keys.
    from app.api.auth import LOGIN_FAILURE_KEY_PREFIX, _login_guard_key, _login_guard_username_key

    request = _request()
    ip_key = f"{LOGIN_FAILURE_KEY_PREFIX}{_login_guard_key('bob', request)}"
    name_key = f"{LOGIN_FAILURE_KEY_PREFIX}{_login_guard_username_key('bob')}"
    redis_store.values[ip_key] = 4
    redis_store.values[name_key] = 4

    target = user(username="bob", password_hash=auth_api.get_password_hash("Secret123!"))
    db = FakeDB(
        FakeResult(scalar_one_or_none=target),
        FakeResult(scalar_one_or_none=None),  # max_login_attempts -> default 5
        FakeResult(scalar_one_or_none=None),  # lockout_duration -> default 30
    )

    with pytest.raises(HTTPException) as exc:
        await auth_api.login(
            request=request,
            response=Response(),
            data=LoginRequest(username="bob", password="WrongPass!"),
            db=db,
        )

    assert exc.value.status_code == 401  # this attempt still reports wrong-password

    # The next attempt must be locked out regardless of password correctness.
    db2 = FakeDB()
    with pytest.raises(HTTPException) as exc2:
        await auth_api.login(
            request=request,
            response=Response(),
            data=LoginRequest(username="bob", password="Secret123!"),
            db=db2,
        )
    assert exc2.value.status_code == 429


@pytest.mark.asyncio
async def test_login_locked_account_blocks_before_password_check(monkeypatch):
    redis_store = FakeRedisSessionStore()
    monkeypatch.setattr(auth_api, "get_redis", lambda: redis_store)

    from app.api.auth import LOGIN_LOCK_KEY_PREFIX, _login_guard_key

    request = _request()
    lock_key = f"{LOGIN_LOCK_KEY_PREFIX}{_login_guard_key('bob', request)}"
    redis_store.values[lock_key] = "1"

    db = FakeDB()  # no DB access should happen once locked

    with pytest.raises(HTTPException) as exc:
        await auth_api.login(
            request=request,
            response=Response(),
            data=LoginRequest(username="bob", password="Secret123!"),
            db=db,
        )

    assert exc.value.status_code == 429
    assert db.executed == []


@pytest.mark.asyncio
async def test_login_success_returns_token_for_normal_user(monkeypatch):
    redis_store = FakeRedisSessionStore()
    monkeypatch.setattr(auth_api, "get_redis", lambda: redis_store)
    monkeypatch.setattr(session_core, "get_redis", lambda: redis_store)

    target = user(
        id=5, username="bob", is_superuser=True,
        password_hash=auth_api.get_password_hash("Secret123!"),
        must_change_password=False, mfa_enabled=False,
    )
    db = FakeDB(
        FakeResult(scalar_one_or_none=target),  # user lookup
        FakeResult(scalar_one_or_none=None),    # session_timeout setting (via _complete_login)
    )

    response = await auth_api.login(
        request=_request(),
        response=Response(),
        data=LoginRequest(username="bob", password="Secret123!"),
        db=db,
    )

    assert response.data.user.username == "bob"
    assert "view" in response.data.user.permissions
    assert db.commits >= 1


@pytest.mark.asyncio
async def test_login_requires_forced_password_change_before_session(monkeypatch):
    redis_store = FakeRedisSessionStore()
    monkeypatch.setattr(auth_api, "get_redis", lambda: redis_store)

    target = user(
        id=5, username="bob",
        password_hash=auth_api.get_password_hash("Secret123!"),
        must_change_password=True,
    )
    db = FakeDB(FakeResult(scalar_one_or_none=target))

    response = await auth_api.login(
        request=_request(),
        response=Response(),
        data=LoginRequest(username="bob", password="Secret123!"),
        db=db,
    )

    assert response.data.must_change_password is True
    assert response.data.challenge_token


@pytest.mark.asyncio
async def test_login_requires_mfa_when_enabled(monkeypatch):
    redis_store = FakeRedisSessionStore()
    monkeypatch.setattr(auth_api, "get_redis", lambda: redis_store)

    target = user(
        id=5, username="bob",
        password_hash=auth_api.get_password_hash("Secret123!"),
        must_change_password=False, mfa_enabled=True, mfa_secret=None,
    )
    db = FakeDB(FakeResult(scalar_one_or_none=target))

    response = await auth_api.login(
        request=_request(),
        response=Response(),
        data=LoginRequest(username="bob", password="Secret123!"),
        db=db,
    )

    assert response.data.requires_mfa is True
    assert response.data.setup is True  # no mfa_secret yet -> must bind
    assert response.data.challenge_token
