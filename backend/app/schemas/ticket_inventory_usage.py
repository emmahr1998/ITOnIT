from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import TicketInventoryUsageStatus
from app.schemas.inventory_item import InventoryItemResponse
from app.schemas.ticket import TicketUserSummary
from app.schemas.types import UTCDatetime


class TicketInventoryReserve(BaseModel):
    """POST /tickets/{id}/inventory request body.

    quantity defaults to 1 - the only legal value for a SERIALIZED item
    (enforced in TicketInventoryService, not here, since that depends on
    the referenced item's tracking_type). For a BULK item this is how many
    units to reserve; if the same item is already reserved on this ticket,
    the request adds to the existing reservation's quantity instead of
    creating a second row (see TicketInventoryService.reserve).
    """

    inventory_item_id: int
    quantity: int = Field(default=1, ge=1)


class TicketInventoryUsageResponse(BaseModel):
    """TicketInventoryUsage representation returned by the API - the
    inventory item is nested in full (asset tag, name, category, tracking
    type, current holder, ...) since the Ticket Detail page's Inventory
    section needs all of it and no separate lookup is worth adding."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    ticket_id: int
    inventory_item: InventoryItemResponse
    quantity: int
    status: TicketInventoryUsageStatus
    selected_by: TicketUserSummary
    created_at: UTCDatetime
    updated_at: UTCDatetime
