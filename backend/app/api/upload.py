"""
File Upload API Routes
"""
import os
import uuid
from io import BytesIO
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from PIL import Image, UnidentifiedImageError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.api.deps import PermissionChecker
from app.models import User
from app.config import settings

router = APIRouter(prefix="/upload", tags=["Upload"])

ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


def _get_upload_dir() -> Path:
    """Get and ensure upload directory exists"""
    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)
    return upload_dir


def _normalize_image(content: bytes, ext: str) -> bytes:
    format_map = {
        ".png": "PNG",
        ".jpg": "JPEG",
        ".jpeg": "JPEG",
        ".gif": "GIF",
        ".webp": "WEBP",
    }
    try:
        with Image.open(BytesIO(content)) as image:
            image.load()
            output = BytesIO()
            save_format = format_map[ext]
            if save_format == "JPEG" and image.mode not in ("RGB", "L"):
                image = image.convert("RGB")
            image.save(output, format=save_format)
            return output.getvalue()
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="文件内容不是有效图片",
        ) from exc


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
    # Validate file extension
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type: {ext}. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    # Read and validate file size
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File too large. Maximum size: {MAX_FILE_SIZE // (1024 * 1024)}MB",
        )

    content = _normalize_image(content, ext)

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
