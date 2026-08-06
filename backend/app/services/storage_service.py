import uuid
from pathlib import Path

from app.core.config import settings


class StorageService:
    """Pure filesystem I/O for attachments - no business rules, no DB access.

    Only responsible for: saving files, loading files, deleting files, and
    generating safe filenames. Every filename it's given (other than at
    construction) is resolved against the storage root and rejected if it
    would escape it - the one place path-traversal is defended against.
    """

    def __init__(self, base_path: Path | str | None = None) -> None:
        self._base_path = Path(base_path or settings.ATTACHMENT_STORAGE_PATH).resolve()
        self._base_path.mkdir(parents=True, exist_ok=True)

    def generate_stored_filename(self, original_filename: str) -> str:
        """A random name derived only from the extension - the original
        filename is never trusted or reused for the file on disk."""
        extension = Path(original_filename or "").suffix.lower()
        return f"{uuid.uuid4().hex}{extension}"

    def save(self, stored_filename: str, content: bytes) -> None:
        self._resolve(stored_filename).write_bytes(content)

    def load(self, stored_filename: str) -> bytes:
        return self._resolve(stored_filename).read_bytes()

    def delete(self, stored_filename: str) -> None:
        self._resolve(stored_filename).unlink(missing_ok=True)

    def _resolve(self, stored_filename: str) -> Path:
        """Resolve a stored filename to an absolute path, rejecting anything
        that would resolve outside the storage root (e.g. '../../etc/passwd')."""
        candidate = (self._base_path / stored_filename).resolve()
        if not candidate.is_relative_to(self._base_path):
            raise ValueError(f"Invalid stored filename: {stored_filename!r}")
        return candidate
