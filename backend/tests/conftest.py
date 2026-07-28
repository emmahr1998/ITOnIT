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
from app.dependencies.history import get_history_service
from app.dependencies.ticket import get_ticket_service
from app.main import app
from app.models.attachment import Attachment
from app.models.category import Category
from app.models.comment import Comment
from app.models.enums import TicketPriority, TicketStatus
from app.models.role import Role
from app.models.ticket import Ticket
from app.models.ticket_history import TicketHistory
from app.models.user import User
from app.services.attachment_service import AttachmentService
from app.services.auth_service import AuthService
from app.services.category_service import CategoryService
from app.services.comment_service import CommentService
from app.services.history_service import HistoryService
from app.services.ticket_service import TicketService

ADMIN_PASSWORD = "CorrectHorseBattery1!"
INACTIVE_PASSWORD = "SomePassword1!"
EMPLOYEE_PASSWORD = "EmployeePass1!"
TECHNICIAN_PASSWORD = "TechnicianPass1!"
MANAGER_PASSWORD = "ManagerPass1!"
EMPLOYEE_2_PASSWORD = "EmployeeTwoPass1!"
TECHNICIAN_2_PASSWORD = "TechnicianTwoPass1!"


class FakeUserRepository:
    """In-memory stand-in for UserRepository.

    Auth tests must not touch the real SQL-Server-only database, and the
    production models aren't SQLite-compatible enough to fake with an
    in-memory engine. Instead, AuthService and the auth dependencies accept
    a repository object structurally (same method names/signatures as
    UserRepository), so this plain Python class - backed by a dict of
    plain (unsaved) User/Role ORM instances - substitutes for it without
    ever creating an engine or session.
    """

    def __init__(self, users: list[User]) -> None:
        self._by_id = {user.id: user for user in users}
        self._by_email = {user.email.strip().lower(): user for user in users}

    def get_by_id(self, id_: int) -> User | None:
        return self._by_id.get(id_)

    def get_by_email(self, email: str) -> User | None:
        return self._by_email.get(email.strip().lower())


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


class FakeTicketRepository:
    """In-memory stand-in for TicketRepository. Same rationale as FakeCategoryRepository."""

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
        priority: TicketPriority | None = None,
        category_id: int | None = None,
        created_by_user_id: int | None = None,
        assigned_technician_id: int | None = None,
    ) -> list[Ticket]:
        results = list(self._by_id.values())
        if status is not None:
            results = [t for t in results if t.status == status]
        if priority is not None:
            results = [t for t in results if t.priority == priority]
        if category_id is not None:
            results = [t for t in results if t.category_id == category_id]
        if created_by_user_id is not None:
            results = [t for t in results if t.created_by_user_id == created_by_user_id]
        if assigned_technician_id is not None:
            results = [t for t in results if t.assigned_technician_id == assigned_technician_id]
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

    CategoryService/TicketService/CommentService own commit()/rollback()
    (repositories never commit), so a fake service needs a fake session to
    call those on - this just swallows both, since the fake repositories
    already persist in memory.
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
def active_admin_user(admin_role: Role) -> User:
    user = User(
        id=1,
        first_name="Ada",
        last_name="Admin",
        email="admin@itonit.test",
        password_hash=hash_password(ADMIN_PASSWORD),
        role_id=admin_role.id,
        is_active=True,
    )
    user.role = admin_role
    return user


@pytest.fixture
def inactive_user(employee_role: Role) -> User:
    user = User(
        id=2,
        first_name="Ivy",
        last_name="Inactive",
        email="inactive@itonit.test",
        password_hash=hash_password(INACTIVE_PASSWORD),
        role_id=employee_role.id,
        is_active=False,
    )
    user.role = employee_role
    return user


@pytest.fixture
def active_employee_user(employee_role: Role) -> User:
    user = User(
        id=3,
        first_name="Eve",
        last_name="Employee",
        email="employee@itonit.test",
        password_hash=hash_password(EMPLOYEE_PASSWORD),
        role_id=employee_role.id,
        is_active=True,
    )
    user.role = employee_role
    return user


@pytest.fixture
def active_technician_user(technician_role: Role) -> User:
    user = User(
        id=4,
        first_name="Tom",
        last_name="Technician",
        email="technician@itonit.test",
        password_hash=hash_password(TECHNICIAN_PASSWORD),
        role_id=technician_role.id,
        is_active=True,
    )
    user.role = technician_role
    return user


@pytest.fixture
def active_manager_user(manager_role: Role) -> User:
    user = User(
        id=5,
        first_name="Mona",
        last_name="Manager",
        email="manager@itonit.test",
        password_hash=hash_password(MANAGER_PASSWORD),
        role_id=manager_role.id,
        is_active=True,
    )
    user.role = manager_role
    return user


@pytest.fixture
def active_employee_user_2(employee_role: Role) -> User:
    """A second employee, distinct from active_employee_user - needed to
    prove employees cannot see/edit each other's tickets."""
    user = User(
        id=6,
        first_name="Eli",
        last_name="EmployeeTwo",
        email="employee2@itonit.test",
        password_hash=hash_password(EMPLOYEE_2_PASSWORD),
        role_id=employee_role.id,
        is_active=True,
    )
    user.role = employee_role
    return user


@pytest.fixture
def active_technician_user_2(technician_role: Role) -> User:
    """A second technician, distinct from active_technician_user - needed to
    prove technicians cannot see/edit tickets assigned to someone else."""
    user = User(
        id=7,
        first_name="Tia",
        last_name="TechnicianTwo",
        email="technician2@itonit.test",
        password_hash=hash_password(TECHNICIAN_2_PASSWORD),
        role_id=technician_role.id,
        is_active=True,
    )
    user.role = technician_role
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
def employee_ticket(hardware_category: Category, active_employee_user: User) -> Ticket:
    """A brand-new ticket, owned by active_employee_user, not yet assigned."""
    now = datetime.now(timezone.utc)
    ticket = Ticket(
        id=1,
        ticket_number="IT-2026-000001",
        title="Laptop will not boot",
        description="Screen stays black after pressing the power button.",
        status=TicketStatus.NEW,
        priority=TicketPriority.MEDIUM,
        category_id=hardware_category.id,
        created_by_user_id=active_employee_user.id,
        assigned_technician_id=None,
        created_at=now,
        updated_at=now,
    )
    ticket.category = hardware_category
    ticket.created_by = active_employee_user
    ticket.assigned_technician = None
    return ticket


@pytest.fixture
def assigned_ticket(
    software_category: Category, active_employee_user: User, active_technician_user: User
) -> Ticket:
    """A ticket already assigned to active_technician_user and in progress."""
    now = datetime.now(timezone.utc)
    ticket = Ticket(
        id=2,
        ticket_number="IT-2026-000002",
        title="VPN disconnects repeatedly",
        description="The VPN client drops the connection every few minutes.",
        status=TicketStatus.ASSIGNED,
        priority=TicketPriority.HIGH,
        category_id=software_category.id,
        created_by_user_id=active_employee_user.id,
        assigned_technician_id=active_technician_user.id,
        created_at=now,
        updated_at=now,
    )
    ticket.category = software_category
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
    app.dependency_overrides[get_ticket_service] = lambda: TicketService(
        db=FakeSession(),
        ticket_repository=ticket_repository,
        category_repository=category_repository,
        user_repository=user_repository,
        history_service=history_service,
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
