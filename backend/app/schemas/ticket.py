from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import TicketPriority, TicketStatus
from app.schemas.category import CategoryResponse


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
    category_id: int
    priority: TicketPriority = TicketPriority.MEDIUM

    @field_validator("title", "description")
    @classmethod
    def _strip(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be empty")
        return stripped


class TicketCreate(TicketContentBase):
    """POST /tickets request body.

    status/created_by/assigned_to are never accepted from the client -
    the service always sets status=NEW, created_by=the caller, assigned_to=None.
    """


class TicketUpdate(TicketContentBase):
    """PUT /tickets/{id} request body - full replacement, not a partial patch."""

    priority: TicketPriority


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
    status: TicketStatus
    priority: TicketPriority
    category: CategoryResponse
    created_by: TicketUserSummary
    assigned_technician: TicketUserSummary | None
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None
    closed_at: datetime | None
