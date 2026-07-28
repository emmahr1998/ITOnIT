from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PriorityCreate(BaseModel):
    """POST /priorities request body."""

    title: str = Field(min_length=1, max_length=50)

    @field_validator("title")
    @classmethod
    def _strip_title(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("title must not be empty")
        return stripped


class PriorityUpdate(BaseModel):
    """PATCH /priorities/{id} request body - partial update."""

    title: str | None = Field(default=None, min_length=1, max_length=50)

    @field_validator("title")
    @classmethod
    def _strip_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("title must not be empty")
        return stripped


class PriorityResponse(BaseModel):
    """Priority representation returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    created_at: datetime
    updated_at: datetime
