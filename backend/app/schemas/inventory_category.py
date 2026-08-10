from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class InventoryCategoryCreate(BaseModel):
    """POST /inventory-categories request body."""

    name: str = Field(min_length=1, max_length=100)

    @field_validator("name")
    @classmethod
    def _strip_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("name must not be empty")
        return stripped


class InventoryCategoryUpdate(BaseModel):
    """PATCH /inventory-categories/{id} request body - partial update.

    Setting is_active=False is how a category is retired ("deactivated")
    without deleting it - there is no DELETE endpoint. A deactivated
    category may no longer be assigned to new/reassigned inventory items,
    though items that already reference one keep a valid reference.
    """

    name: str | None = Field(default=None, min_length=1, max_length=100)
    is_active: bool | None = None

    @field_validator("name")
    @classmethod
    def _strip_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("name must not be empty")
        return stripped


class InventoryCategoryResponse(BaseModel):
    """InventoryCategory representation returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    is_active: bool
    created_at: datetime
