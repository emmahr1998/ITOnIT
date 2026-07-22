from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.enums import TicketPriority, TicketStatus
from app.models.ticket import Ticket
from app.repositories.base import BaseRepository

_EAGER_OPTIONS = (
    selectinload(Ticket.category),
    selectinload(Ticket.created_by),
    selectinload(Ticket.assigned_technician),
)


class TicketRepository(BaseRepository[Ticket]):
    """Ticket persistence: filtered listing and ticket-number sequencing."""

    def __init__(self, db: Session) -> None:
        super().__init__(db, Ticket)

    def get_by_id(self, id_: int) -> Ticket | None:
        """Overrides BaseRepository.get_by_id to eager-load the relationships
        every TicketResponse needs, avoiding an N+1 query per nested field."""
        return self.db.scalar(select(Ticket).where(Ticket.id == id_).options(*_EAGER_OPTIONS))

    def get_with_filters(
        self,
        *,
        status: TicketStatus | None = None,
        priority: TicketPriority | None = None,
        category_id: int | None = None,
        created_by_user_id: int | None = None,
        assigned_technician_id: int | None = None,
    ) -> list[Ticket]:
        """One filter method covers every caller: Manager/Admin's free filtering
        and Employee/Technician's forced ownership scope are both just filters."""
        stmt = select(Ticket).options(*_EAGER_OPTIONS)
        if status is not None:
            stmt = stmt.where(Ticket.status == status)
        if priority is not None:
            stmt = stmt.where(Ticket.priority == priority)
        if category_id is not None:
            stmt = stmt.where(Ticket.category_id == category_id)
        if created_by_user_id is not None:
            stmt = stmt.where(Ticket.created_by_user_id == created_by_user_id)
        if assigned_technician_id is not None:
            stmt = stmt.where(Ticket.assigned_technician_id == assigned_technician_id)
        return list(self.db.scalars(stmt).all())

    def count_for_year(self, year: int) -> int:
        """Used to generate the next sequential ticket_number for a given year."""
        return (
            self.db.scalar(
                select(func.count())
                .select_from(Ticket)
                .where(Ticket.ticket_number.like(f"IT-{year}-%"))
            )
            or 0
        )
