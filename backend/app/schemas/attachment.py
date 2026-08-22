from pydantic import BaseModel, ConfigDict

from app.schemas.ticket import TicketUserSummary
from app.schemas.types import UTCDatetime


class AttachmentResponse(BaseModel):
    """Attachment metadata returned by the API.

    Deliberately excludes stored_filename/file_path - the internal storage
    location is never exposed, only the original filename the user uploaded.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    ticket_id: int
    original_filename: str
    content_type: str | None
    file_size: int
    uploaded_by: TicketUserSummary
    created_at: UTCDatetime
