from pydantic import BaseModel, ConfigDict, Field

from app.schemas.ticket import TicketUserSummary
from app.schemas.types import UTCDatetime


class TicketHistoryResponse(BaseModel):
    """A single audit entry, returned by GET /tickets/{id}/history.

    The underlying model column is field_name, not action - aliased here
    rather than renaming the column, since the model is not being modified.
    """

    model_config = ConfigDict(from_attributes=True)

    action: str = Field(validation_alias="field_name")
    performed_by: TicketUserSummary = Field(validation_alias="changed_by")
    old_value: str | None = None
    new_value: str | None = None
    timestamp: UTCDatetime = Field(validation_alias="created_at")
