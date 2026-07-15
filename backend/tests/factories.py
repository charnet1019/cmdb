"""Shared test infrastructure: fake async DB/session primitives and model
factories, used across all test_*.py files so fixtures aren't duplicated
per-file.
"""
from datetime import datetime
import importlib.util
import sys
import types

# app.api.__init__ imports the auth router, whose avatar helpers import Pillow,
# and the MFA helpers import pyotp/qrcode. Tests that don't exercise those
# code paths still trigger the import chain, so stub the modules when the
# real packages aren't installed in the local test environment.
if importlib.util.find_spec("PIL") is None:
    pil_module = types.ModuleType("PIL")
    image_module = types.ModuleType("PIL.Image")
    pil_module.Image = image_module
    pil_module.UnidentifiedImageError = ValueError
    sys.modules["PIL"] = pil_module
    sys.modules["PIL.Image"] = image_module

if importlib.util.find_spec("pyotp") is None:
    pyotp_module = types.ModuleType("pyotp")

    class _TOTP:
        def __init__(self, secret):
            self.secret = secret

        def verify(self, code):
            return code == "123456"

        def provisioning_uri(self, name, issuer_name=None):
            return f"otpauth://totp/{name}"

    pyotp_module.TOTP = _TOTP
    pyotp_module.random_base32 = lambda: "JBSWY3DPEHPK3PXP"
    sys.modules["pyotp"] = pyotp_module

if importlib.util.find_spec("qrcode") is None:
    qrcode_module = types.ModuleType("qrcode")

    class _QR:
        def save(self, buffer, format=None):
            buffer.write(b"png")

    qrcode_module.make = lambda uri: _QR()
    sys.modules["qrcode"] = qrcode_module


from app.models import Asset, Authorization, Group, Organization, User


class ScalarList:
    def __init__(self, values):
        self.values = values

    def all(self):
        return self.values

    def first(self):
        return self.values[0] if self.values else None


class FakeResult:
    def __init__(self, *, scalar=None, scalar_one=None, scalar_one_or_none=None, scalars=None, all_rows=None, one_row=None):
        self._scalar = scalar
        self._scalar_one = scalar_one if scalar_one is not None else scalar
        self._scalar_one_or_none = scalar_one_or_none if scalar_one_or_none is not None else scalar
        self._scalars = scalars if scalars is not None else []
        self._all_rows = all_rows if all_rows is not None else []
        self._one_row = one_row

    def scalar(self):
        return self._scalar

    def scalar_one(self):
        return self._scalar_one

    def scalar_one_or_none(self):
        return self._scalar_one_or_none

    def scalars(self):
        return ScalarList(self._scalars)

    def all(self):
        return self._all_rows

    def first(self):
        return self._all_rows[0] if self._all_rows else None

    def one(self):
        return self._one_row

    def fetchall(self):
        return self._all_rows

    def __iter__(self):
        return iter(self._all_rows)


class FakeDB:
    def __init__(self, *results):
        self.results = list(results)
        self.added = []
        self.deleted = []
        self.commits = 0
        self.flushes = 0
        self.rollbacks = 0
        self.executed = []
        self._next_id = 100

    async def execute(self, statement):
        self.executed.append(statement)
        if not self.results:
            raise AssertionError(f"Unexpected execute: {statement}")
        return self.results.pop(0)

    async def scalar(self, statement):
        result = await self.execute(statement)
        return result.scalar()

    def add(self, obj):
        self.added.append(obj)

    async def delete(self, obj):
        self.deleted.append(obj)

    async def flush(self):
        self.flushes += 1
        self._hydrate_added()

    async def commit(self):
        self.commits += 1
        self._hydrate_added()

    async def rollback(self):
        self.rollbacks += 1

    async def refresh(self, obj):
        self._hydrate(obj)

    def _hydrate_added(self):
        for obj in self.added:
            self._hydrate(obj)

    def _hydrate(self, obj):
        if getattr(obj, "id", None) is None:
            if obj.__class__.__name__ == "Asset":
                obj.id = f"asset-{self._next_id}"
            else:
                obj.id = self._next_id
            self._next_id += 1
        now = datetime(2026, 1, 1, 0, 0, 0)
        for field in ("created_at", "updated_at"):
            if hasattr(obj, field) and getattr(obj, field, None) is None:
                setattr(obj, field, now)


def user(**kwargs):
    data = {
        "id": 1,
        "username": "alice",
        "email": "alice@example.com",
        "full_name": "Alice",
        "phone": None,
        "password_hash": "hash",
        "is_active": True,
        "is_superuser": False,
        "mfa_enabled": False,
        "mfa_secret": None,
        "must_change_password": False,
        "avatar_url": None,
        "last_login_at": None,
        "created_at": datetime(2026, 1, 1, 0, 0, 0),
    }
    data.update(kwargs)
    return User(**data)


def group(**kwargs):
    data = {
        "id": 10,
        "name": "ops",
        "description": "Operations",
        "is_default": False,
        "created_at": datetime(2026, 1, 1, 0, 0, 0),
    }
    data.update(kwargs)
    return Group(**data)


def asset(**kwargs):
    data = {
        "id": "asset-1",
        "name": "db-primary",
        "category": "database",
        "internal_address": "10.0.0.10",
        "external_address": None,
        "platform": "PostgreSQL",
        "db_type": "postgres",
        "organization_id": 7,
        "notes": "primary",
        "extra_data": {"version": "16", "oob_password": "secret"},
        "created_at": datetime(2026, 1, 1, 0, 0, 0),
        "updated_at": datetime(2026, 1, 2, 0, 0, 0),
        "applicant": "team-a",
        "namespace": "public",
        "owner_id": 1,
        "owner_name": "Alice",
        "status": "active",
    }
    data.update(kwargs)
    return Asset(**data)


def asset_with_credentials(**kwargs):
    item = asset(**kwargs)
    item.credentials = []
    return item


def organization(**kwargs):
    data = {
        "id": 7,
        "name": "Database Team",
        "parent_id": None,
        "path": "7",
        "level": 0,
        "created_at": datetime(2026, 1, 1, 0, 0, 0),
    }
    data.update(kwargs)
    return Organization(**data)


def auth(**kwargs):
    data = {
        "id": 50,
        "entity_type": "user",
        "entity_id": 1,
        "target_type": "asset",
        "target_ids": ["asset-1"],
        "permissions": ["view"],
        "valid_from": None,
        "valid_until": None,
        "is_active": True,
        "created_by": 1,
        "created_at": datetime(2026, 1, 1, 0, 0, 0),
    }
    data.update(kwargs)
    return Authorization(**data)


class FakeRedisSessionStore:
    """In-memory stand-in for the Redis client used by app.core.session,
    app.api.auth's login-lockout/challenge helpers, and rate limiters."""

    def __init__(self):
        self.values = {}
        self.sets = {}
        self.ttls = {}

    async def setex(self, key, ttl, value):
        self.values[key] = value
        self.ttls[key] = ttl

    async def get(self, key):
        return self.values.get(key)

    async def mget(self, *keys):
        return [self.values.get(key) for key in keys]

    async def incr(self, key):
        current = int(self.values.get(key, 0)) + 1
        self.values[key] = current
        return current

    async def expire(self, key, ttl):
        self.ttls[key] = ttl
        return True

    async def delete(self, *keys):
        deleted = 0
        for key in keys:
            removed = False
            if key in self.values:
                del self.values[key]
                removed = True
            if key in self.sets:
                del self.sets[key]
                removed = True
            self.ttls.pop(key, None)
            if removed:
                deleted += 1
        return deleted

    async def sadd(self, key, value):
        self.sets.setdefault(key, set()).add(value)
        return 1

    async def srem(self, key, value):
        values = self.sets.get(key)
        if not values or value not in values:
            return 0
        values.remove(value)
        if not values:
            self.sets.pop(key, None)
        return 1

    async def smembers(self, key):
        return set(self.sets.get(key, set()))

    async def exists(self, key):
        return key in self.values or key in self.sets

    async def ttl(self, key):
        return self.ttls.get(key, -1)
