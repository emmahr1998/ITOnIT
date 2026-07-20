from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.core.security import hash_password
from app.dependencies.auth import get_auth_service, get_user_repository
from app.main import app
from app.models.role import Role
from app.models.user import User
from app.services.auth_service import AuthService

ADMIN_PASSWORD = "CorrectHorseBattery1!"
INACTIVE_PASSWORD = "SomePassword1!"


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


@pytest.fixture
def admin_role() -> Role:
    return Role(id=1, name="Administrator", description="Full system access")


@pytest.fixture
def employee_role() -> Role:
    return Role(id=2, name="Employee", description="Reports tickets")


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
def admin_password() -> str:
    return ADMIN_PASSWORD


@pytest.fixture
def inactive_password() -> str:
    return INACTIVE_PASSWORD


@pytest.fixture
def user_repository(active_admin_user: User, inactive_user: User) -> FakeUserRepository:
    return FakeUserRepository([active_admin_user, inactive_user])


@pytest.fixture
def client(user_repository: FakeUserRepository) -> Iterator[TestClient]:
    app.dependency_overrides[get_user_repository] = lambda: user_repository
    app.dependency_overrides[get_auth_service] = lambda: AuthService(
        db=None, user_repository=user_repository
    )
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
