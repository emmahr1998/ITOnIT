from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from app.models.priority import Priority
from app.models.user import User
from app.schemas.priority import PriorityCreate
from app.services.priority_service import PriorityService, PriorityTitleConflictError
from tests.conftest import FakePriorityRepository, FakeSession

# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("role_fixture", ["active_manager_user", "active_admin_user"])
def test_create_priority_succeeds_for_manage_roles(
    client: TestClient,
    auth_headers: Callable[[User], dict[str, str]],
    role_fixture: str,
    request: pytest.FixtureRequest,
) -> None:
    user = request.getfixturevalue(role_fixture)
    response = client.post(
        "/priorities", json={"title": "Urgent"}, headers=auth_headers(user)
    )
    assert response.status_code == 201
    body = response.json()
    assert body["data"]["title"] == "Urgent"
    assert "id" in body["data"]
    assert body["msg"]


@pytest.mark.parametrize(
    "role_fixture", ["active_employee_user", "active_technician_user"]
)
def test_create_priority_forbidden_for_non_manage_roles(
    client: TestClient,
    auth_headers: Callable[[User], dict[str, str]],
    role_fixture: str,
    request: pytest.FixtureRequest,
) -> None:
    user = request.getfixturevalue(role_fixture)
    response = client.post(
        "/priorities", json={"title": "Urgent"}, headers=auth_headers(user)
    )
    assert response.status_code == 403


def test_create_priority_duplicate_title_returns_409(
    client: TestClient,
    active_manager_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    medium_priority: Priority,
) -> None:
    response = client.post(
        "/priorities",
        json={"title": medium_priority.title},
        headers=auth_headers(active_manager_user),
    )
    assert response.status_code == 409


def test_create_priority_case_insensitive_duplicate_returns_409(
    client: TestClient,
    active_manager_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    medium_priority: Priority,
) -> None:
    response = client.post(
        "/priorities",
        json={"title": medium_priority.title.upper()},
        headers=auth_headers(active_manager_user),
    )
    assert response.status_code == 409


def test_create_priority_blank_title_returns_422(
    client: TestClient,
    active_manager_user: User,
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    response = client.post(
        "/priorities", json={"title": "   "}, headers=auth_headers(active_manager_user)
    )
    assert response.status_code == 422


def test_create_priority_requires_authentication(client: TestClient) -> None:
    response = client.post("/priorities", json={"title": "Urgent"})
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# List / Get
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "role_fixture",
    ["active_employee_user", "active_technician_user", "active_manager_user", "active_admin_user"],
)
def test_list_priorities_allowed_for_every_role(
    client: TestClient,
    auth_headers: Callable[[User], dict[str, str]],
    role_fixture: str,
    request: pytest.FixtureRequest,
) -> None:
    user = request.getfixturevalue(role_fixture)
    response = client.get("/priorities", headers=auth_headers(user))
    assert response.status_code == 200
    titles = {p["title"] for p in response.json()["data"]}
    assert {"Low", "Medium", "High", "Critical"} <= titles


def test_list_priorities_requires_authentication(client: TestClient) -> None:
    response = client.get("/priorities")
    assert response.status_code == 401


def test_get_priority_by_id_succeeds(
    client: TestClient,
    active_employee_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    high_priority: Priority,
) -> None:
    response = client.get(
        f"/priorities/{high_priority.id}", headers=auth_headers(active_employee_user)
    )
    assert response.status_code == 200
    assert response.json()["data"]["title"] == "High"


def test_get_priority_unknown_id_returns_404(
    client: TestClient,
    active_employee_user: User,
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    response = client.get("/priorities/999999", headers=auth_headers(active_employee_user))
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------


def test_update_priority_succeeds(
    client: TestClient,
    active_admin_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    high_priority: Priority,
) -> None:
    response = client.patch(
        f"/priorities/{high_priority.id}",
        json={"title": "Very High"},
        headers=auth_headers(active_admin_user),
    )
    assert response.status_code == 200
    assert response.json()["data"]["title"] == "Very High"


def test_update_priority_unknown_id_returns_404(
    client: TestClient,
    active_admin_user: User,
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    response = client.patch(
        "/priorities/999999", json={"title": "Whatever"}, headers=auth_headers(active_admin_user)
    )
    assert response.status_code == 404


def test_update_priority_duplicate_title_returns_409(
    client: TestClient,
    active_admin_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    medium_priority: Priority,
    high_priority: Priority,
) -> None:
    response = client.patch(
        f"/priorities/{medium_priority.id}",
        json={"title": high_priority.title},
        headers=auth_headers(active_admin_user),
    )
    assert response.status_code == 409


def test_update_priority_forbidden_for_non_manage_role(
    client: TestClient,
    active_technician_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    high_priority: Priority,
) -> None:
    response = client.patch(
        f"/priorities/{high_priority.id}",
        json={"title": "New Name"},
        headers=auth_headers(active_technician_user),
    )
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Schema-level validation (no HTTP, no DB)
# ---------------------------------------------------------------------------


def test_priority_create_strips_whitespace_from_title() -> None:
    payload = PriorityCreate(title="  Urgent  ")
    assert payload.title == "Urgent"


def test_priority_create_rejects_empty_title() -> None:
    with pytest.raises(ValueError):
        PriorityCreate(title="   ")


# ---------------------------------------------------------------------------
# Service-level: race-condition fallback for uniqueness
# ---------------------------------------------------------------------------


def test_create_priority_translates_integrity_error_to_conflict() -> None:
    class RaisingRepository(FakePriorityRepository):
        def create(self, obj: Priority) -> Priority:
            raise IntegrityError("insert", {}, Exception("unique constraint"))

    service = PriorityService(db=FakeSession(), priority_repository=RaisingRepository())

    with pytest.raises(PriorityTitleConflictError):
        service.create_priority(PriorityCreate(title="Urgent"))
