import mimetypes
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.attachment import Attachment
from app.models.user import User
from app.repositories.attachment import AttachmentRepository
from app.services.history_service import HistoryService
from app.services.storage_service import StorageService

_ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".pdf", ".txt", ".docx", ".xlsx"}


class AttachmentNotFoundError(Exception):
    """Raised when an attachment id does not exist, or does not belong to the given ticket."""


class InvalidAttachmentError(Exception):
    """Raised when an upload is empty, oversized, or an unsupported file type."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class AttachmentService:
    """Owns attachment business rules: upload validation and history recording.

    Ticket-level access (can this user see/attach to this ticket at all) is
    verified by the route via TicketService/get_viewable_ticket before this
    is ever called, exactly like CommentService - that check is never
    duplicated here. Unlike comments, the business rules give attachments no
    separate per-item ownership layer: any user who can view the ticket may
    also upload, download, or delete any attachment on it.

    Also owns the transaction boundary for metadata writes (same convention
    as CategoryService/TicketService/CommentService).
    """

    def __init__(
        self,
        db: Session,
        attachment_repository: AttachmentRepository | None = None,
        storage_service: StorageService | None = None,
        history_service: HistoryService | None = None,
    ) -> None:
        self._db = db
        self._attachment_repository = (
            attachment_repository if attachment_repository is not None else AttachmentRepository(db)
        )
        self._storage_service = storage_service if storage_service is not None else StorageService()
        self._history_service = (
            history_service if history_service is not None else HistoryService(db)
        )

    def list_attachments(self, ticket_id: int) -> list[Attachment]:
        return self._attachment_repository.list_for_ticket(ticket_id)

    def get_attachment(self, ticket_id: int, attachment_id: int) -> Attachment:
        attachment = self._attachment_repository.get_by_id(attachment_id)
        if attachment is None or attachment.ticket_id != ticket_id:
            raise AttachmentNotFoundError
        return attachment

    def upload_attachment(
        self,
        current_user: User,
        ticket_id: int,
        original_filename: str,
        content_type: str | None,
        content: bytes,
    ) -> Attachment:
        if not content:
            raise InvalidAttachmentError("Uploaded file is empty")
        if len(content) > settings.MAX_ATTACHMENT_SIZE_BYTES:
            raise InvalidAttachmentError("Uploaded file exceeds the maximum allowed size")

        extension = Path(original_filename or "").suffix.lower()
        if extension not in _ALLOWED_EXTENSIONS:
            raise InvalidAttachmentError(f"Unsupported file type: {extension or 'unknown'}")

        # Never trust the client's declared filename for storage - only its
        # (already-validated) extension survives into the generated name.
        stored_filename = self._storage_service.generate_stored_filename(original_filename)
        self._storage_service.save(stored_filename, content)

        # The content type is derived from the validated extension, not the
        # client-supplied header, which is attacker-controlled and inconsistent.
        resolved_content_type = (
            mimetypes.guess_type(original_filename)[0] or content_type or "application/octet-stream"
        )

        attachment = Attachment(
            ticket_id=ticket_id,
            uploaded_by_user_id=current_user.id,
            original_filename=original_filename,
            stored_filename=stored_filename,
            file_path=stored_filename,
            content_type=resolved_content_type,
            file_size=len(content),
        )
        attachment.uploaded_by = current_user
        self._attachment_repository.create(attachment)
        self._history_service.record(
            ticket_id, current_user, "attachment_added", None, original_filename
        )
        self._db.commit()
        return attachment

    def download_attachment(self, ticket_id: int, attachment_id: int) -> tuple[Attachment, bytes]:
        attachment = self.get_attachment(ticket_id, attachment_id)
        content = self._storage_service.load(attachment.file_path)
        return attachment, content

    def delete_attachment(self, current_user: User, ticket_id: int, attachment_id: int) -> None:
        attachment = self.get_attachment(ticket_id, attachment_id)
        original_filename = attachment.original_filename
        file_path = attachment.file_path

        # Delete the DB record (and commit) before the physical file: if the
        # physical delete then fails, the result is an orphaned file on disk
        # (harmless, invisible to users) rather than a DB record pointing at
        # a file that's already gone (a broken reference, surfaced as a
        # confusing download failure).
        self._attachment_repository.delete(attachment)
        self._history_service.record(
            ticket_id, current_user, "attachment_deleted", original_filename, None
        )
        self._db.commit()
        self._storage_service.delete(file_path)
