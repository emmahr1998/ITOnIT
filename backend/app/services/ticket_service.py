from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.time import utc_now_naive
from app.models.category import Category
from app.models.enums import TicketStatus
from app.models.location import Location
from app.models.priority import Priority
from app.models.ticket import Ticket
from app.models.user import User
from app.repositories.category import CategoryRepository
from app.repositories.location import LocationRepository
from app.repositories.priority import PriorityRepository
from app.repositories.ticket import TicketRepository
from app.repositories.user import UserRepository
from app.schemas.ticket import TicketNewCreate, TicketPatch
from app.services.history_service import HistoryService
from app.services.storage_service import StorageService
from app.services.ticket_inventory_service import TicketInventoryService

TECHNICIAN_ROLE_NAME = "Technician"
_MANAGE_ROLE_NAMES = ("Company Administrator",)

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


class TicketPriorityNotFoundError(Exception):
    """Raised when a ticket create/update references a priority id that does not exist."""


class TicketLocationNotFoundError(Exception):
    """Raised when a ticket create/update references a location id that does not exist
    or is deactivated (is_active=False) - a deactivated location may no longer be
    newly selected, though tickets that already reference it are unaffected.
    """


class TicketRequesterNotFoundError(Exception):
    """Raised when POST /ticket-new's requester_user_id does not reference an existing user."""


class TicketPermissionError(Exception):
    """Raised when the current user has no access to this ticket at all, or -
    for ticket creation - tries to set a requester other than themselves
    without being a Company Administrator.
    """


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


@dataclass(frozen=True)
class TicketOwnershipScope:
    """The one canonical ticket ownership/visibility rule, shared by
    every ticket-scoped read - normal ticket listing (list_tickets) and
    ticket analytics (AnalyticsService) alike. See
    TicketService.resolve_ownership_scope's docstring for the rule itself.

    Each field is None when that dimension is unrestricted - which only
    ever happens for both fields at once (Company Administrator sees the
    whole company); Technician and Employee each always have exactly one
    field set to their own id. is_company_wide is the same check made
    explicit, rather than callers re-deriving "both fields None" for
    themselves at every use site.
    """

    created_by_user_id: int | None
    assigned_technician_id: int | None

    @property
    def is_company_wide(self) -> bool:
        return self.created_by_user_id is None and self.assigned_technician_id is None


class TicketService:
    """Owns ticket business rules: ownership scope, status workflow, assignment validation.

    Also owns the transaction boundary for writes (see CategoryService for
    the same convention - repositories only flush, never commit).

    company_id always comes from the authenticated caller (see
    app.dependencies.auth.get_current_company_id), never from client input.
    It scopes every repository this service touches - including the
    internal UserRepository, which is why a technician-assignment or
    requester-override lookup can never resolve to another company's user
    (UserRepository normally defaults to unscoped for auth's benefit - see
    its own docstring - but this service always supplies company_id
    explicitly, so that default never applies here).
    """

    def __init__(
        self,
        db: Session,
        company_id: int,
        ticket_repository: TicketRepository | None = None,
        category_repository: CategoryRepository | None = None,
        priority_repository: PriorityRepository | None = None,
        location_repository: LocationRepository | None = None,
        user_repository: UserRepository | None = None,
        history_service: HistoryService | None = None,
        storage_service: StorageService | None = None,
        ticket_inventory_service: TicketInventoryService | None = None,
    ) -> None:
        self._db = db
        self._company_id = company_id
        self._ticket_repository = (
            ticket_repository if ticket_repository is not None else TicketRepository(db, company_id)
        )
        self._category_repository = (
            category_repository
            if category_repository is not None
            else CategoryRepository(db, company_id)
        )
        self._priority_repository = (
            priority_repository
            if priority_repository is not None
            else PriorityRepository(db, company_id)
        )
        self._location_repository = (
            location_repository
            if location_repository is not None
            else LocationRepository(db, company_id)
        )
        self._user_repository = (
            user_repository if user_repository is not None else UserRepository(db, company_id)
        )
        self._history_service = (
            history_service if history_service is not None else HistoryService(db, company_id)
        )
        self._storage_service = (
            storage_service if storage_service is not None else StorageService()
        )
        self._ticket_inventory_service = (
            ticket_inventory_service
            if ticket_inventory_service is not None
            else TicketInventoryService(db, company_id)
        )

    # ---- ownership -----------------------------------------------------

    @staticmethod
    def _is_manager_or_admin(user: User) -> bool:
        return user.role.name in _MANAGE_ROLE_NAMES

    @staticmethod
    def resolve_ownership_scope(current_user: User) -> TicketOwnershipScope:
        """The one canonical ticket ownership/visibility rule:

        - Company Administrator: all tickets in their company (both
          fields None - no restriction).
        - Technician: only tickets assigned to that technician.
        - Employee: only tickets created by that employee.

        Every ticket-scoped read must call this - never re-derive the
        role check inline - so normal ticket listing and ticket analytics
        can never drift apart on who is allowed to see what.
        """
        if TicketService._is_manager_or_admin(current_user):
            return TicketOwnershipScope(created_by_user_id=None, assigned_technician_id=None)
        if current_user.role.name == TECHNICIAN_ROLE_NAME:
            return TicketOwnershipScope(
                created_by_user_id=None, assigned_technician_id=current_user.id
            )
        return TicketOwnershipScope(
            created_by_user_id=current_user.id, assigned_technician_id=None
        )

    def _ensure_can_view(self, ticket: Ticket, user: User) -> None:
        if self._is_manager_or_admin(user):
            return
        if user.role.name == TECHNICIAN_ROLE_NAME:
            if ticket.assigned_technician_id != user.id:
                raise TicketPermissionError
            return
        if ticket.created_by_user_id != user.id:
            raise TicketPermissionError

    def _get_category_or_raise(self, category_id: int) -> Category:
        category = self._category_repository.get_by_id(category_id)
        if category is None:
            raise TicketCategoryNotFoundError
        return category

    def _get_priority_or_raise(self, priority_id: int) -> Priority:
        priority = self._priority_repository.get_by_id(priority_id)
        if priority is None:
            raise TicketPriorityNotFoundError
        return priority

    def _get_location_or_raise(self, location_id: int) -> Location:
        location = self._location_repository.get_by_id(location_id)
        if location is None or not location.is_active:
            raise TicketLocationNotFoundError
        return location

    # ---- reads -----------------------------------------------------------

    def list_tickets(
        self,
        current_user: User,
        *,
        status: TicketStatus | None = None,
        priority_id: int | None = None,
        category_id: int | None = None,
        department_id: int | None = None,
        created_by: int | None = None,
        assigned_to: int | None = None,
        search: str | None = None,
        sort_by: str = "created_at",
        sort_dir: str = "desc",
        skip: int | None = None,
        limit: int | None = None,
    ) -> list[Ticket]:
        """Backs both GET /tickets (no search/sort/pagination passed) and
        GET /all-tickets (the full filter set) - the ownership scoping
        below applies identically to both.
        """
        scope = self.resolve_ownership_scope(current_user)
        if scope.created_by_user_id is not None:
            created_by = scope.created_by_user_id  # hard scope; overrides any client value
        if scope.assigned_technician_id is not None:
            assigned_to = scope.assigned_technician_id  # hard scope; overrides any client value

        return self._ticket_repository.get_with_filters(
            status=status,
            priority_id=priority_id,
            category_id=category_id,
            department_id=department_id,
            created_by_user_id=created_by,
            assigned_technician_id=assigned_to,
            search=search,
            sort_by=sort_by,
            sort_dir=sort_dir,
            skip=skip,
            limit=limit,
        )

    def get_ticket(self, current_user: User, ticket_id: int) -> Ticket:
        ticket = self._ticket_repository.get_by_id(ticket_id)
        if ticket is None:
            raise TicketNotFoundError
        self._ensure_can_view(ticket, current_user)
        return ticket

    # ---- writes ------------------------------------------------------------

    def _persist_new_ticket(
        self,
        actor: User,
        requester: User,
        *,
        title: str,
        description: str,
        location: Location | None,
        category: Category,
        priority: Priority,
    ) -> Ticket:
        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            ticket = Ticket(
                company_id=self._company_id,
                ticket_number=self._generate_ticket_number(),
                title=title,
                description=description,
                location_id=location.id if location is not None else None,
                status=TicketStatus.NEW,
                priority_id=priority.id,
                category_id=category.id,
                created_by_user_id=requester.id,
                assigned_technician_id=None,
            )
            # Set the relationship objects directly rather than relying on a
            # later lazy-load through the FK - correct immediately, with no
            # dependency on session/refresh timing.
            ticket.category = category
            ticket.priority = priority
            ticket.location = location
            ticket.created_by = requester
            ticket.assigned_technician = None
            try:
                self._ticket_repository.create(ticket)
                self._history_service.record(
                    ticket.id, actor, "ticket_created", None, ticket.ticket_number
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

    def create_ticket_new(self, current_user: User, payload: TicketNewCreate) -> Ticket:
        """POST /ticket-new: same as create_ticket, but a Company
        Administrator may set requester_user_id to create the ticket on
        behalf of someone else. Anyone else supplying a requester_user_id
        other than their own id is rejected outright.
        """
        category = self._get_category_or_raise(payload.category_id)
        priority = self._get_priority_or_raise(payload.priority_id)
        location = (
            self._get_location_or_raise(payload.location_id)
            if payload.location_id is not None
            else None
        )

        requester = current_user
        if (
            payload.requester_user_id is not None
            and payload.requester_user_id != current_user.id
        ):
            if not self._is_manager_or_admin(current_user):
                raise TicketPermissionError
            requester = self._user_repository.get_by_id(payload.requester_user_id)
            if requester is None:
                raise TicketRequesterNotFoundError

        return self._persist_new_ticket(
            current_user,
            requester,
            title=payload.title,
            description=payload.description,
            location=location,
            category=category,
            priority=priority,
        )

    def patch_ticket(self, current_user: User, ticket_id: int, payload: TicketPatch) -> Ticket:
        """PATCH /tickets/{id}: partial update of title/description/location_id/
        category_id/priority_id only. Assignment, status, requester, and
        timestamps are never touched here - each still goes through its own
        dedicated endpoint/mechanism.
        """
        ticket = self.get_ticket(current_user, ticket_id)  # 404 + view-ownership check

        if current_user.role.name == TECHNICIAN_ROLE_NAME:
            pass  # already confirmed assigned to them above
        elif not self._is_manager_or_admin(current_user):
            if ticket.status != TicketStatus.NEW:
                raise TicketNotEditableError

        fields_set = payload.model_fields_set

        if "title" in fields_set and payload.title is not None and ticket.title != payload.title:
            self._history_service.record(
                ticket.id, current_user, "title", ticket.title, payload.title
            )
            ticket.title = payload.title
        if (
            "description" in fields_set
            and payload.description is not None
            and ticket.description != payload.description
        ):
            self._history_service.record(
                ticket.id, current_user, "description", ticket.description, payload.description
            )
            ticket.description = payload.description
        if "location_id" in fields_set and ticket.location_id != payload.location_id:
            location = (
                self._get_location_or_raise(payload.location_id)
                if payload.location_id is not None
                else None
            )
            self._history_service.record(
                ticket.id,
                current_user,
                "location",
                ticket.location.title if ticket.location is not None else None,
                location.title if location is not None else None,
            )
            ticket.location_id = payload.location_id
            ticket.location = location
        if (
            "category_id" in fields_set
            and payload.category_id is not None
            and ticket.category_id != payload.category_id
        ):
            category = self._get_category_or_raise(payload.category_id)
            self._history_service.record(
                ticket.id, current_user, "category", ticket.category.name, category.name
            )
            ticket.category_id = payload.category_id
            ticket.category = category
        if (
            "priority_id" in fields_set
            and payload.priority_id is not None
            and ticket.priority_id != payload.priority_id
        ):
            priority = self._get_priority_or_raise(payload.priority_id)
            self._history_service.record(
                ticket.id, current_user, "priority", ticket.priority.title, priority.title
            )
            ticket.priority_id = payload.priority_id
            ticket.priority = priority

        self._ticket_repository.update(ticket)
        self._db.commit()
        return ticket

    def delete_ticket(self, ticket_id: int, current_user: User) -> None:
        # Role gate (Company Administrator only) is enforced at the route.
        ticket = self._ticket_repository.get_by_id(ticket_id)
        if ticket is None:
            raise TicketNotFoundError

        # Revert any RESERVED/CONSUMED inventory attached to this ticket
        # first, so deleting it never leaves an item permanently stuck
        # RESERVED/IN_USE with no owning ticket - see
        # TicketInventoryService.release_all_for_ticket. current_user (the
        # Company Administrator deleting the ticket) is who Phase 12.1's
        # InventoryTransaction rows for this cleanup attribute the action
        # to - not whoever originally reserved/consumed each item.
        self._ticket_inventory_service.release_all_for_ticket(ticket, current_user)

        # Capture file paths before the cascade delete removes the
        # attachment rows. The DB delete commits first, then physical files
        # are removed - same ordering rationale as
        # AttachmentService.delete_attachment: a failed physical delete
        # leaves a harmless orphaned file rather than a DB row pointing at
        # nothing.
        file_paths = [attachment.file_path for attachment in ticket.attachments]
        self._ticket_repository.delete(ticket)
        self._db.commit()
        for file_path in file_paths:
            self._storage_service.delete(file_path)

    def assign_technician(
        self, current_user: User, ticket_id: int, technician_id: int
    ) -> Ticket:
        # Role gate (Company Administrator only) is enforced at the route.
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
        # Role gate (Technician/Company Administrator, not Employee) is
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
        now = utc_now_naive()
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
