from pydantic import BaseModel, ConfigDict

from app.models.enums import InventoryTransactionType
from app.schemas.ticket import TicketUserSummary
from app.schemas.types import UTCDatetime


class InventoryTransactionItemSummary(BaseModel):
    """Minimal item info nested inside a transaction response - avoids
    pulling in the full InventoryItemResponse (category/location/holder/
    every metadata field) when only "which item was this" is needed."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    asset_tag: str | None


class InventoryTransactionTicketSummary(BaseModel):
    """Minimal ticket info nested inside a transaction response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    ticket_number: str


class InventoryTransactionResponse(BaseModel):
    """InventoryTransaction representation returned by the API - read-only,
    there is no corresponding create/update schema since every row is
    written internally by services, never directly by a client request."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    inventory_item: InventoryTransactionItemSummary
    ticket: InventoryTransactionTicketSummary | None
    performed_by: TicketUserSummary
    transaction_type: InventoryTransactionType
    quantity_delta: int | None
    field_name: str | None
    old_value: str | None
    new_value: str | None
    notes: str | None
    created_at: UTCDatetime
