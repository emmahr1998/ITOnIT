from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.enums import TicketPriority, TicketStatus
from app.models.ticket import Ticket
from app.models.user import User
from app.repositories.category import CategoryRepository
from app.repositories.ticket import TicketRepository
from app.repositories.user import UserRepository
from app.schemas.ticket import TicketCreate, TicketUpdate
from app.services.history_service import HistoryService

TECHNICIAN_ROLE_NAME = "Technician"
_MANAGE_ROLE_NAMES = ("Manager", "Administrator")

# NEW is this system's "OPEN" - the enum (app.models.enums.TicketStatus) has no
# OPEN member. ASSIGNED/WAITING_FOR_EMPLOYEE are given a real, reachable place
# in the graph rather than being unused enum values.
_STATUS_TRANSITIONS: dict[TicketStatus, frozenset[TicketStatus]] = {
    TicketStatus.NEW: frozenset({TicketStatus.ASSIGNED}),
    TicketStatus.ASSIGNED: frozenset({TicketStatus.IN_PROGRESS}),
    TicketStatus.IN_PROGRESS: frozenset(
        {TicketStatus.WAITING_FOR_EMPLOYEE, TicketStatus.RESOLVED}
    ),
    TicketStatus.WAITING_FOR_EMPLOYEE: frozenset({TicketStatus.IN_PROGRESS}),
    TicketStatus.RESOLVED: frozenset({TicketStatus.CLOSED}),
    TicketStatus.CLOSED: frozenset(),
}


class TicketNotFoundError(Exception):
    """Raised when a ticket id does not exist."""


class TicketCategoryNotFoundError(Exception):
    """Raised when a ticket create/update references a category id that does not exist."""


class TicketPermissionError(Exception):
    """Raised when the current user has no access to this ticket at all."""


class TicketNotEditableError(Exception):
    """Raised when an employee tries to edit a ticket whose status is past NEW."""


class InvalidTechnicianAssignmentError(Exception):
    """Raised when an /assign payload does not reference a valid, active technician."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class InvalidStatusTransitionError(Exception):
    """Raised when a /status payload requests a transition not allowed from the current status."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class TicketService:
    """Owns ticket business rules: ownership scope, status workflow, assignment validation.

    Also owns the transaction boundary for writes (see CategoryService for
    the same convention - repositories only flush, never commit).
    """

    def __init__(
        self,
        db: Session,
        ticket_repository: TicketRepository | None = None,
        category_repository: CategoryRepository | None = None,
        user_repository: UserRepository | None = None,
        history_service: HistoryService | None = None,
    ) -> None:
        self._db = db
        self._ticket_repository = (
            ticket_repository if ticket_repository is not None else TicketRepository(db)
        )
        self._category_repository = (
            category_repository if category_repository is not None else CategoryRepository(db)
        )
        self._user_repository = (
            user_repository if user_repository is not None else UserRepository(db)
        )
        self._history_service = (
            history_service if history_service is not None else HistoryService(db)
        )

    # ---- ownership -----------------------------------------------------

    @staticmethod
    def _is_manager_or_admin(user: User) -> bool:
        return user.role.name in _MANAGE_ROLE_NAMES

    def _ensure_can_view(self, ticket: Ticket, user: User) -> None:
        if self._is_manager_or_admin(user):
            return
        if user.role.name == TECHNICIAN_ROLE_NAME:
            if ticket.assigned_technician_id != user.id:
                raise TicketPermissionError
            return
        if ticket.created_by_user_id != user.id:
            raise TicketPermissionError

    # ---- reads -----------------------------------------------------------

    def list_tickets(
        self,
        current_user: User,
        *,
        status: TicketStatus | None = None,
        priority: TicketPriority | None = None,
        category_id: int | None = None,
        created_by: int | None = None,
        assigned_to: int | None = None,
    ) -> list[Ticket]:
        if not self._is_manager_or_admin(current_user):
            if current_user.role.name == TECHNICIAN_ROLE_NAME:
                assigned_to = current_user.id  # hard scope; overrides any client value
            else:
                created_by = current_user.id  # hard scope; overrides any client value

        return self._ticket_repository.get_with_filters(
            status=status,
            priority=priority,
            category_id=category_id,
            created_by_user_id=created_by,
            assigned_technician_id=assigned_to,
        )

    def get_ticket(self, current_user: User, ticket_id: int) -> Ticket:
        ticket = self._ticket_repository.get_by_id(ticket_id)
        if ticket is None:
            raise TicketNotFoundError
        self._ensure_can_view(ticket, current_user)
        return ticket

    # ---- writes ------------------------------------------------------------

    def create_ticket(self, current_user: User, payload: TicketCreate) -> Ticket:
        category = self._category_repository.get_by_id(payload.category_id)
        if category is None:
            raise TicketCategoryNotFoundError

        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            ticket = Ticket(
                ticket_number=self._generate_ticket_number(),
                title=payload.title,
                description=payload.description,
                status=TicketStatus.NEW,
                priority=payload.priority,
                category_id=payload.category_id,
                created_by_user_id=current_user.id,
                assigned_technician_id=None,
            )
            # Set the relationship objects directly rather than relying on a
            # later lazy-load through the FK - correct immediately, with no
            # dependency on session/refresh timing.
            ticket.category = category
            ticket.created_by = current_user
            ticket.assigned_technician = None
            try:
                self._ticket_repository.create(ticket)
                self._history_service.record(
                    ticket.id, current_user, "ticket_created", None, ticket.ticket_number
                )
                self._db.commit()
                return ticket
            except IntegrityError:
                # Defense in depth: a concurrent request could compute the
                # same next sequence number for the same year.
                self._db.rollback()
                if attempt == max_attempts:
                    raise

        raise AssertionError("unreachable: loop always returns or re-raises")

    def update_ticket(self, current_user: User, ticket_id: int, payload: TicketUpdate) -> Ticket:
        ticket = self.get_ticket(current_user, ticket_id)  # 404 + view-ownership check

        if current_user.role.name == TECHNICIAN_ROLE_NAME:
            pass  # already confirmed assigned to them above
        elif not self._is_manager_or_admin(current_user):
            if ticket.status != TicketStatus.NEW:
                raise TicketNotEditableError

        category = self._category_repository.get_by_id(payload.category_id)
        if category is None:
            raise TicketCategoryNotFoundError

        # One history entry per field that actually changed - "Ticket
        # updated"/"Category changed"/"Priority changed" from the business
        # rules are all realized this way, rather than one generic entry
        # that couldn't hold more than one field's old/new value anyway.
        if ticket.title != payload.title:
            self._history_service.record(
                ticket.id, current_user, "title", ticket.title, payload.title
            )
            ticket.title = payload.title
        if ticket.description != payload.description:
            self._history_service.record(
                ticket.id, current_user, "description", ticket.description, payload.description
            )
            ticket.description = payload.description
        if ticket.category_id != payload.category_id:
            self._history_service.record(
                ticket.id, current_user, "category", ticket.category.name, category.name
            )
            ticket.category_id = payload.category_id
        ticket.category = category
        if ticket.priority != payload.priority:
            self._history_service.record(
                ticket.id,
                current_user,
                "priority",
                ticket.priority.value,
                payload.priority.value,
            )
            ticket.priority = payload.priority

        self._ticket_repository.update(ticket)
        self._db.commit()
        return ticket

    def delete_ticket(self, ticket_id: int) -> None:
        # Role gate (Manager/Administrator only) is enforced at the route.
        ticket = self._ticket_repository.get_by_id(ticket_id)
        if ticket is None:
            raise TicketNotFoundError
        self._ticket_repository.delete(ticket)
        self._db.commit()

    def assign_technician(
        self, current_user: User, ticket_id: int, technician_id: int
    ) -> Ticket:
        # Role gate (Manager/Administrator only) is enforced at the route.
        ticket = self._ticket_repository.get_by_id(ticket_id)
        if ticket is None:
            raise TicketNotFoundError
        if ticket.status == TicketStatus.CLOSED:
            raise InvalidTechnicianAssignmentError("Cannot assign a technician to a closed ticket")

        technician = self._user_repository.get_by_id(technician_id)
        if technician is None:
            raise InvalidTechnicianAssignmentError("Technician not found")
        if technician.role.name != TECHNICIAN_ROLE_NAME:
            raise InvalidTechnicianAssignmentError("User is not a technician")
        if not technician.is_active:
            raise InvalidTechnicianAssignmentError("Technician is not active")

        previous_technician_name = (
            f"{ticket.assigned_technician.first_name} {ticket.assigned_technician.last_name}"
            if ticket.assigned_technician is not None
            else None
        )
        ticket.assigned_technician_id = technician.id
        ticket.assigned_technician = technician
        self._history_service.record(
            ticket.id,
            current_user,
            "assigned_technician",
            previous_technician_name,
            f"{technician.first_name} {technician.last_name}",
        )
        if ticket.status == TicketStatus.NEW:
            old_status = ticket.status.value
            ticket.status = TicketStatus.ASSIGNED
            self._history_service.record(
                ticket.id, current_user, "status", old_status, ticket.status.value
            )
        self._ticket_repository.update(ticket)
        self._db.commit()
        return ticket

    def change_status(
        self, current_user: User, ticket_id: int, new_status: TicketStatus
    ) -> Ticket:
        # Role gate (Technician/Manager/Administrator, not Employee) is
        # enforced at the route; the technician-must-be-assigned check below
        # is ownership, not role, so it belongs here.
        ticket = self._ticket_repository.get_by_id(ticket_id)
        if ticket is None:
            raise TicketNotFoundError

        if (
            current_user.role.name == TECHNICIAN_ROLE_NAME
            and ticket.assigned_technician_id != current_user.id
        ):
            raise TicketPermissionError

        if new_status not in _STATUS_TRANSITIONS.get(ticket.status, frozenset()):
            raise InvalidStatusTransitionError(
                f"Cannot transition ticket from {ticket.status.value} to {new_status.value}"
            )

        old_status = ticket.status.value
        ticket.status = new_status
        now = datetime.now(timezone.utc)
        if new_status == TicketStatus.RESOLVED:
            ticket.resolved_at = now
        elif new_status == TicketStatus.CLOSED:
            ticket.closed_at = now

        self._history_service.record(
            ticket.id, current_user, "status", old_status, new_status.value
        )
        self._ticket_repository.update(ticket)
        self._db.commit()
        return ticket

    # ---- internal ------------------------------------------------------------

    def _generate_ticket_number(self) -> str:
        year = datetime.now(timezone.utc).year
        count = self._ticket_repository.count_for_year(year)
        return f"IT-{year}-{count + 1:06d}"
