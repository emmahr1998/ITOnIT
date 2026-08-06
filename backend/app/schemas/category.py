from pydantic import BaseModel, ConfigDict, Field, field_validator


class CategoryBase(BaseModel):
    """Shared validation for category writes: trimmed, non-empty, DB-length-bound."""

    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=255)

    @field_validator("name")
    @classmethod
    def _strip_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("name must not be empty")
        return stripped

    @field_validator("description")
    @classmethod
    def _strip_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None


class CategoryCreate(CategoryBase):
    """POST /categories request body."""


class CategoryUpdate(CategoryBase):
    """PUT /categories/{id} request body - full replacement, not a partial patch."""


class CategoryResponse(BaseModel):
    """Category representation returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
