"""Disk storage for inventory product photos — no DB concerns here, just
files. `app/inventory.py` owns the corresponding `inventory_photos` rows."""

import os
import re
import uuid
from pathlib import Path

from fastapi import UploadFile

PHOTOS_DIR = Path(os.environ.get("PHOTOS_DIR", "photos"))

ALLOWED_CONTENT_TYPES = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}
MAX_UPLOAD_BYTES = 15 * 1024 * 1024

_SKU_RE = re.compile(r"[^A-Za-z0-9_-]+")


class InvalidPhotoUpload(Exception):
    pass


def _safe_sku(sku: str) -> str:
    """Never trust a SKU into a path unescaped, even though SKUs are normally
    server-generated — this is the one place a path-traversal attempt would
    matter, so guard it here rather than trusting every caller."""
    cleaned = _SKU_RE.sub("", sku)
    if not cleaned:
        raise InvalidPhotoUpload(f"SKU {sku!r} has no usable path characters")
    return cleaned


def item_photo_dir(sku: str) -> Path:
    return PHOTOS_DIR / _safe_sku(sku)


async def save_upload(sku: str, upload: UploadFile) -> tuple[str, str]:
    """Streams an UploadFile to disk under a server-chosen name, enforcing the
    content-type allow-list and size cap. Returns (filename, content_type).
    Raises InvalidPhotoUpload on anything that fails validation."""
    content_type = upload.content_type or ""
    ext = ALLOWED_CONTENT_TYPES.get(content_type)
    if ext is None:
        raise InvalidPhotoUpload(
            f"Unsupported content type {content_type!r} — allowed: {', '.join(ALLOWED_CONTENT_TYPES)}"
        )

    directory = item_photo_dir(sku)
    directory.mkdir(parents=True, exist_ok=True)

    # Server-generated name — never the client's filename, both to avoid
    # collisions/overwrites and to rule out path traversal via the upload name.
    filename = f"{_safe_sku(sku)}_{uuid.uuid4().hex[:8]}.{ext}"
    dest = directory / filename

    size = 0
    chunk_size = 1024 * 1024
    try:
        with open(dest, "wb") as f:
            while chunk := await upload.read(chunk_size):
                size += len(chunk)
                if size > MAX_UPLOAD_BYTES:
                    raise InvalidPhotoUpload(
                        f"Photo exceeds {MAX_UPLOAD_BYTES // (1024 * 1024)}MB limit"
                    )
                f.write(chunk)
    except InvalidPhotoUpload:
        dest.unlink(missing_ok=True)
        raise

    return filename, content_type


def delete_photo_file(sku: str, filename: str) -> None:
    path = item_photo_dir(sku) / filename
    path.unlink(missing_ok=True)


def photo_path(sku: str, filename: str) -> Path:
    return item_photo_dir(sku) / filename
