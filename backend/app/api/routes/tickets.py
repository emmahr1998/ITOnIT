from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.dependencies import (
    get_comment_service,
    get_history_service,
    get_ticket_service,
    get_viewable_ticket,
    require_roles,
)
from app.models.enums import TicketStatus
from app.models.ticket import Ticket
from app.models.user import User
from app.schemas.comment import CommentCreate, CommentResponse, CommentUpdate
from app.schemas.history import TicketHistoryResponse
from app.schemas.response import DataResponse
from app.schemas.ticket import (
    TicketAssign,
    TicketNewCreate,
    TicketPatch,
    TicketResponse,
    TicketStatusUpdate,
)
from app.services.comment_service import (
    CommentNotFoundError,
    CommentPermissionError,
    CommentService,
)
from app.services.history_service import HistoryService
from app.services.ticket_service import (
    InvalidStatusTransitionError,
    InvalidTechnicianAssignmentError,
    TicketCategoryNotFoundError,
    TicketNotEditableError,
    TicketNotFoundError,
    TicketPermissionError,
    TicketPriorityNotFoundError,
    TicketRequesterNotFoundError,
    TicketService,
)

router = APIRouter(prefix="/tickets", tags=["Tickets"])

# Collection endpoints that must live at exactly /ticket-new and
# /all-tickets (not nested under /tickets) - see flat_router below.
flat_router = APIRouter(tags=["Tickets"])

_CREATE_ROLES = ("Employee", "Manager", "Administrator")
_VIEW_ROLES = ("Employee", "Technician", "Manager", "Administrator")
_DELETE_ROLES = ("Manager", "Administrator")
_ASSIGN_ROLES = ("Manager", "Administrator")
_STATUS_ROLES = ("Technician", "Manager", "Administrator")


@router.get("/{ticket_id}", response_model=TicketResponse)
def get_ticket(ticket: Ticket = Depends(get_viewable_ticket)) -> TicketResponse:
    return TicketResponse.model_validate(ticket)


@router.patch("/{ticket_id}", response_model=DataResponse[TicketResponse])
def patch_ticket(
    ticket_id: int,
    payload: TicketPatch,
    ticket_service: TicketService = Depends(get_ticket_service),
    current_user: User = Depends(require_roles(*_VIEW_ROLES)),
) -> DataResponse[TicketResponse]:
    """Partial update of title/description/location/category_id/priority_id.

    Assignment, status, requester, and timestamps stay out of reach here -
    they're each owned by their own endpoint/mechanism.
    """
    try:
        ticket = ticket_service.patch_ticket(current_user, ticket_id, payload)
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
    except TicketPriorityNotFoundError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Priority not found") from exc
    return DataResponse(data=TicketResponse.model_validate(ticket), msg="Ticket updated successfully")


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
    current_user: User = Depends(require_roles(*_ASSIGN_ROLES)),
) -> TicketResponse:
    try:
        ticket = ticket_service.assign_technician(current_user, ticket_id, payload.technician_id)
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


# ---------------------------------------------------------------------------
# Comments - nested under a ticket. get_viewable_ticket already applies the
# exact same view-ownership rule the Comment Rules table requires (Employees
# on their own tickets, Technicians on assigned tickets, Managers/Admins
# everywhere), so no separate role check is needed to reach these routes.
# ---------------------------------------------------------------------------


@router.get("/{ticket_id}/comments", response_model=list[CommentResponse])
def list_comments(
    ticket: Ticket = Depends(get_viewable_ticket),
    comment_service: CommentService = Depends(get_comment_service),
) -> list[CommentResponse]:
    comments = comment_service.list_comments(ticket.id)
    return [CommentResponse.model_validate(comment) for comment in comments]


@router.post(
    "/{ticket_id}/comments", response_model=CommentResponse, status_code=status.HTTP_201_CREATED
)
def add_comment(
    payload: CommentCreate,
    ticket: Ticket = Depends(get_viewable_ticket),
    comment_service: CommentService = Depends(get_comment_service),
    current_user: User = Depends(require_roles(*_VIEW_ROLES)),
) -> CommentResponse:
    comment = comment_service.add_comment(current_user, ticket.id, payload.content)
    return CommentResponse.model_validate(comment)


@router.put("/{ticket_id}/comments/{comment_id}", response_model=CommentResponse)
def update_comment(
    comment_id: int,
    payload: CommentUpdate,
    ticket: Ticket = Depends(get_viewable_ticket),
    comment_service: CommentService = Depends(get_comment_service),
    current_user: User = Depends(require_roles(*_VIEW_ROLES)),
) -> CommentResponse:
    try:
        comment = comment_service.update_comment(
            current_user, ticket.id, comment_id, payload.content
        )
    except CommentNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Comment not found") from exc
    except CommentPermissionError as exc:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "You can only edit your own comments"
        ) from exc
    return CommentResponse.model_validate(comment)


@router.delete("/{ticket_id}/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_comment(
    comment_id: int,
    ticket: Ticket = Depends(get_viewable_ticket),
    comment_service: CommentService = Depends(get_comment_service),
    current_user: User = Depends(require_roles(*_VIEW_ROLES)),
) -> None:
    try:
        comment_service.delete_comment(current_user, ticket.id, comment_id)
    except CommentNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Comment not found") from exc
    except CommentPermissionError as exc:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "You can only delete your own comments"
        ) from exc


# ---------------------------------------------------------------------------
# History - read-only, same view-ownership gate as comments.
# ---------------------------------------------------------------------------


@router.get("/{ticket_id}/history", response_model=list[TicketHistoryResponse])
def get_ticket_history(
    ticket: Ticket = Depends(get_viewable_ticket),
    history_service: HistoryService = Depends(get_history_service),
) -> list[TicketHistoryResponse]:
    entries = history_service.list_for_ticket(ticket.id)
    return [TicketHistoryResponse.model_validate(entry) for entry in entries]


# ---------------------------------------------------------------------------
# Flat collection endpoints - must live at exactly /ticket-new and
# /all-tickets, not nested under /tickets.
# ---------------------------------------------------------------------------


@flat_router.post(
    "/ticket-new", response_model=DataResponse[TicketResponse], status_code=status.HTTP_201_CREATED
)
def create_ticket_new(
    payload: TicketNewCreate,
    ticket_service: TicketService = Depends(get_ticket_service),
    current_user: User = Depends(require_roles(*_CREATE_ROLES)),
) -> DataResponse[TicketResponse]:
    """The requester is always the caller, unless a Manager/Administrator
    explicitly sets requester_user_id to create the ticket on someone
    else's behalf.
    """
    try:
        ticket = ticket_service.create_ticket_new(current_user, payload)
    except TicketCategoryNotFoundError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Category not found") from exc
    except TicketPriorityNotFoundError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Priority not found") from exc
    except TicketRequesterNotFoundError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Requester not found") from exc
    except TicketPermissionError as exc:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Only a Manager or Administrator may create a ticket for another user",
        ) from exc
    return DataResponse(data=TicketResponse.model_validate(ticket), msg="Ticket created successfully")


@flat_router.get("/all-tickets", response_model=DataResponse[list[TicketResponse]])
def get_all_tickets(
    ticket_status: TicketStatus | None = Query(default=None, alias="status"),
    priority_id: int | None = Query(default=None),
    category_id: int | None = Query(default=None),
    department_id: int | None = Query(default=None),
    requester_id: int | None = Query(default=None, alias="requester"),
    assigned_to: int | None = Query(default=None),
    search: str | None = Query(default=None),
    sort_by: str = Query(default="created_at"),
    sort_dir: str = Query(default="desc"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    ticket_service: TicketService = Depends(get_ticket_service),
    current_user: User = Depends(require_roles(*_VIEW_ROLES)),
) -> DataResponse[list[TicketResponse]]:
    """Same visibility rules as GET /tickets (Employee own, Technician
    assigned, Manager/Admin all), plus pagination, sorting, and the full
    filter/search set.
    """
    tickets = ticket_service.list_tickets(
        current_user,
        status=ticket_status,
        priority_id=priority_id,
        category_id=category_id,
        department_id=department_id,
        created_by=requester_id,
        assigned_to=assigned_to,
        search=search,
        sort_by=sort_by,
        sort_dir=sort_dir,
        skip=skip,
        limit=limit,
    )
    return DataResponse(
        data=[TicketResponse.model_validate(ticket) for ticket in tickets],
        msg=f"Fetched {len(tickets)} tickets",
    )
