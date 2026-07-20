from collections.abc import Callable, Iterator

import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token, hash_password
from app.dependencies.auth import get_auth_service, get_user_repository
from app.dependencies.category import get_category_service
from app.main import app
from app.models.category import Category
from app.models.role import Role
from app.models.user import User
from app.services.auth_service import AuthService
from app.services.category_service import CategoryService

ADMIN_PASSWORD = "CorrectHorseBattery1!"
INACTIVE_PASSWORD = "SomePassword1!"
EMPLOYEE_PASSWORD = "EmployeePass1!"
TECHNICIAN_PASSWORD = "TechnicianPass1!"
MANAGER_PASSWORD = "ManagerPass1!"


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


class FakeSession:
    """No-op stand-in for the transaction-boundary calls CategoryService makes.

    CategoryService owns commit()/rollback() (repositories never commit),
    so a fake service needs a fake session to call those on - this just
    swallows both, since FakeCategoryRepository already persists in memory.
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
def user_repository(
    active_admin_user: User,
    inactive_user: User,
    active_employee_user: User,
    active_technician_user: User,
    active_manager_user: User,
) -> FakeUserRepository:
    return FakeUserRepository(
        [
            active_admin_user,
            inactive_user,
            active_employee_user,
            active_technician_user,
            active_manager_user,
        ]
    )


@pytest.fixture
def category_repository(
    hardware_category: Category, software_category: Category
) -> FakeCategoryRepository:
    return FakeCategoryRepository([hardware_category, software_category])


@pytest.fixture
def auth_headers() -> Callable[[User], dict[str, str]]:
    """Build an Authorization header for a given (unsaved) fixture user."""

    def _make(user: User) -> dict[str, str]:
        token = create_access_token(subject=user.id)
        return {"Authorization": f"Bearer {token}"}

    return _make


@pytest.fixture
def client(
    user_repository: FakeUserRepository, category_repository: FakeCategoryRepository
) -> Iterator[TestClient]:
    app.dependency_overrides[get_user_repository] = lambda: user_repository
    app.dependency_overrides[get_auth_service] = lambda: AuthService(
        db=None, user_repository=user_repository
    )
    app.dependency_overrides[get_category_service] = lambda: CategoryService(
        db=FakeSession(), category_repository=category_repository
    )
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
