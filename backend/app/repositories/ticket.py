from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models.enums import TicketStatus
from app.models.ticket import Ticket
from app.models.user import User
from app.repositories.base import BaseRepository

_EAGER_OPTIONS = (
    selectinload(Ticket.category),
    selectinload(Ticket.priority),
    selectinload(Ticket.location),
    selectinload(Ticket.created_by),
    selectinload(Ticket.assigned_technician),
)

_SORTABLE_COLUMNS = {
    "created_at": Ticket.created_at,
    "updated_at": Ticket.updated_at,
    "title": Ticket.title,
    "ticket_number": Ticket.ticket_number,
}


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
        priority_id: int | None = None,
        category_id: int | None = None,
        department_id: int | None = None,
        created_by_user_id: int | None = None,
        assigned_technician_id: int | None = None,
        search: str | None = None,
        sort_by: str = "created_at",
        sort_dir: str = "desc",
        skip: int | None = None,
        limit: int | None = None,
    ) -> list[Ticket]:
        """One filter method covers every caller: Manager/Admin's free filtering
        and Employee/Technician's forced ownership scope are both just filters.

        skip/limit default to None (no pagination applied) so the existing
        GET /tickets caller, which never passes them, keeps returning every
        matching row exactly as before; GET /all-tickets is the caller that
        supplies them.
        """
        stmt = select(Ticket).options(*_EAGER_OPTIONS)
        if department_id is not None:
            stmt = stmt.join(User, Ticket.created_by_user_id == User.id).where(
                User.department_id == department_id
            )
        if status is not None:
            stmt = stmt.where(Ticket.status == status)
        if priority_id is not None:
            stmt = stmt.where(Ticket.priority_id == priority_id)
        if category_id is not None:
            stmt = stmt.where(Ticket.category_id == category_id)
        if created_by_user_id is not None:
            stmt = stmt.where(Ticket.created_by_user_id == created_by_user_id)
        if assigned_technician_id is not None:
            stmt = stmt.where(Ticket.assigned_technician_id == assigned_technician_id)
        if search:
            pattern = f"%{search.strip().lower()}%"
            stmt = stmt.where(
                or_(
                    func.lower(Ticket.title).like(pattern),
                    func.lower(Ticket.description).like(pattern),
                )
            )

        sort_column = _SORTABLE_COLUMNS.get(sort_by, Ticket.created_at)
        stmt = stmt.order_by(sort_column.asc() if sort_dir == "asc" else sort_column.desc())

        if skip is not None:
            stmt = stmt.offset(skip)
        if limit is not None:
            stmt = stmt.limit(limit)
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
