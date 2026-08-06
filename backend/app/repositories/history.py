from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.ticket_history import TicketHistory
from app.repositories.base import BaseRepository


class HistoryRepository(BaseRepository[TicketHistory]):
    """History persistence: creation (via BaseRepository.create) and
    chronological listing for a ticket, with the author eager-loaded."""

    def __init__(self, db: Session) -> None:
        super().__init__(db, TicketHistory)

    def list_for_ticket(self, ticket_id: int) -> list[TicketHistory]:
        return list(
            self.db.scalars(
                select(TicketHistory)
                .where(TicketHistory.ticket_id == ticket_id)
                .options(selectinload(TicketHistory.changed_by))
                .order_by(TicketHistory.created_at.asc(), TicketHistory.id.asc())
            ).all()
        )
