from collections.abc import Callable, Iterator
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from app.core.security import create_access_token, hash_password
from app.dependencies.attachment import get_attachment_service
from app.dependencies.auth import get_auth_service, get_user_repository
from app.dependencies.category import get_category_service
from app.dependencies.comment import get_comment_service
from app.dependencies.department import get_department_service
from app.dependencies.history import get_history_service
from app.dependencies.location import get_location_service
from app.dependencies.priority import get_priority_service
from app.dependencies.ticket import get_ticket_service
from app.dependencies.user import get_user_service
from app.main import app
from app.models.attachment import Attachment
from app.models.category import Category
from app.models.comment import Comment
from app.models.department import Department
from app.models.enums import TicketStatus
from app.models.location import Location
from app.models.priority import Priority
from app.models.role import Role
from app.models.ticket import Ticket
from app.models.ticket_history import TicketHistory
from app.models.user import User
from app.services.attachment_service import AttachmentService
from app.services.auth_service import AuthService
from app.services.category_service import CategoryService
from app.services.comment_service import CommentService
from app.services.department_service import DepartmentService
from app.services.history_service import HistoryService
from app.services.location_service import LocationService
from app.services.priority_service import PriorityService
from app.services.ticket_service import TicketService
from app.services.user_service import UserService

ADMIN_PASSWORD = "CorrectHorseBattery1!"
INACTIVE_PASSWORD = "SomePassword1!"
EMPLOYEE_PASSWORD = "EmployeePass1!"
TECHNICIAN_PASSWORD = "TechnicianPass1!"
MANAGER_PASSWORD = "ManagerPass1!"
EMPLOYEE_2_PASSWORD = "EmployeeTwoPass1!"
TECHNICIAN_2_PASSWORD = "TechnicianTwoPass1!"


class FakeUserRepository:
    """In-memory stand-in for UserRepository.

    Auth/user-management tests must not touch the real SQL-Server-only
    database, and the production models aren't SQLite-compatible enough to
    fake with an in-memory engine. Instead, AuthService/UserService and the
    auth dependencies accept a repository object structurally (same method
    names/signatures as UserRepository), so this plain Python class -
    backed by a dict of plain (unsaved) User/Role ORM instances -
    substitutes for it without ever creating an engine or session.
    """

    def __init__(self, users: list[User]) -> None:
        self._by_id = {user.id: user for user in users}
        self._next_id = max(self._by_id, default=0) + 1

    def _reindex(self, obj: User) -> None:
        self._by_id[obj.id] = obj

    def get_by_id(self, id_: int) -> User | None:
        return self._by_id.get(id_)

    def get_all(self) -> list[User]:
        return list(self._by_id.values())

    def get_by_email(self, email: str) -> User | None:
        target = email.strip().lower()
        return next((u for u in self._by_id.values() if u.email.lower() == target), None)

    def get_by_username(self, username: str) -> User | None:
        target = username.strip().lower()
        return next((u for u in self._by_id.values() if u.username.lower() == target), None)

    def get_by_username_or_email(self, identifier: str) -> User | None:
        return self.get_by_username(identifier) or self.get_by_email(identifier)

    def _filtered(
        self,
        *,
        role_id: int | None = None,
        department_id: int | None = None,
        is_active: bool | None = None,
        search: str | None = None,
    ) -> list[User]:
        results = list(self._by_id.values())
        if role_id is not None:
            results = [u for u in results if u.role_id == role_id]
        if department_id is not None:
            results = [u for u in results if u.department_id == department_id]
        if is_active is not None:
            results = [u for u in results if u.is_active == is_active]
        if search:
            needle = search.strip().lower()
            results = [
                u
                for u in results
                if needle in u.username.lower()
                or needle in u.first_name.lower()
                or needle in u.last_name.lower()
                or needle in u.email.lower()
            ]
        return sorted(results, key=lambda u: u.id)

    def get_with_filters(
        self,
        *,
        role_id: int | None = None,
        department_id: int | None = None,
        is_active: bool | None = None,
        search: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[User]:
        results = self._filtered(
            role_id=role_id, department_id=department_id, is_active=is_active, search=search
        )
        return results[skip : skip + limit]

    def count_with_filters(
        self,
        *,
        role_id: int | None = None,
        department_id: int | None = None,
        is_active: bool | None = None,
        search: str | None = None,
    ) -> int:
        return len(
            self._filtered(
                role_id=role_id, department_id=department_id, is_active=is_active, search=search
            )
        )

    def create(self, obj: User) -> User:
        obj.id = self._next_id
        self._next_id += 1
        now = datetime.now(timezone.utc)
        obj.created_at = now
        obj.updated_at = now
        self._reindex(obj)
        return obj

    def update(self, obj: User) -> User:
        obj.updated_at = datetime.now(timezone.utc)
        self._reindex(obj)
        return obj


class FakeRoleRepository:
    """In-memory stand-in for RoleRepository. Same rationale as FakeUserRepository."""

    def __init__(self, roles: list[Role]) -> None:
        self._by_id = {role.id: role for role in roles}

    def get_by_id(self, id_: int) -> Role | None:
        return self._by_id.get(id_)

    def get_by_name(self, name: str) -> Role | None:
        return next((r for r in self._by_id.values() if r.name == name), None)


class FakeCategoryRepository:
    """In-memory stand-in for CategoryRepository. Same rationale as FakeUserRepository."""

    def __init__(self, categories: list[Category] | None = None) -> None:
        self._by_id = {category.id: category for category in (categories or [])}
        self._next_id = max(self._by_id, default=0) + 1
        self.referenced_category_ids: set[int] = set()

    def get_all(self) -> list[Category]:
        return list(self._by_id.values())

    def get_by_id(self, id_: int) -> Category | None:
        return self._by_id.get(id_)

    def get_by_name(self, name: str) -> Category | None:
        target = name.strip().lower()
        return next((c for c in self._by_id.values() if c.name.lower() == target), None)

    def create(self, obj: Category) -> Category:
        obj.id = self._next_id
        self._next_id += 1
        self._by_id[obj.id] = obj
        return obj

    def update(self, obj: Category) -> Category:
        self._by_id[obj.id] = obj
        return obj

    def delete(self, obj: Category) -> None:
        self._by_id.pop(obj.id, None)

    def is_referenced_by_tickets(self, category_id: int) -> bool:
        return category_id in self.referenced_category_ids


class FakeDepartmentRepository:
    """In-memory stand-in for DepartmentRepository. Same rationale as FakeCategoryRepository."""

    def __init__(self, departments: list[Department] | None = None) -> None:
        self._by_id = {department.id: department for department in (departments or [])}
        self._next_id = max(self._by_id, default=0) + 1

    def get_all(self) -> list[Department]:
        return list(self._by_id.values())

    def get_by_id(self, id_: int) -> Department | None:
        return self._by_id.get(id_)

    def get_by_title(self, title: str) -> Department | None:
        target = title.strip().lower()
        return next((d for d in self._by_id.values() if d.title.lower() == target), None)

    def create(self, obj: Department) -> Department:
        obj.id = self._next_id
        self._next_id += 1
        now = datetime.now(timezone.utc)
        obj.created_at = now
        obj.updated_at = now
        self._by_id[obj.id] = obj
        return obj

    def update(self, obj: Department) -> Department:
        obj.updated_at = datetime.now(timezone.utc)
        self._by_id[obj.id] = obj
        return obj


class FakeLocationRepository:
    """In-memory stand-in for LocationRepository. Same rationale as FakeCategoryRepository."""

    def __init__(self, locations: list[Location] | None = None) -> None:
        self._by_id = {location.id: location for location in (locations or [])}
        self._next_id = max(self._by_id, default=0) + 1

    def get_all(self) -> list[Location]:
        return list(self._by_id.values())

    def get_by_id(self, id_: int) -> Location | None:
        return self._by_id.get(id_)

    def get_by_title(self, title: str) -> Location | None:
        target = title.strip().lower()
        return next((loc for loc in self._by_id.values() if loc.title.lower() == target), None)

    def create(self, obj: Location) -> Location:
        obj.id = self._next_id
        self._next_id += 1
        now = datetime.now(timezone.utc)
        obj.created_at = now
        obj.updated_at = now
        self._by_id[obj.id] = obj
        return obj

    def update(self, obj: Location) -> Location:
        obj.updated_at = datetime.now(timezone.utc)
        self._by_id[obj.id] = obj
        return obj


class FakePriorityRepository:
    """In-memory stand-in for PriorityRepository. Same rationale as FakeCategoryRepository."""

    def __init__(self, priorities: list[Priority] | None = None) -> None:
        self._by_id = {priority.id: priority for priority in (priorities or [])}
        self._next_id = max(self._by_id, default=0) + 1

    def get_all(self) -> list[Priority]:
        return list(self._by_id.values())

    def get_by_id(self, id_: int) -> Priority | None:
        return self._by_id.get(id_)

    def get_by_title(self, title: str) -> Priority | None:
        target = title.strip().lower()
        return next((p for p in self._by_id.values() if p.title.lower() == target), None)

    def create(self, obj: Priority) -> Priority:
        obj.id = self._next_id
        self._next_id += 1
        now = datetime.now(timezone.utc)
        obj.created_at = now
        obj.updated_at = now
        self._by_id[obj.id] = obj
        return obj

    def update(self, obj: Priority) -> Priority:
        obj.updated_at = datetime.now(timezone.utc)
        self._by_id[obj.id] = obj
        return obj


class FakeTicketRepository:
    """In-memory stand-in for TicketRepository. Same rationale as FakeCategoryRepository."""

    _SORT_KEYS: dict[str, Callable[[Ticket], object]] = {
        "created_at": lambda t: t.created_at,
        "updated_at": lambda t: t.updated_at,
        "title": lambda t: t.title,
        "ticket_number": lambda t: t.ticket_number,
    }

    def __init__(self, tickets: list[Ticket] | None = None) -> None:
        self._by_id = {ticket.id: ticket for ticket in (tickets or [])}
        self._next_id = max(self._by_id, default=0) + 1
        self.fail_next_create = False

    def get_by_id(self, id_: int) -> Ticket | None:
        return self._by_id.get(id_)

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
        results = list(self._by_id.values())
        if department_id is not None:
            results = [
                t
                for t in results
                if t.created_by is not None and t.created_by.department_id == department_id
            ]
        if status is not None:
            results = [t for t in results if t.status == status]
        if priority_id is not None:
            results = [t for t in results if t.priority_id == priority_id]
        if category_id is not None:
            results = [t for t in results if t.category_id == category_id]
        if created_by_user_id is not None:
            results = [t for t in results if t.created_by_user_id == created_by_user_id]
        if assigned_technician_id is not None:
            results = [t for t in results if t.assigned_technician_id == assigned_technician_id]
        if search:
            needle = search.strip().lower()
            results = [
                t
                for t in results
                if needle in t.title.lower() or needle in t.description.lower()
            ]

        key_fn = self._SORT_KEYS.get(sort_by, self._SORT_KEYS["created_at"])
        results = sorted(results, key=key_fn, reverse=(sort_dir != "asc"))

        if skip is not None:
            results = results[skip:]
        if limit is not None:
            results = results[:limit]
        return results

    def create(self, obj: Ticket) -> Ticket:
        if self.fail_next_create:
            self.fail_next_create = False
            raise IntegrityError("insert", {}, Exception("duplicate ticket_number"))
        obj.id = self._next_id
        self._next_id += 1
        # A real INSERT would populate these via server_default=func.now();
        # an unsaved Python object has neither until "written".
        now = datetime.now(timezone.utc)
        obj.created_at = now
        obj.updated_at = now
        self._by_id[obj.id] = obj
        return obj

    def update(self, obj: Ticket) -> Ticket:
        obj.updated_at = datetime.now(timezone.utc)
        self._by_id[obj.id] = obj
        return obj

    def delete(self, obj: Ticket) -> None:
        self._by_id.pop(obj.id, None)

    def count_for_year(self, year: int) -> int:
        prefix = f"IT-{year}-"
        return sum(1 for t in self._by_id.values() if t.ticket_number.startswith(prefix))


class FakeCommentRepository:
    """In-memory stand-in for CommentRepository. Same rationale as FakeTicketRepository."""

    def __init__(self, comments: list[Comment] | None = None) -> None:
        self._by_id = {comment.id: comment for comment in (comments or [])}
        self._next_id = max(self._by_id, default=0) + 1

    def get_by_id(self, id_: int) -> Comment | None:
        return self._by_id.get(id_)

    def list_for_ticket(self, ticket_id: int) -> list[Comment]:
        return [c for c in self._by_id.values() if c.ticket_id == ticket_id]

    def create(self, obj: Comment) -> Comment:
        obj.id = self._next_id
        self._next_id += 1
        # A real INSERT would populate this via CreatedAtMixin's
        # server_default=func.now(); updated_at stays None until an edit,
        # matching the model exactly (no server default/onupdate on it).
        obj.created_at = datetime.now(timezone.utc)
        self._by_id[obj.id] = obj
        return obj

    def update(self, obj: Comment) -> Comment:
        self._by_id[obj.id] = obj
        return obj

    def delete(self, obj: Comment) -> None:
        self._by_id.pop(obj.id, None)


class FakeHistoryRepository:
    """In-memory stand-in for HistoryRepository. Same rationale as the others."""

    def __init__(self) -> None:
        self._entries: list[TicketHistory] = []
        self._next_id = 1

    def create(self, obj: TicketHistory) -> TicketHistory:
        obj.id = self._next_id
        self._next_id += 1
        obj.created_at = datetime.now(timezone.utc)
        self._entries.append(obj)
        return obj

    def list_for_ticket(self, ticket_id: int) -> list[TicketHistory]:
        return [e for e in self._entries if e.ticket_id == ticket_id]


class FakeAttachmentRepository:
    """In-memory stand-in for AttachmentRepository. Same rationale as the others."""

    def __init__(self, attachments: list[Attachment] | None = None) -> None:
        self._by_id = {a.id: a for a in (attachments or [])}
        self._next_id = max(self._by_id, default=0) + 1

    def get_by_id(self, id_: int) -> Attachment | None:
        return self._by_id.get(id_)

    def list_for_ticket(self, ticket_id: int) -> list[Attachment]:
        return [a for a in self._by_id.values() if a.ticket_id == ticket_id]

    def create(self, obj: Attachment) -> Attachment:
        obj.id = self._next_id
        self._next_id += 1
        obj.created_at = datetime.now(timezone.utc)
        self._by_id[obj.id] = obj
        return obj

    def delete(self, obj: Attachment) -> None:
        self._by_id.pop(obj.id, None)


class FakeStorageService:
    """In-memory stand-in for StorageService - no real filesystem access.

    AttachmentService only calls a few narrow methods, so a dict-backed
    double is enough to exercise upload/download/delete without touching
    disk during the API test suite. Real filesystem behavior (including
    path-traversal defense) is covered separately in test_storage_service.py
    against a real temp directory.
    """

    def __init__(self) -> None:
        self.files: dict[str, bytes] = {}
        self._counter = 0

    def generate_stored_filename(self, original_filename: str) -> str:
        extension = Path(original_filename or "").suffix.lower()
        self._counter += 1
        return f"fake-{self._counter}{extension}"

    def save(self, stored_filename: str, content: bytes) -> None:
        self.files[stored_filename] = content

    def load(self, stored_filename: str) -> bytes:
        return self.files[stored_filename]

    def delete(self, stored_filename: str) -> None:
        self.files.pop(stored_filename, None)


class FakeSession:
    """No-op stand-in for the transaction-boundary calls the services make.

    CategoryService/TicketService/CommentService/UserService/etc. own
    commit()/rollback() (repositories never commit), so a fake service
    needs a fake session to call those on - this just swallows both, since
    the fake repositories already persist in memory.
    """

    def commit(self) -> None:
        pass

    def rollback(self) -> None:
        pass


@pytest.fixture
def admin_role() -> Role:
    return Role(id=1, name="Administrator", description="Full system access")


@pytest.fixture
def employee_role() -> Role:
    return Role(id=2, name="Employee", description="Reports tickets")


@pytest.fixture
def technician_role() -> Role:
    return Role(id=3, name="Technician", description="Resolves tickets")


@pytest.fixture
def manager_role() -> Role:
    return Role(id=4, name="Manager", description="Oversees ticket resolution")


@pytest.fixture
def it_department() -> Department:
    now = datetime.now(timezone.utc)
    return Department(id=1, title="IT", created_at=now, updated_at=now)


@pytest.fixture
def hr_department() -> Department:
    now = datetime.now(timezone.utc)
    return Department(id=2, title="HR", created_at=now, updated_at=now)


@pytest.fixture
def low_priority() -> Priority:
    now = datetime.now(timezone.utc)
    return Priority(id=1, title="Low", created_at=now, updated_at=now)


@pytest.fixture
def medium_priority() -> Priority:
    now = datetime.now(timezone.utc)
    return Priority(id=2, title="Medium", created_at=now, updated_at=now)


@pytest.fixture
def high_priority() -> Priority:
    now = datetime.now(timezone.utc)
    return Priority(id=3, title="High", created_at=now, updated_at=now)


@pytest.fixture
def critical_priority() -> Priority:
    now = datetime.now(timezone.utc)
    return Priority(id=4, title="Critical", created_at=now, updated_at=now)


@pytest.fixture
def head_office_location() -> Location:
    now = datetime.now(timezone.utc)
    return Location(id=1, title="Head Office - Floor 2", is_active=True, created_at=now, updated_at=now)


@pytest.fixture
def branch_office_location() -> Location:
    now = datetime.now(timezone.utc)
    return Location(id=2, title="Branch Office", is_active=True, created_at=now, updated_at=now)


@pytest.fixture
def inactive_location() -> Location:
    """A retired location - no longer selectable, but a ticket may still reference it."""
    now = datetime.now(timezone.utc)
    return Location(id=3, title="Old Warehouse", is_active=False, created_at=now, updated_at=now)


@pytest.fixture
def active_admin_user(admin_role: Role, it_department: Department) -> User:
    now = datetime.now(timezone.utc)
    user = User(
        id=1,
        username="admin",
        first_name="Ada",
        last_name="Admin",
        email="admin@itonit.test",
        password_hash=hash_password(ADMIN_PASSWORD),
        role_id=admin_role.id,
        department_id=it_department.id,
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    user.role = admin_role
    user.department = it_department
    return user


@pytest.fixture
def inactive_user(employee_role: Role) -> User:
    now = datetime.now(timezone.utc)
    user = User(
        id=2,
        username="inactive",
        first_name="Ivy",
        last_name="Inactive",
        email="inactive@itonit.test",
        password_hash=hash_password(INACTIVE_PASSWORD),
        role_id=employee_role.id,
        is_active=False,
        created_at=now,
        updated_at=now,
    )
    user.role = employee_role
    user.department = None
    return user


@pytest.fixture
def active_employee_user(employee_role: Role, it_department: Department) -> User:
    now = datetime.now(timezone.utc)
    user = User(
        id=3,
        username="employee",
        first_name="Eve",
        last_name="Employee",
        email="employee@itonit.test",
        password_hash=hash_password(EMPLOYEE_PASSWORD),
        role_id=employee_role.id,
        department_id=it_department.id,
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    user.role = employee_role
    user.department = it_department
    return user


@pytest.fixture
def active_technician_user(technician_role: Role) -> User:
    now = datetime.now(timezone.utc)
    user = User(
        id=4,
        username="technician",
        first_name="Tom",
        last_name="Technician",
        email="technician@itonit.test",
        password_hash=hash_password(TECHNICIAN_PASSWORD),
        role_id=technician_role.id,
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    user.role = technician_role
    user.department = None
    return user


@pytest.fixture
def active_manager_user(manager_role: Role) -> User:
    now = datetime.now(timezone.utc)
    user = User(
        id=5,
        username="manager",
        first_name="Mona",
        last_name="Manager",
        email="manager@itonit.test",
        password_hash=hash_password(MANAGER_PASSWORD),
        role_id=manager_role.id,
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    user.role = manager_role
    user.department = None
    return user


@pytest.fixture
def active_employee_user_2(employee_role: Role, hr_department: Department) -> User:
    """A second employee, distinct from active_employee_user - needed to
    prove employees cannot see/edit each other's tickets."""
    now = datetime.now(timezone.utc)
    user = User(
        id=6,
        username="employee2",
        first_name="Eli",
        last_name="EmployeeTwo",
        email="employee2@itonit.test",
        password_hash=hash_password(EMPLOYEE_2_PASSWORD),
        role_id=employee_role.id,
        department_id=hr_department.id,
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    user.role = employee_role
    user.department = hr_department
    return user


@pytest.fixture
def active_technician_user_2(technician_role: Role) -> User:
    """A second technician, distinct from active_technician_user - needed to
    prove technicians cannot see/edit tickets assigned to someone else."""
    now = datetime.now(timezone.utc)
    user = User(
        id=7,
        username="technician2",
        first_name="Tia",
        last_name="TechnicianTwo",
        email="technician2@itonit.test",
        password_hash=hash_password(TECHNICIAN_2_PASSWORD),
        role_id=technician_role.id,
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    user.role = technician_role
    user.department = None
    return user


@pytest.fixture
def admin_password() -> str:
    return ADMIN_PASSWORD


@pytest.fixture
def inactive_password() -> str:
    return INACTIVE_PASSWORD


@pytest.fixture
def hardware_category() -> Category:
    return Category(id=1, name="Hardware", description="Physical equipment issues")


@pytest.fixture
def software_category() -> Category:
    return Category(id=2, name="Software", description="Application issues")


@pytest.fixture
def employee_ticket(
    hardware_category: Category,
    medium_priority: Priority,
    head_office_location: Location,
    active_employee_user: User,
) -> Ticket:
    """A brand-new ticket, owned by active_employee_user, not yet assigned."""
    now = datetime.now(timezone.utc)
    ticket = Ticket(
        id=1,
        ticket_number="IT-2026-000001",
        title="Laptop will not boot",
        description="Screen stays black after pressing the power button.",
        location_id=head_office_location.id,
        status=TicketStatus.NEW,
        priority_id=medium_priority.id,
        category_id=hardware_category.id,
        created_by_user_id=active_employee_user.id,
        assigned_technician_id=None,
        created_at=now,
        updated_at=now,
    )
    ticket.category = hardware_category
    ticket.priority = medium_priority
    ticket.location = head_office_location
    ticket.created_by = active_employee_user
    ticket.assigned_technician = None
    return ticket


@pytest.fixture
def assigned_ticket(
    software_category: Category,
    high_priority: Priority,
    active_employee_user: User,
    active_technician_user: User,
) -> Ticket:
    """A ticket already assigned to active_technician_user and in progress."""
    now = datetime.now(timezone.utc)
    ticket = Ticket(
        id=2,
        ticket_number="IT-2026-000002",
        title="VPN disconnects repeatedly",
        description="The VPN client drops the connection every few minutes.",
        location_id=None,
        status=TicketStatus.ASSIGNED,
        priority_id=high_priority.id,
        category_id=software_category.id,
        created_by_user_id=active_employee_user.id,
        assigned_technician_id=active_technician_user.id,
        created_at=now,
        updated_at=now,
    )
    ticket.category = software_category
    ticket.priority = high_priority
    ticket.created_by = active_employee_user
    ticket.assigned_technician = active_technician_user
    return ticket


@pytest.fixture
def employee_comment(employee_ticket: Ticket, active_employee_user: User) -> Comment:
    """A comment authored by active_employee_user on their own ticket."""
    comment = Comment(
        id=1,
        ticket_id=employee_ticket.id,
        author_user_id=active_employee_user.id,
        content="Initial comment from the employee.",
        created_at=datetime.now(timezone.utc),
    )
    comment.author = active_employee_user
    return comment


@pytest.fixture
def assigned_ticket_comment(assigned_ticket: Ticket, active_employee_user: User) -> Comment:
    """A comment on assigned_ticket, authored by the employee who created it.

    active_technician_user can also view assigned_ticket (it's assigned to
    them), so this fixture lets tests distinguish "blocked at the ticket
    view gate" from "blocked at comment ownership specifically" - both the
    employee and the technician can see this comment, but only the employee
    authored it.
    """
    comment = Comment(
        id=2,
        ticket_id=assigned_ticket.id,
        author_user_id=active_employee_user.id,
        content="Employee's comment on the assigned ticket.",
        created_at=datetime.now(timezone.utc),
    )
    comment.author = active_employee_user
    return comment


@pytest.fixture
def employee_attachment(employee_ticket: Ticket, active_employee_user: User) -> Attachment:
    """An attachment on employee_ticket, uploaded by active_employee_user."""
    attachment = Attachment(
        id=1,
        ticket_id=employee_ticket.id,
        uploaded_by_user_id=active_employee_user.id,
        original_filename="screenshot.png",
        stored_filename="existing-file.png",
        file_path="existing-file.png",
        content_type="image/png",
        file_size=17,
        created_at=datetime.now(timezone.utc),
    )
    attachment.uploaded_by = active_employee_user
    return attachment


@pytest.fixture
def user_repository(
    active_admin_user: User,
    inactive_user: User,
    active_employee_user: User,
    active_technician_user: User,
    active_manager_user: User,
    active_employee_user_2: User,
    active_technician_user_2: User,
) -> FakeUserRepository:
    return FakeUserRepository(
        [
            active_admin_user,
            inactive_user,
            active_employee_user,
            active_technician_user,
            active_manager_user,
            active_employee_user_2,
            active_technician_user_2,
        ]
    )


@pytest.fixture
def role_repository(
    admin_role: Role, employee_role: Role, technician_role: Role, manager_role: Role
) -> FakeRoleRepository:
    return FakeRoleRepository([admin_role, employee_role, technician_role, manager_role])


@pytest.fixture
def department_repository(
    it_department: Department, hr_department: Department
) -> FakeDepartmentRepository:
    return FakeDepartmentRepository([it_department, hr_department])


@pytest.fixture
def priority_repository(
    low_priority: Priority,
    medium_priority: Priority,
    high_priority: Priority,
    critical_priority: Priority,
) -> FakePriorityRepository:
    return FakePriorityRepository([low_priority, medium_priority, high_priority, critical_priority])


@pytest.fixture
def location_repository(
    head_office_location: Location,
    branch_office_location: Location,
    inactive_location: Location,
) -> FakeLocationRepository:
    return FakeLocationRepository([head_office_location, branch_office_location, inactive_location])


@pytest.fixture
def category_repository(
    hardware_category: Category, software_category: Category
) -> FakeCategoryRepository:
    return FakeCategoryRepository([hardware_category, software_category])


@pytest.fixture
def ticket_repository(
    employee_ticket: Ticket, assigned_ticket: Ticket
) -> FakeTicketRepository:
    return FakeTicketRepository([employee_ticket, assigned_ticket])


@pytest.fixture
def comment_repository(
    employee_comment: Comment, assigned_ticket_comment: Comment
) -> FakeCommentRepository:
    return FakeCommentRepository([employee_comment, assigned_ticket_comment])


@pytest.fixture
def history_repository() -> FakeHistoryRepository:
    return FakeHistoryRepository()


@pytest.fixture
def storage_service() -> FakeStorageService:
    return FakeStorageService()


@pytest.fixture
def attachment_repository(
    employee_attachment: Attachment, storage_service: FakeStorageService
) -> FakeAttachmentRepository:
    # Pre-populate the fake filesystem so a download of the fixture
    # attachment (created outside any upload call) has real bytes to return.
    storage_service.files[employee_attachment.file_path] = b"fake-png-bytes"
    return FakeAttachmentRepository([employee_attachment])


@pytest.fixture
def auth_headers() -> Callable[[User], dict[str, str]]:
    """Build an Authorization header for a given (unsaved) fixture user."""

    def _make(user: User) -> dict[str, str]:
        token = create_access_token(subject=user.id)
        return {"Authorization": f"Bearer {token}"}

    return _make


@pytest.fixture
def client(
    user_repository: FakeUserRepository,
    role_repository: FakeRoleRepository,
    department_repository: FakeDepartmentRepository,
    priority_repository: FakePriorityRepository,
    location_repository: FakeLocationRepository,
    category_repository: FakeCategoryRepository,
    ticket_repository: FakeTicketRepository,
    comment_repository: FakeCommentRepository,
    history_repository: FakeHistoryRepository,
    attachment_repository: FakeAttachmentRepository,
    storage_service: FakeStorageService,
) -> Iterator[TestClient]:
    # One shared HistoryService instance so ticket-mutation, comment-mutation,
    # and attachment-mutation history all land in the same store - a single
    # GET /history call in a test can then observe entries from any of them.
    history_service = HistoryService(db=FakeSession(), history_repository=history_repository)

    app.dependency_overrides[get_user_repository] = lambda: user_repository
    app.dependency_overrides[get_auth_service] = lambda: AuthService(
        db=None, user_repository=user_repository
    )
    app.dependency_overrides[get_category_service] = lambda: CategoryService(
        db=FakeSession(), category_repository=category_repository
    )
    app.dependency_overrides[get_department_service] = lambda: DepartmentService(
        db=FakeSession(), department_repository=department_repository
    )
    app.dependency_overrides[get_priority_service] = lambda: PriorityService(
        db=FakeSession(), priority_repository=priority_repository
    )
    app.dependency_overrides[get_location_service] = lambda: LocationService(
        db=FakeSession(), location_repository=location_repository
    )
    app.dependency_overrides[get_user_service] = lambda: UserService(
        db=FakeSession(),
        user_repository=user_repository,
        role_repository=role_repository,
        department_repository=department_repository,
    )
    app.dependency_overrides[get_ticket_service] = lambda: TicketService(
        db=FakeSession(),
        ticket_repository=ticket_repository,
        category_repository=category_repository,
        priority_repository=priority_repository,
        location_repository=location_repository,
        user_repository=user_repository,
        history_service=history_service,
        storage_service=storage_service,
    )
    app.dependency_overrides[get_comment_service] = lambda: CommentService(
        db=FakeSession(),
        comment_repository=comment_repository,
        history_service=history_service,
    )
    app.dependency_overrides[get_history_service] = lambda: history_service
    app.dependency_overrides[get_attachment_service] = lambda: AttachmentService(
        db=FakeSession(),
        attachment_repository=attachment_repository,
        storage_service=storage_service,
        history_service=history_service,
    )
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
