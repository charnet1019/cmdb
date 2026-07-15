"""Tests for POST /upload/image and DELETE /upload/image/{filename}.

delete_image in particular guards against path traversal
(`../../etc/passwd`-style filenames) — security-relevant and previously
untested.
"""
import pytest
from fastapi import HTTPException

from tests.factories import FakeDB, user

from app.api import upload as upload_api


class FakeUploadFile:
    def __init__(self, filename="logo.png", content=b"fake-png-bytes"):
        self.filename = filename
        self._content = content

    async def read(self):
        return self._content


@pytest.fixture(autouse=True)
def isolated_upload_dir(tmp_path, monkeypatch):
    """Redirect settings.UPLOAD_DIR to a throwaway tmp directory for every
    test in this file, so we never touch the real upload directory."""
    monkeypatch.setattr(upload_api.settings, "UPLOAD_DIR", str(tmp_path))
    return tmp_path


@pytest.mark.asyncio
async def test_upload_image_rejects_unsupported_extension():
    with pytest.raises(HTTPException) as exc:
        await upload_api.upload_image(
            file=FakeUploadFile(filename="malware.exe"),
            db=FakeDB(),
            current_user=user(is_superuser=True),
        )

    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_upload_image_rejects_oversized_file(monkeypatch):
    monkeypatch.setattr(upload_api, "MAX_IMAGE_FILE_SIZE", 10)

    with pytest.raises(HTTPException) as exc:
        await upload_api.upload_image(
            file=FakeUploadFile(content=b"x" * 100),
            db=FakeDB(),
            current_user=user(is_superuser=True),
        )

    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_upload_image_normalizes_and_saves_file(monkeypatch, isolated_upload_dir):
    monkeypatch.setattr(upload_api, "normalize_image", lambda content, ext: b"normalized-bytes")

    response = await upload_api.upload_image(
        file=FakeUploadFile(filename="logo.png", content=b"raw-bytes"),
        db=FakeDB(),
        current_user=user(is_superuser=True),
    )

    assert response["code"] == 0
    filename = response["data"]["filename"]
    assert filename.endswith(".png")
    assert response["data"]["url"] == f"/uploads/{filename}"
    saved_path = isolated_upload_dir / filename
    assert saved_path.exists()
    assert saved_path.read_bytes() == b"normalized-bytes"


@pytest.mark.asyncio
async def test_delete_image_rejects_path_traversal_filename():
    with pytest.raises(HTTPException) as exc:
        await upload_api.delete_image(
            filename="../../etc/passwd",
            db=FakeDB(),
            current_user=user(is_superuser=True),
        )

    assert exc.value.status_code == 400
    assert exc.value.detail == "非法文件名"


@pytest.mark.asyncio
async def test_delete_image_rejects_absolute_path_escaping_upload_dir():
    with pytest.raises(HTTPException) as exc:
        await upload_api.delete_image(
            filename="/etc/passwd",
            db=FakeDB(),
            current_user=user(is_superuser=True),
        )

    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_delete_image_404_when_file_missing():
    with pytest.raises(HTTPException) as exc:
        await upload_api.delete_image(
            filename="does-not-exist.png",
            db=FakeDB(),
            current_user=user(is_superuser=True),
        )

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_delete_image_removes_existing_file(isolated_upload_dir):
    target = isolated_upload_dir / "existing.png"
    target.write_bytes(b"data")

    response = await upload_api.delete_image(
        filename="existing.png",
        db=FakeDB(),
        current_user=user(is_superuser=True),
    )

    assert response["data"]["deleted"] == "existing.png"
    assert not target.exists()
