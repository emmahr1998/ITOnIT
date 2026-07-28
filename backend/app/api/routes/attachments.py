import re
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from starlette.responses import Response

from app.dependencies import get_attachment_service, get_current_active_user, get_viewable_ticket
from app.models.ticket import Ticket
from app.models.user import User
from app.schemas.attachment import AttachmentResponse
from app.services.attachment_service import (
    AttachmentNotFoundError,
    AttachmentService,
    InvalidAttachmentError,
)

# Own router, not folded into tickets.py: attachments have enough distinct
# concerns (multipart upload, binary download responses) to warrant their
# own file, and tickets.py was already large after comments/history.
router = APIRouter(prefix="/tickets/{ticket_id}/attachments", tags=["Attachments"])


def _content_disposition(filename: str) -> str:
    """Build a safe Content-Disposition header value for a user-controlled
    filename - strips characters that could break header parsing/inject a
    second header, and RFC-6266-encodes it for non-ASCII names."""
    safe_ascii = re.sub(r'[\r\n"]', "_", filename)
    encoded = quote(filename, safe="")
    return f'attachment; filename="{safe_ascii}"; filename*=UTF-8\'\'{encoded}'


@router.get("", response_model=list[AttachmentResponse])
def list_attachments(
    ticket: Ticket = Depends(get_viewable_ticket),
    attachment_service: AttachmentService = Depends(get_attachment_service),
) -> list[AttachmentResponse]:
    attachments = attachment_service.list_attachments(ticket.id)
    return [AttachmentResponse.model_validate(attachment) for attachment in attachments]


@router.post("", response_model=AttachmentResponse, status_code=status.HTTP_201_CREATED)
async def upload_attachment(
    file: UploadFile = File(...),
    ticket: Ticket = Depends(get_viewable_ticket),
    attachment_service: AttachmentService = Depends(get_attachment_service),
    current_user: User = Depends(get_current_active_user),
) -> AttachmentResponse:
    content = await file.read()
    try:
        attachment = attachment_service.upload_attachment(
            current_user, ticket.id, file.filename or "upload", file.content_type, content
        )
    except InvalidAttachmentError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return AttachmentResponse.model_validate(attachment)


@router.get("/{attachment_id}")
def download_attachment(
    attachment_id: int,
    ticket: Ticket = Depends(get_viewable_ticket),
    attachment_service: AttachmentService = Depends(get_attachment_service),
) -> Response:
    try:
        attachment, content = attachment_service.download_attachment(ticket.id, attachment_id)
    except AttachmentNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Attachment not found") from exc
    return Response(
        content=content,
        media_type=attachment.content_type or "application/octet-stream",
        headers={"Content-Disposition": _content_disposition(attachment.original_filename)},
    )


@router.delete("/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_attachment(
    attachment_id: int,
    ticket: Ticket = Depends(get_viewable_ticket),
    attachment_service: AttachmentService = Depends(get_attachment_service),
    current_user: User = Depends(get_current_active_user),
) -> None:
    try:
        attachment_service.delete_attachment(current_user, ticket.id, attachment_id)
    except AttachmentNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Attachment not found") from exc
