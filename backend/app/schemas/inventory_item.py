from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import InventoryCondition, InventoryStatus, InventoryTrackingType
from app.schemas.inventory_category import InventoryCategoryResponse
from app.schemas.location import LocationResponse


def _strip_or_none(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _strip_required(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise ValueError("must not be empty")
    return stripped


class InventoryHolderSummary(BaseModel):
    """Minimal, safe user info nested inside an inventory item response -
    never password_hash. Same shape/rationale as TicketUserSummary."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    first_name: str
    last_name: str
    email: str


class InventoryItemCreate(BaseModel):
    """POST /inventory-items request body.

    Field-level shape/format only (lengths, non-negativity) is validated
    here. Every cross-field rule that depends on `tracking_type` or on
    other fields' final values (SERIALIZED vs. BULK combinations, date
    ordering) is validated in InventoryItemService against the fully
    assembled item - see its _validate_business_rules - the same two-layer
    split as the database CHECK constraints from Phase 10.1.

    reserved_quantity is deliberately not a field here at all: reservation
    logic doesn't exist yet (Phase 10.4/11), so every item is created with
    reserved_quantity=0, unconditionally, with no client-facing way to set
    it otherwise. tracking_type is not updatable after creation - see
    InventoryItemUpdate.
    """

    inventory_category_id: int
    name: str = Field(min_length=1, max_length=200)
    tracking_type: InventoryTrackingType
    status: InventoryStatus = InventoryStatus.AVAILABLE
    condition: InventoryCondition | None = None
    asset_tag: str | None = Field(default=None, max_length=50)
    manufacturer: str | None = Field(default=None, max_length=100)
    model: str | None = Field(default=None, max_length=100)
    serial_number: str | None = Field(default=None, max_length=100)
    stock_quantity: int | None = Field(default=None, ge=0)
    minimum_stock: int | None = Field(default=None, ge=0)
    current_location_id: int | None = None
    current_holder_user_id: int | None = None
    purchase_date: date | None = None
    warranty_expiration: date | None = None
    supplier: str | None = Field(default=None, max_length=150)
    purchase_cost: Decimal | None = Field(default=None, ge=0)
    invoice_number: str | None = Field(default=None, max_length=100)
    image_path: str | None = Field(default=None, max_length=500)
    notes: str | None = None

    @field_validator("name")
    @classmethod
    def _strip_name(cls, value: str) -> str:
        return _strip_required(value)

    @field_validator(
        "asset_tag",
        "manufacturer",
        "model",
        "serial_number",
        "supplier",
        "invoice_number",
        "image_path",
        "notes",
    )
    @classmethod
    def _strip_optional(cls, value: str | None) -> str | None:
        return _strip_or_none(value)


class InventoryItemUpdate(BaseModel):
    """PATCH /inventory-items/{id} request body - partial update.

    tracking_type is intentionally absent: converting an item between
    SERIALIZED and BULK after creation would require silently rewriting
    asset_tag/stock_quantity/current_holder_user_id/condition to match the
    new type's rules, which is a re-creation in disguise, not an edit -
    retire the item and create a new one instead.

    Nullable columns (current_location_id, current_holder_user_id,
    asset_tag, condition, and the rest of the optional metadata fields) use
    the same "presence in the payload, not the value, decides whether it's
    applied" convention as TicketPatch.location_id - sending null clears
    the field, omitting it leaves it untouched. NOT NULL columns
    (inventory_category_id, name, status, stock_quantity) ignore an
    explicit null since it isn't a valid value for them.
    """

    inventory_category_id: int | None = None
    name: str | None = Field(default=None, min_length=1, max_length=200)
    status: InventoryStatus | None = None
    condition: InventoryCondition | None = None
    asset_tag: str | None = Field(default=None, max_length=50)
    manufacturer: str | None = Field(default=None, max_length=100)
    model: str | None = Field(default=None, max_length=100)
    serial_number: str | None = Field(default=None, max_length=100)
    stock_quantity: int | None = Field(default=None, ge=0)
    minimum_stock: int | None = Field(default=None, ge=0)
    current_location_id: int | None = None
    current_holder_user_id: int | None = None
    purchase_date: date | None = None
    warranty_expiration: date | None = None
    supplier: str | None = Field(default=None, max_length=150)
    purchase_cost: Decimal | None = Field(default=None, ge=0)
    invoice_number: str | None = Field(default=None, max_length=100)
    image_path: str | None = Field(default=None, max_length=500)
    notes: str | None = None

    @field_validator("name")
    @classmethod
    def _strip_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _strip_required(value)

    @field_validator(
        "asset_tag",
        "manufacturer",
        "model",
        "serial_number",
        "supplier",
        "invoice_number",
        "image_path",
        "notes",
    )
    @classmethod
    def _strip_optional(cls, value: str | None) -> str | None:
        return _strip_or_none(value)


class InventoryItemResponse(BaseModel):
    """InventoryItem representation returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    inventory_category: InventoryCategoryResponse
    current_location: LocationResponse | None
    current_holder: InventoryHolderSummary | None
    asset_tag: str | None
    name: str
    manufacturer: str | None
    model: str | None
    serial_number: str | None
    tracking_type: InventoryTrackingType
    status: InventoryStatus
    condition: InventoryCondition | None
    stock_quantity: int
    reserved_quantity: int
    minimum_stock: int | None
    purchase_date: date | None
    warranty_expiration: date | None
    supplier: str | None
    purchase_cost: Decimal | None
    invoice_number: str | None
    image_path: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime
