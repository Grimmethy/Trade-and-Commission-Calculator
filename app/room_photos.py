"""Room photo storage.

Photos live under <media dir>/<room_code>/, where the media dir comes from the
ROOM_PHOTOS_DIR env var (default data/room_photos/). Directories are keyed by
rooms.code at write time. rename_room_code in app/rooms.py changes that key, so
the rename path must move the directory or existing photos are orphaned; that
wiring belongs to the cleanup piece, not this module.

Uploads are read with a 5 MB cap, checked with Pillow (JPEG, PNG, WebP only),
and re-encoded after exif_transpose so EXIF and ICC metadata are dropped.
The module does no background work; it is called only from upload and delete.
"""

import io
import os
import re
import shutil
import uuid
from pathlib import Path

from PIL import Image, ImageOps

MAX_PHOTO_BYTES = 5 * 1024 * 1024
CHUNK_SIZE = 64 * 1024
THUMB_SIZE = 320
ALLOWED_FORMATS = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}
# Assumed room code character set; verify against the code generator in app/rooms.py.
_ROOM_CODE_RE = re.compile(r"[A-Za-z0-9_-]+")


class RoomPhotoError(Exception):
    """Carries an HTTP-style status code and a message. The router maps it to a response."""

    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


def room_photos_dir() -> Path:
    """Media root, read at call time so tests and deployments can override it."""
    return Path(os.environ.get("ROOM_PHOTOS_DIR", "data/room_photos/"))


def _check_room_code(room_code) -> None:
    if not isinstance(room_code, str) or not _ROOM_CODE_RE.fullmatch(room_code):
        raise RoomPhotoError(400, "invalid room code")


def read_capped(fileobj) -> bytes:
    """Read any object with .read(n) in chunks, raising 413 as soon as the cap is exceeded."""
    buf = io.BytesIO()
    total = 0
    while True:
        chunk = fileobj.read(CHUNK_SIZE)
        if not chunk:
            break
        total += len(chunk)
        if total > MAX_PHOTO_BYTES:
            raise RoomPhotoError(413, "photo exceeds the 5 MB limit")
        buf.write(chunk)
    return buf.getvalue()


def _open_checked(data: bytes) -> tuple[Image.Image, str]:
    """Verify the bytes are an allowed image format. Returns a freshly loaded image and its format."""
    try:
        probe = Image.open(io.BytesIO(data))
        fmt = probe.format
        probe.verify()
        img = Image.open(io.BytesIO(data))
        img.load()
    except (OSError, SyntaxError, ValueError, Image.DecompressionBombError):
        raise RoomPhotoError(415, "unreadable image")
    if fmt not in ALLOWED_FORMATS:
        raise RoomPhotoError(415, "only JPEG, PNG and WebP images are accepted")
    return img, fmt


def _encode(img: Image.Image, fmt: str) -> bytes:
    """Re-encode in the original format. No exif= or icc_profile= is passed, so metadata is dropped."""
    if fmt == "JPEG" and img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    out = io.BytesIO()
    img.save(out, format=fmt)
    return out.getvalue()


def _atomic_write(path: Path, data: bytes) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def save_room_photo(room_code: str, data: bytes) -> dict:
    """Validate, strip metadata, and write a photo plus its 320px thumbnail."""
    _check_room_code(room_code)
    if len(data) > MAX_PHOTO_BYTES:
        raise RoomPhotoError(413, "photo exceeds the 5 MB limit")

    img, fmt = _open_checked(data)
    img = ImageOps.exif_transpose(img)
    ext = ALLOWED_FORMATS[fmt]
    width, height = img.size

    thumb = img.copy()
    thumb.thumbnail((THUMB_SIZE, THUMB_SIZE))

    photo_id = uuid.uuid4().hex
    folder = room_photos_dir() / room_code
    folder.mkdir(parents=True, exist_ok=True)

    filename = f"{photo_id}{ext}"
    thumb_filename = f"{photo_id}_thumb{ext}"
    _atomic_write(folder / filename, _encode(img, fmt))
    _atomic_write(folder / thumb_filename, _encode(thumb, fmt))

    return {
        "id": photo_id,
        "filename": filename,
        "thumb_filename": thumb_filename,
        "width": width,
        "height": height,
    }


def delete_room_photos(room_code: str) -> None:
    """Remove all photos for a room. A missing directory is a no-op."""
    _check_room_code(room_code)
    target = room_photos_dir() / room_code
    if target.exists():
        shutil.rmtree(target)
