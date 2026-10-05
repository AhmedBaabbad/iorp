"""Shared local file-storage adapter."""

import base64
from pathlib import Path
import uuid

from app.core.config import settings

MAX_LOGO_BYTES = 2 * 1024 * 1024


class InvalidLogoError(ValueError):
    pass


class LocalFileStorage:
    def __init__(self, root: str | None = None) -> None:
        self.root = Path(root or settings.uploads_dir).resolve()

    def save_logo(self, encoded: str, organization_id: uuid.UUID) -> str:
        content, extension = self._validated_content(encoded)
        return self.save_logo_content(content, organization_id, extension)

    def save_logo_content(self, content: bytes, organization_id: uuid.UUID, extension: str | None = None) -> str:
        if len(content) > MAX_LOGO_BYTES:
            raise InvalidLogoError("Logo exceeds maximum size.")
        detected = self._extension(content)
        if extension and extension != detected:
            raise InvalidLogoError("Logo content does not match its type.")
        extension = detected
        relative = Path("organizations") / str(organization_id) / f"logo_{uuid.uuid4()}.{extension}"
        destination = (self.root / relative).resolve()
        if self.root not in destination.parents:
            raise InvalidLogoError("Invalid storage path.")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
        return relative.as_posix()

    def validate_logo_content(self, content: bytes) -> tuple[str, str]:
        if len(content) > MAX_LOGO_BYTES:
            raise InvalidLogoError("Logo exceeds maximum size.")
        extension = self._extension(content)
        return extension, {"png": "image/png", "jpg": "image/jpeg", "webp": "image/webp"}[extension]

    def validate_logo(self, encoded: str) -> None:
        self._validated_content(encoded)

    def _validated_content(self, encoded: str) -> tuple[bytes, str]:
        payload = encoded.split(",", 1)[-1]
        try:
            content = base64.b64decode(payload, validate=True)
        except ValueError as exc:
            raise InvalidLogoError("Invalid logo encoding.") from exc
        if len(content) > MAX_LOGO_BYTES:
            raise InvalidLogoError("Logo exceeds maximum size.")
        return content, self._extension(content)

    def resolve(self, relative_path: str) -> Path:
        target = (self.root / relative_path).resolve()
        if self.root not in target.parents:
            raise FileNotFoundError
        return target

    def delete(self, relative_path: str) -> None:
        self.resolve(relative_path).unlink(missing_ok=True)

    def exists(self, relative_path: str) -> bool:
        return self.resolve(relative_path).is_file()

    @staticmethod
    def _extension(content: bytes) -> str:
        if content.startswith(b"\x89PNG\r\n\x1a\n"):
            return "png"
        if content.startswith(b"\xff\xd8\xff"):
            return "jpg"
        if len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP":
            return "webp"
        raise InvalidLogoError("Unsupported logo type.")


MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024
ATTACHMENT_TYPES = {"png": "image/png", "jpg": "image/jpeg", "webp": "image/webp", "pdf": "application/pdf"}


class InvalidAttachmentError(ValueError):
    pass


def save_attachment(content: bytes, organization_id: uuid.UUID, folder: str, storage: LocalFileStorage | None = None) -> tuple[str, str]:
    """A user's file (an image or a PDF, by its content, not its name) under the organization's folder:
    (relative path, content type)."""
    if not content:
        raise InvalidAttachmentError("EMPTY")
    if len(content) > MAX_ATTACHMENT_BYTES:
        raise InvalidAttachmentError("TOO_LARGE")
    if content.startswith(b"%PDF-"):
        extension = "pdf"
    else:
        try:
            extension = LocalFileStorage._extension(content)
        except InvalidLogoError as exc:
            raise InvalidAttachmentError("UNSUPPORTED_TYPE") from exc
    storage = storage or LocalFileStorage()
    relative = Path("organizations") / str(organization_id) / folder / f"{uuid.uuid4()}.{extension}"
    destination = (storage.root / relative).resolve()
    if storage.root not in destination.parents:
        raise InvalidAttachmentError("INVALID_PATH")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(content)
    return relative.as_posix(), ATTACHMENT_TYPES[extension]
