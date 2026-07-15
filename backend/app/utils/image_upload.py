"""Shared image upload validation and normalization."""
from io import BytesIO

from fastapi import HTTPException, status
from PIL import Image, UnidentifiedImageError

ALLOWED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
MAX_IMAGE_FILE_SIZE = 10 * 1024 * 1024  # 10MB

_FORMAT_MAP = {".png": "PNG", ".jpg": "JPEG", ".jpeg": "JPEG", ".gif": "GIF", ".webp": "WEBP"}


def validate_image_extension(ext: str, detail: str) -> None:
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


def validate_image_size(content: bytes, detail: str) -> None:
    if len(content) > MAX_IMAGE_FILE_SIZE:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


def normalize_image(content: bytes, ext: str) -> bytes:
    """Decode, re-encode (converting to RGB for JPEG if needed), and return image bytes."""
    try:
        with Image.open(BytesIO(content)) as image:
            image.load()
            output = BytesIO()
            save_format = _FORMAT_MAP[ext]
            if save_format == "JPEG" and image.mode not in ("RGB", "L"):
                image = image.convert("RGB")
            image.save(output, format=save_format)
            return output.getvalue()
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="文件内容不是有效图片",
        ) from exc
