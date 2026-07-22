from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.dependencies import get_ticket_service, require_roles
from app.models.enums import TicketPriority, TicketStatus
from app.models.user import User
from app.schemas.ticket import (
    TicketAssign,
    TicketCreate,
    TicketResponse,
    TicketStatusUpdate,
    TicketUpdate,
)
from app.services.ticket_service import (
    InvalidStatusTransitionError,
    InvalidTechnicianAssignmentError,
    TicketCategoryNotFoundError,
    TicketNotEditableError,
    TicketNotFoundError,
    TicketPermissionError,
    TicketService,
)

router = APIRouter(prefix="/tickets", tags=["Tickets"])

_CREATE_ROLES = ("Employee", "Manager", "Administrator")
_VIEW_ROLES = ("Employee", "Technician", "Manager", "Administrator")
_DELETE_ROLES = ("Manager", "Administrator")
_ASSIGN_ROLES = ("Manager", "Administrator")
_STATUS_ROLES = ("Technician", "Manager", "Administrator")


@router.get("", response_model=list[TicketResponse])
def list_tickets(
    ticket_status: TicketStatus | None = Query(default=None, alias="status"),
    priority: TicketPriority | None = Query(default=None),
    category_id: int | None = Query(default=None, alias="category"),
    created_by: int | None = Query(default=None),
    assigned_to: int | None = Query(default=None),
    ticket_service: TicketService = Depends(get_ticket_service),
    current_user: User = Depends(require_roles(*_VIEW_ROLES)),
) -> list[TicketResponse]:
    """Employees automatically see only their own tickets; technicians only
    their assigned tickets. Managers/Administrators see everything."""
    tickets = ticket_service.list_tickets(
        current_user,
        status=ticket_status,
        priority=priority,
        category_id=category_id,
        created_by=created_by,
        assigned_to=assigned_to,
    )
    return [TicketResponse.model_validate(ticket) for ticket in tickets]


@router.get("/{ticket_id}", response_model=TicketResponse)
def get_ticket(
    ticket_id: int,
    ticket_service: TicketService = Depends(get_ticket_service),
    current_user: User = Depends(require_roles(*_VIEW_ROLES)),
) -> TicketResponse:
    try:
        ticket = ticket_service.get_ticket(current_user, ticket_id)
    except TicketNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ticket not found") from exc
    except TicketPermissionError as exc:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "You do not have access to this ticket"
        ) from exc
    return TicketResponse.model_validate(ticket)


@router.post("", response_model=TicketResponse, status_code=status.HTTP_201_CREATED)
def create_ticket(
    payload: TicketCreate,
    ticket_service: TicketService = Depends(get_ticket_service),
    current_user: User = Depends(require_roles(*_CREATE_ROLES)),
) -> TicketResponse:
    try:
        ticket = ticket_service.create_ticket(current_user, payload)
    except TicketCategoryNotFoundError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Category not found") from exc
    return TicketResponse.model_validate(ticket)


@router.put("/{ticket_id}", response_model=TicketResponse)
def update_ticket(
    ticket_id: int,
    payload: TicketUpdate,
    ticket_service: TicketService = Depends(get_ticket_service),
    current_user: User = Depends(require_roles(*_VIEW_ROLES)),
) -> TicketResponse:
    try:
        ticket = ticket_service.update_ticket(current_user, ticket_id, payload)
    except TicketNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ticket not found") from exc
    except TicketPermissionError as exc:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "You do not have access to this ticket"
        ) from exc
    except TicketNotEditableError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "This ticket can no longer be edited once work has started",
        ) from exc
    except TicketCategoryNotFoundError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Category not found") from exc
    return TicketResponse.model_validate(ticket)


@router.delete("/{ticket_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_ticket(
    ticket_id: int,
    ticket_service: TicketService = Depends(get_ticket_service),
    _current_user: User = Depends(require_roles(*_DELETE_ROLES)),
) -> None:
    try:
        ticket_service.delete_ticket(ticket_id)
    except TicketNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ticket not found") from exc


@router.patch("/{ticket_id}/assign", response_model=TicketResponse)
def assign_technician(
    ticket_id: int,
    payload: TicketAssign,
    ticket_service: TicketService = Depends(get_ticket_service),
    _current_user: User = Depends(require_roles(*_ASSIGN_ROLES)),
) -> TicketResponse:
    try:
        ticket = ticket_service.assign_technician(ticket_id, payload.technician_id)
    except TicketNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ticket not found") from exc
    except InvalidTechnicianAssignmentError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return TicketResponse.model_validate(ticket)


@router.patch("/{ticket_id}/status", response_model=TicketResponse)
def change_status(
    ticket_id: int,
    payload: TicketStatusUpdate,
    ticket_service: TicketService = Depends(get_ticket_service),
    current_user: User = Depends(require_roles(*_STATUS_ROLES)),
) -> TicketResponse:
    try:
        ticket = ticket_service.change_status(current_user, ticket_id, payload.status)
    except TicketNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ticket not found") from exc
    except TicketPermissionError as exc:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "You do not have access to this ticket"
        ) from exc
    except InvalidStatusTransitionError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    return TicketResponse.model_validate(ticket)
