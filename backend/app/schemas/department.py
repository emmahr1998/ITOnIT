from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.types import UTCDatetime


class DepartmentCreate(BaseModel):
    """POST /departments request body."""

    title: str = Field(min_length=1, max_length=100)

    @field_validator("title")
    @classmethod
    def _strip_title(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("title must not be empty")
        return stripped


class DepartmentUpdate(BaseModel):
    """PATCH /departments/{id} request body - partial update."""

    title: str | None = Field(default=None, min_length=1, max_length=100)

    @field_validator("title")
    @classmethod
    def _strip_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("title must not be empty")
        return stripped


class DepartmentResponse(BaseModel):
    """Department representation returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    created_at: UTCDatetime
    updated_at: UTCDatetime
