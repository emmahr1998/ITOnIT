from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.ticket import TicketUserSummary
from app.schemas.types import UTCDatetime


class CommentContentBase(BaseModel):
    """Shared validation for comment writes.

    No max_length: Comment.content is an unbounded Text column, so there is
    no database length to mirror here - only non-empty is enforceable.
    """

    content: str = Field(min_length=1)

    @field_validator("content")
    @classmethod
    def _strip(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("content must not be empty")
        return stripped


class CommentCreate(CommentContentBase):
    """POST /tickets/{id}/comments request body."""


class CommentUpdate(CommentContentBase):
    """PUT /tickets/{id}/comments/{commentId} request body."""


class CommentResponse(BaseModel):
    """Comment representation returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    ticket_id: int
    content: str
    author: TicketUserSummary
    created_at: UTCDatetime
    updated_at: UTCDatetime | None
