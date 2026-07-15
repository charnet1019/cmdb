"""
File Upload API Routes
"""
import os
import uuid
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.api.deps import PermissionChecker
from app.models import User
from app.config import settings
from app.utils.image_upload import (
    ALLOWED_IMAGE_EXTENSIONS,
    MAX_IMAGE_FILE_SIZE,
    validate_image_extension,
    validate_image_size,
    normalize_image,
)

router = APIRouter(prefix="/upload", tags=["Upload"])


def _get_upload_dir() -> Path:
    """Get and ensure upload directory exists"""
    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)
    return upload_dir


@router.post("/image")
async def upload_image(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("sys_config")),
):
    """
    Upload an image file.
    Requires sys_config permission.
    Returns the URL path to access the uploaded image.
    """
    ext = os.path.splitext(file.filename or "")[1].lower()
    validate_image_extension(
        ext, f"Unsupported file type: {ext}. Allowed: {', '.join(ALLOWED_IMAGE_EXTENSIONS)}"
    )

    content = await file.read()
    validate_image_size(
        content, f"File too large. Maximum size: {MAX_IMAGE_FILE_SIZE // (1024 * 1024)}MB"
    )

    content = normalize_image(content, ext)

    # Generate unique filename preserving extension
    filename = f"{uuid.uuid4().hex}{ext}"
    upload_dir = _get_upload_dir()
    file_path = upload_dir / filename

    # Write file
    file_path.write_bytes(content)

    url = f"/uploads/{filename}"

    return {
        "code": 0,
        "message": "success",
        "data": {"url": url, "filename": filename},
    }


@router.delete("/image/{filename}")
async def delete_image(
    filename: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("sys_config")),
):
    """
    Delete an uploaded image file.
    Requires sys_config permission.
    """
    if Path(filename).name != filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="非法文件名")

    upload_dir = _get_upload_dir().resolve()
    file_path = (upload_dir / filename).resolve()
    if upload_dir not in file_path.parents and file_path != upload_dir:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="非法文件路径")

    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File not found: {filename}",
        )

    file_path.unlink()

    return {
        "code": 0,
        "message": "success",
        "data": {"deleted": filename},
    }
