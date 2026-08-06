from sqlalchemy.orm import Session

from app.models.ticket_history import TicketHistory
from app.models.user import User
from app.repositories.history import HistoryRepository

_MAX_VALUE_LENGTH = 255  # matches TicketHistory.old_value/new_value column width


class HistoryService:
    """Owns TicketHistory writes - the one place every ticket/comment mutation
    records an audit entry, so this logic is never duplicated per call site.

    Deliberately does not commit: recording history is always one step
    inside a larger operation (creating a ticket, changing its status,
    adding a comment...) owned by whichever service orchestrates that
    operation. This only flushes (via HistoryRepository/BaseRepository),
    matching the project convention that repositories persist and the
    orchestrating service owns the transaction boundary.

    company_id always comes from the authenticated caller (see
    app.dependencies.auth.get_current_company_id), never from client input -
    it is denormalized from the parent ticket, same as on the model itself.
    """

    def __init__(
        self,
        db: Session,
        company_id: int,
        history_repository: HistoryRepository | None = None,
    ) -> None:
        self._company_id = company_id
        self._history_repository = (
            history_repository
            if history_repository is not None
            else HistoryRepository(db, company_id)
        )

    def record(
        self,
        ticket_id: int,
        changed_by: User,
        field_name: str,
        old_value: str | None,
        new_value: str | None,
    ) -> TicketHistory:
        entry = TicketHistory(
            company_id=self._company_id,
            ticket_id=ticket_id,
            changed_by_user_id=changed_by.id,
            field_name=field_name,
            old_value=self._truncate(old_value),
            new_value=self._truncate(new_value),
        )
        # Set the relationship directly (not just the FK) - see
        # TicketService's create/assign fixes for why: avoids depending on
        # lazy-load timing, and this entry is stored as-is by fakes in tests.
        entry.changed_by = changed_by
        return self._history_repository.create(entry)

    def list_for_ticket(self, ticket_id: int) -> list[TicketHistory]:
        return self._history_repository.list_for_ticket(ticket_id)

    @staticmethod
    def _truncate(value: str | None) -> str | None:
        if value is None:
            return None
        return value[:_MAX_VALUE_LENGTH]
