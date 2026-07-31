from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class LocationCreate(BaseModel):
    """POST /locations request body."""

    title: str = Field(min_length=1, max_length=100)

    @field_validator("title")
    @classmethod
    def _strip_title(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("title must not be empty")
        return stripped


class LocationUpdate(BaseModel):
    """PATCH /locations/{id} request body - partial update.

    Setting is_active=False is how a location is retired ("deactivated")
    without deleting it - there is no DELETE endpoint for locations.
    """

    title: str | None = Field(default=None, min_length=1, max_length=100)
    is_active: bool | None = None

    @field_validator("title")
    @classmethod
    def _strip_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("title must not be empty")
        return stripped


class LocationResponse(BaseModel):
    """Location representation returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
