"""File storage (PROJECT-FILES-003): where the bytes of uploaded files live, behind one small interface.

Business tables keep a storage key (organizations/{organization}/{module}/{yyyy}/{mm}/{uuid}.{ext}) and the file's
metadata, never its bytes nor an absolute path. LocalFileStorage keeps the files under UPLOADS_DIR; another storage
(S3, MinIO) implements the same five methods and nothing else changes. Keys written before (organizations/{org}/…
without a year) are read the same way.
"""

from pathlib import Path
from typing import Protocol
import logging
from contextlib import contextmanager

from app.core.config import settings
from app.core.files import FileRejected, IMAGE_TYPES, detect

logger = logging.getLogger(__name__)


class FileStorage(Protocol):
    def put(self, key: str, content: bytes) -> None: ...
    def read(self, key: str) -> bytes: ...
    def delete(self, key: str) -> None: ...
    def exists(self, key: str) -> bool: ...
    def resolve(self, key: str) -> Path: ...  # a local path to stream from; a remote storage downloads to a temporary file


@contextmanager
def compensate_new_file(db, storage, path, is_referenced):
    """Clean up a new file only after DB confirms no committed reference.

    A lost commit acknowledgement is ambiguous: retain the file when the DB
    cannot be queried, allowing reconciliation instead of losing committed data.
    """
    try:
        yield
    except Exception:
        try:
            db.rollback()
            if not is_referenced():
                storage.delete(path)
        except Exception as cleanup_error:
            logger.error('File compensation needs reconciliation (%s)', type(cleanup_error).__name__)
        raise


class InvalidLogoError(ValueError):
    pass


# An attachment refused by the policy; str(error) is its code (EMPTY, TOO_LARGE, UNSUPPORTED_TYPE, QUOTA_EXCEEDED …).
InvalidAttachmentError = FileRejected


class LocalFileStorage:
    def __init__(self, root: str | None = None) -> None:
        self.root = Path(root or settings.uploads_dir).resolve()

    def resolve(self, relative_path: str) -> Path:
        target = (self.root / relative_path).resolve()
        if self.root not in target.parents:
            raise FileNotFoundError
        return target

    def put(self, key: str, content: bytes) -> None:
        destination = self.resolve(key)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)

    def read(self, key: str) -> bytes:
        return self.resolve(key).read_bytes()

    def delete(self, relative_path: str) -> None:
        self.resolve(relative_path).unlink(missing_ok=True)

    def exists(self, relative_path: str) -> bool:
        return self.resolve(relative_path).is_file()

    @staticmethod
    def media_type(content: bytes) -> str:
        """The image type of a stored logo (by its content)."""
        try:
            found = detect(content)
        except FileRejected as exc:
            raise InvalidLogoError("Unsupported logo type.") from exc
        if found not in IMAGE_TYPES:
            raise InvalidLogoError("Unsupported logo type.")
        return IMAGE_TYPES[found]
