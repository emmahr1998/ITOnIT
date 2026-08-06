from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.dependencies.auth import get_current_active_user
from app.dependencies.database import get_db
from app.models.ticket import Ticket
from app.models.user import User
from app.repositories.ticket import TicketRepository
from app.services.ticket_service import TicketNotFoundError, TicketPermissionError, TicketService


def get_ticket_repository(db: Session = Depends(get_db)) -> TicketRepository:
    return TicketRepository(db)


def get_ticket_service(db: Session = Depends(get_db)) -> TicketService:
    return TicketService(db)


def get_viewable_ticket(
    ticket_id: int,
    ticket_service: TicketService = Depends(get_ticket_service),
    current_user: User = Depends(get_current_active_user),
) -> Ticket:
    """Resolve a ticket the current user is allowed to view, or raise 404/403.

    Shared by every /tickets/{ticket_id}/... sub-resource route (comments,
    history) so the ownership check TicketService already implements isn't
    duplicated at each call site. No role gate here beyond "authenticated":
    ownership (not role) is what actually restricts access to a ticket.
    """
    try:
        return ticket_service.get_ticket(current_user, ticket_id)
    except TicketNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ticket not found") from exc
    except TicketPermissionError as exc:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "You do not have access to this ticket"
        ) from exc
