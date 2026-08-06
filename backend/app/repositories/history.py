from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.ticket_history import TicketHistory
from app.repositories.base import CompanyScopedRepository


class HistoryRepository(CompanyScopedRepository[TicketHistory]):
    """History persistence: creation (via BaseRepository.create) and
    chronological listing for a ticket, with the author eager-loaded.
    Company-scoped - see CompanyScopedRepository."""

    def __init__(self, db: Session, company_id: int) -> None:
        super().__init__(db, TicketHistory, company_id)

    def list_for_ticket(self, ticket_id: int) -> list[TicketHistory]:
        return list(
            self.db.scalars(
                select(TicketHistory)
                .where(
                    TicketHistory.ticket_id == ticket_id,
                    TicketHistory.company_id == self.company_id,
                )
                .options(selectinload(TicketHistory.changed_by))
                .order_by(TicketHistory.created_at.asc(), TicketHistory.id.asc())
            ).all()
        )
