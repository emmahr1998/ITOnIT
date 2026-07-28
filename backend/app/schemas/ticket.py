from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import TicketStatus
from app.schemas.category import CategoryResponse
from app.schemas.priority import PriorityResponse


class TicketUserSummary(BaseModel):
    """Minimal, safe user info nested inside a ticket response - never password_hash."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    first_name: str
    last_name: str
    email: str


class TicketContentBase(BaseModel):
    """Shared validation for the editable content fields of a ticket."""

    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1)
    location: str | None = Field(default=None, max_length=200)
    category_id: int
    priority_id: int

    @field_validator("title", "description")
    @classmethod
    def _strip(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be empty")
        return stripped


class TicketPatch(BaseModel):
    """PATCH /tickets/{id} request body - partial update.

    Only title/description/location/category_id/priority_id may change
    here. Assignment and status stay in their own dedicated endpoints, and
    requester/timestamps are never client-controlled.
    """

    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, min_length=1)
    location: str | None = None
    category_id: int | None = None
    priority_id: int | None = None

    @field_validator("title", "description")
    @classmethod
    def _strip(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be empty")
        return stripped


class TicketNewCreate(TicketContentBase):
    """POST /ticket-new request body.

    requester_user_id is optional, and only Manager/Administrator callers
    may set it to someone other than themselves - the service rejects it
    outright for anyone else, so a normal employee's requester is always
    the authenticated caller.
    """

    requester_user_id: int | None = None


class TicketAssign(BaseModel):
    """PATCH /tickets/{id}/assign request body."""

    technician_id: int


class TicketStatusUpdate(BaseModel):
    """PATCH /tickets/{id}/status request body."""

    status: TicketStatus


class TicketResponse(BaseModel):
    """Ticket representation returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    ticket_number: str
    title: str
    description: str
    location: str | None
    status: TicketStatus
    priority: PriorityResponse
    category: CategoryResponse
    created_by: TicketUserSummary
    assigned_technician: TicketUserSummary | None
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None
    closed_at: datetime | None
