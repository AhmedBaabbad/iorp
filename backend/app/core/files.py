"""Uploaded files (PROJECT-FILES-003): one policy, small stored files, a storage that can be replaced, a quota.

    upload ─prepare→ checked by its content (not its name), images made small ─store→ storage key + metadata in the
    module's own table (the module stays its only writer); the bytes live in the storage, never in a business table.

Kinds of upload (the numbers are settings, core/config.py):
  logo        PNG / JPEG / WebP up to 1 MB → at most 400 px, kept as PNG (or WebP when smaller), ≤ 50 KB
  attachment  PNG / JPEG / WebP up to 5 MB → at most 1280 px, WebP quality 70, camera data removed, ≤ 200 KB
              PDF up to 2 MB, kept exactly as sent (a document is never altered)
Every organization has a quota (2 GB unless the platform sets another); an upload that would pass it is refused.
"""
from __future__ import annotations

import hashlib
import uuid
import warnings
from dataclasses import dataclass
from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import func, select

from app.core.config import settings
from app.core.db import Base
from app.core.utils import utc_now

IMAGE_TYPES = {"png": "image/png", "jpg": "image/jpeg", "webp": "image/webp"}
PDF = {"pdf": "application/pdf"}
MAX_PIXELS = 40_000_000  # a larger picture is refused before it is decoded (decompression bomb)


class FileRejected(ValueError):
    """Why an upload was refused: EMPTY, TOO_LARGE, UNSUPPORTED_TYPE, INVALID_IMAGE, INVALID_PDF, QUOTA_EXCEEDED."""

    def __init__(self, code: str, limit: int | None = None):
        super().__init__(code)
        self.code, self.limit = code, limit


@dataclass(frozen=True)
class Prepared:
    content: bytes
    extension: str
    media_type: str
    checksum: str

    @property
    def size(self) -> int:
        return len(self.content)


def policy() -> dict:
    """What each kind of upload accepts, for the screens (one source: the settings)."""
    return {
        "logo": {"types": list(IMAGE_TYPES.values()), "max_bytes": {m: settings.file_logo_max_upload for m in IMAGE_TYPES.values()}},
        "attachment": {"types": [*IMAGE_TYPES.values(), *PDF.values()],
                       "max_bytes": {**{m: settings.file_image_max_upload for m in IMAGE_TYPES.values()}, "application/pdf": settings.file_pdf_max_upload}},
    }


def read_limit(kind: str) -> int:
    """How much of an upload to read: one byte past the largest accepted size, so a larger file is seen and refused
    without being read whole."""
    return max(policy()[kind]["max_bytes"].values()) + 1


def detect(content: bytes) -> str:
    """The real type, from the first bytes (a renamed file is still what it is)."""
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if content.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "webp"
    if content.startswith(b"%PDF-"):
        return "pdf"
    raise FileRejected("UNSUPPORTED_TYPE")


def prepare(content: bytes, kind: str) -> Prepared:
    if not content:
        raise FileRejected("EMPTY")
    found = detect(content)
    if kind == "logo":
        if found not in IMAGE_TYPES:
            raise FileRejected("UNSUPPORTED_TYPE")
        _limit(content, settings.file_logo_max_upload)
        data, extension = _logo(content)
    elif kind == "attachment":
        if found == "pdf":
            _limit(content, settings.file_pdf_max_upload)
            if b"%%EOF" not in content[-2048:]:
                raise FileRejected("INVALID_PDF")
            data, extension = content, "pdf"
        else:
            _limit(content, settings.file_image_max_upload)
            data, extension = _photo(content)
    else:
        raise ValueError(f"unknown upload kind {kind}")
    media = {**IMAGE_TYPES, **PDF}[extension]
    return Prepared(data, extension, media, hashlib.sha256(data).hexdigest())


def _limit(content: bytes, limit: int) -> None:
    if len(content) > limit:
        raise FileRejected("TOO_LARGE", limit)


def _open(content: bytes) -> Image.Image:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            image = Image.open(BytesIO(content))
            if image.width * image.height > MAX_PIXELS:
                raise FileRejected("INVALID_IMAGE")
            image.load()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise FileRejected("INVALID_IMAGE") from exc
    return ImageOps.exif_transpose(image)  # the picture the right way up; nothing of the camera's data is written back


def _encode(image: Image.Image, fmt: str, **options) -> bytes:
    out = BytesIO()
    image.save(out, fmt, **options)  # a new file: no EXIF, GPS or other metadata of the original
    return out.getvalue()


def _photo(content: bytes) -> tuple[bytes, str]:
    """A photo as evidence: readable (labels, defects), small: WebP, longest side ≤ 1280 px, ≤ 200 KB."""
    image = _open(content)
    transparent = image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info)
    image = image.convert("RGBA" if transparent else "RGB")
    side, quality = settings.file_image_max_px, settings.file_image_quality
    while True:
        current = image.copy()
        current.thumbnail((side, side), Image.Resampling.LANCZOS)
        data = _encode(current, "WEBP", quality=quality, method=6)
        if len(data) <= settings.file_image_max_stored:
            return data, "webp"
        if quality > 40:
            quality -= 10
        elif side > 320:
            side = int(side * 0.8)  # an unusually detailed photo is made smaller rather than refused
        else:
            return data, "webp"


def _logo(content: bytes) -> tuple[bytes, str]:
    """A logo: transparency kept, ≤ 400 px, PNG (or a smaller WebP), ≤ 50 KB."""
    image = _open(content)
    image = image.convert("RGBA")
    side = settings.file_logo_max_px
    while True:
        current = image.copy()
        current.thumbnail((side, side), Image.Resampling.LANCZOS)
        # PNG first (every document renderer takes it, transparency kept), 256 colours next, WebP only if neither fits.
        for data, extension in ((_encode(current, "PNG", optimize=True), "png"),
                                (_encode(current.quantize(colors=256, method=Image.Quantize.FASTOCTREE), "PNG", optimize=True), "png"),
                                (_encode(current, "WEBP", quality=85, method=6), "webp")):
            if len(data) <= settings.file_logo_max_stored:
                return data, extension
        if side <= 96:
            return data, extension  # an unusually detailed logo is made smaller rather than refused
        side = int(side * 0.8)


def new_key(organization_id, module: str, extension: str) -> str:
    """organizations/{organization}/{module}/{yyyy}/{mm}/{uuid}.{ext}: nothing of the user's file name is used."""
    now = utc_now()
    return f"organizations/{organization_id}/{module}/{now:%Y}/{now:%m}/{uuid.uuid4()}.{extension}"


# ── quota ────────────────────────────────────────────────────────────────────────────────────────
_FILE_TABLES: dict[str, str] = {}


def register_file_table(table: str, size_column: str = "size_bytes") -> None:
    """A module declares the table that holds its files' metadata, so the organization's usage counts them."""
    _FILE_TABLES[table] = size_column


def usage(db, organization_id) -> int:
    """Bytes the organization's files occupy (archived ones too: they are still on the disk). Shared-table reads."""
    total = 0
    for name, column in _FILE_TABLES.items():
        table = Base.metadata.tables.get(name)
        if table is not None:
            total += db.scalar(select(func.coalesce(func.sum(table.c[column]), 0)).where(table.c.organization_id == organization_id)) or 0
    return int(total)


def quota(db, organization_id) -> int:
    organizations = Base.metadata.tables["foundation_organizations"]
    value = db.scalar(select(organizations.c.storage_quota_bytes).where(organizations.c.id == organization_id))
    return int(value or settings.file_organization_quota)


def store(db, storage, organization_id, module: str, content: bytes, kind: str, replacing: int = 0) -> tuple[str, Prepared]:
    """Checked, made small, within the quota (less `replacing`, a file this one replaces), then written: (key, prepared).

    The caller writes its metadata row next and, if that fails, deletes the file (compensate_new_file): no file without
    a row, no row without a file."""
    prepared = prepare(content, kind)
    if usage(db, organization_id) - replacing + prepared.size > quota(db, organization_id):
        raise FileRejected("QUOTA_EXCEEDED", quota(db, organization_id))
    key = new_key(organization_id, module, prepared.extension)
    storage.put(key, prepared.content)
    return key, prepared
