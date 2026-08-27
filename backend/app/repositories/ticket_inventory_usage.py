from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.enums import TicketInventoryUsageStatus
from app.models.inventory_item import InventoryItem
from app.models.ticket import Ticket
from app.models.ticket_inventory_usage import TicketInventoryUsage
from app.repositories.base import CompanyScopedRepository

_EAGER_OPTIONS = (
    selectinload(TicketInventoryUsage.inventory_item).selectinload(
        InventoryItem.inventory_category
    ),
    selectinload(TicketInventoryUsage.inventory_item).selectinload(InventoryItem.current_location),
    selectinload(TicketInventoryUsage.inventory_item).selectinload(InventoryItem.current_holder),
    selectinload(TicketInventoryUsage.selected_by),
)


class TicketInventoryUsageRepository(CompanyScopedRepository[TicketInventoryUsage]):
    """TicketInventoryUsage persistence: per-ticket listing plus the
    (ticket_id, inventory_item_id) lookup TicketInventoryService needs to
    decide whether a reservation merges into an existing row or creates a
    new one. Company-scoped - see CompanyScopedRepository."""

    def __init__(self, db: Session, company_id: int) -> None:
        super().__init__(db, TicketInventoryUsage, company_id)

    def get_by_id(self, id_: int) -> TicketInventoryUsage | None:
        """Overrides CompanyScopedRepository.get_by_id to eager-load the
        nested inventory item (and its own category/location/holder) plus
        selected_by, avoiding an N+1 query when the usage row is serialized."""
        return self.db.scalar(
            select(TicketInventoryUsage)
            .where(
                TicketInventoryUsage.id == id_,
                TicketInventoryUsage.company_id == self.company_id,
            )
            .options(*_EAGER_OPTIONS)
        )

    def list_for_ticket(self, ticket_id: int) -> list[TicketInventoryUsage]:
        return list(
            self.db.scalars(
                select(TicketInventoryUsage)
                .where(
                    TicketInventoryUsage.ticket_id == ticket_id,
                    TicketInventoryUsage.company_id == self.company_id,
                )
                .options(*_EAGER_OPTIONS)
                .order_by(TicketInventoryUsage.created_at.asc(), TicketInventoryUsage.id.asc())
            ).all()
        )

    def get_existing(self, ticket_id: int, inventory_item_id: int) -> TicketInventoryUsage | None:
        """The current usage row (if any) for this exact ticket+item pair -
        at most one can exist, per the table's own unique constraint."""
        return self.db.scalar(
            select(TicketInventoryUsage)
            .where(
                TicketInventoryUsage.ticket_id == ticket_id,
                TicketInventoryUsage.inventory_item_id == inventory_item_id,
                TicketInventoryUsage.company_id == self.company_id,
            )
            .options(*_EAGER_OPTIONS)
        )

    def count_reserved_for_technician(self, technician_id: int) -> int:
        """Analytics aggregate: how many currently-RESERVED usage rows
        (reserved item *lines*, not summed quantity - see
        AnalyticsService.get_inventory_analytics's docstring for why) sit
        on tickets assigned to this technician. Both
        TicketInventoryUsage.company_id (denormalized from the ticket, see
        this model's own docstring) and Ticket.company_id are checked
        explicitly - redundant given FK integrity, but matches
        CompanyScopedRepository's documented convention of never relying
        on a join alone for isolation."""
        stmt = (
            select(func.count())
            .select_from(TicketInventoryUsage)
            .join(Ticket, TicketInventoryUsage.ticket_id == Ticket.id)
            .where(
                TicketInventoryUsage.company_id == self.company_id,
                Ticket.company_id == self.company_id,
                TicketInventoryUsage.status == TicketInventoryUsageStatus.RESERVED,
                Ticket.assigned_technician_id == technician_id,
            )
        )
        return self.db.scalar(stmt) or 0
