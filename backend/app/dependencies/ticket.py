from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.dependencies.auth import get_current_active_user, get_current_company_id
from app.dependencies.database import get_db
from app.models.ticket import Ticket
from app.models.user import User
from app.repositories.ticket import TicketRepository
from app.services.ticket_service import TicketNotFoundError, TicketPermissionError, TicketService


def get_ticket_repository(
    db: Session = Depends(get_db), company_id: int = Depends(get_current_company_id)
) -> TicketRepository:
    return TicketRepository(db, company_id)


def get_ticket_service(
    db: Session = Depends(get_db), company_id: int = Depends(get_current_company_id)
) -> TicketService:
    return TicketService(db, company_id)


def get_viewable_ticket(
    ticket_id: int,
    ticket_service: TicketService = Depends(get_ticket_service),
    current_user: User = Depends(get_current_active_user),
) -> Ticket:
    """Resolve a ticket the current user is allowed to view, or raise 404/403.

    Shared by every /tickets/{ticket_id}/... sub-resource route (comments,
    history) so the ownership check TicketService already implements isn't
    duplicated at each call site. No role gate here beyond "authenticated":
    ownership (not role) is what actually restricts access to a ticket -
    company scoping happens one level below, inside ticket_service itself
    (constructed via get_ticket_service, already scoped to current_user's
    company), so a cross-company ticket id looks identical to a
    non-existent one here.
    """
    try:
        return ticket_service.get_ticket(current_user, ticket_id)
    except TicketNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ticket not found") from exc
    except TicketPermissionError as exc:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "You do not have access to this ticket"
        ) from exc
