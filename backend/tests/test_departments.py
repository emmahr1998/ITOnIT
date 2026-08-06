from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from app.models.department import Department
from app.models.user import User
from app.schemas.department import DepartmentCreate
from app.services.department_service import DepartmentService, DepartmentTitleConflictError
from tests.conftest import FakeDepartmentRepository, FakeSession

# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("role_fixture", ["active_manager_user", "active_admin_user"])
def test_create_department_succeeds_for_manage_roles(
    client: TestClient,
    auth_headers: Callable[[User], dict[str, str]],
    role_fixture: str,
    request: pytest.FixtureRequest,
) -> None:
    user = request.getfixturevalue(role_fixture)
    response = client.post(
        "/departments", json={"title": "Finance"}, headers=auth_headers(user)
    )
    assert response.status_code == 201
    body = response.json()
    assert body["data"]["title"] == "Finance"
    assert "id" in body["data"]
    assert body["msg"]


@pytest.mark.parametrize(
    "role_fixture", ["active_employee_user", "active_technician_user"]
)
def test_create_department_forbidden_for_non_manage_roles(
    client: TestClient,
    auth_headers: Callable[[User], dict[str, str]],
    role_fixture: str,
    request: pytest.FixtureRequest,
) -> None:
    user = request.getfixturevalue(role_fixture)
    response = client.post(
        "/departments", json={"title": "Finance"}, headers=auth_headers(user)
    )
    assert response.status_code == 403


def test_create_department_duplicate_title_returns_409(
    client: TestClient,
    active_manager_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    it_department: Department,
) -> None:
    response = client.post(
        "/departments", json={"title": it_department.title}, headers=auth_headers(active_manager_user)
    )
    assert response.status_code == 409


def test_create_department_case_insensitive_duplicate_returns_409(
    client: TestClient,
    active_manager_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    it_department: Department,
) -> None:
    response = client.post(
        "/departments",
        json={"title": it_department.title.upper()},
        headers=auth_headers(active_manager_user),
    )
    assert response.status_code == 409


def test_create_department_blank_title_returns_422(
    client: TestClient,
    active_manager_user: User,
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    response = client.post(
        "/departments", json={"title": "   "}, headers=auth_headers(active_manager_user)
    )
    assert response.status_code == 422


def test_create_department_requires_authentication(client: TestClient) -> None:
    response = client.post("/departments", json={"title": "Finance"})
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# List / Get
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "role_fixture",
    ["active_employee_user", "active_technician_user", "active_manager_user", "active_admin_user"],
)
def test_list_departments_allowed_for_every_role(
    client: TestClient,
    auth_headers: Callable[[User], dict[str, str]],
    role_fixture: str,
    request: pytest.FixtureRequest,
) -> None:
    user = request.getfixturevalue(role_fixture)
    response = client.get("/departments", headers=auth_headers(user))
    assert response.status_code == 200
    titles = {d["title"] for d in response.json()["data"]}
    assert {"IT", "HR"} <= titles


def test_list_departments_requires_authentication(client: TestClient) -> None:
    response = client.get("/departments")
    assert response.status_code == 401


def test_get_department_by_id_succeeds(
    client: TestClient,
    active_employee_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    it_department: Department,
) -> None:
    response = client.get(
        f"/departments/{it_department.id}", headers=auth_headers(active_employee_user)
    )
    assert response.status_code == 200
    assert response.json()["data"]["title"] == "IT"


def test_get_department_unknown_id_returns_404(
    client: TestClient,
    active_employee_user: User,
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    response = client.get("/departments/999999", headers=auth_headers(active_employee_user))
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------


def test_update_department_succeeds(
    client: TestClient,
    active_admin_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    it_department: Department,
) -> None:
    response = client.patch(
        f"/departments/{it_department.id}",
        json={"title": "Information Technology"},
        headers=auth_headers(active_admin_user),
    )
    assert response.status_code == 200
    assert response.json()["data"]["title"] == "Information Technology"


def test_update_department_unknown_id_returns_404(
    client: TestClient,
    active_admin_user: User,
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    response = client.patch(
        "/departments/999999", json={"title": "Whatever"}, headers=auth_headers(active_admin_user)
    )
    assert response.status_code == 404


def test_update_department_duplicate_title_returns_409(
    client: TestClient,
    active_admin_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    it_department: Department,
    hr_department: Department,
) -> None:
    response = client.patch(
        f"/departments/{it_department.id}",
        json={"title": hr_department.title},
        headers=auth_headers(active_admin_user),
    )
    assert response.status_code == 409


def test_update_department_forbidden_for_non_manage_role(
    client: TestClient,
    active_technician_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    it_department: Department,
) -> None:
    response = client.patch(
        f"/departments/{it_department.id}",
        json={"title": "New Name"},
        headers=auth_headers(active_technician_user),
    )
    assert response.status_code == 403


def test_update_department_partial_update_is_a_noop_when_omitted(
    client: TestClient,
    active_admin_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    it_department: Department,
) -> None:
    response = client.patch(
        f"/departments/{it_department.id}", json={}, headers=auth_headers(active_admin_user)
    )
    assert response.status_code == 200
    assert response.json()["data"]["title"] == it_department.title


# ---------------------------------------------------------------------------
# Schema-level validation (no HTTP, no DB)
# ---------------------------------------------------------------------------


def test_department_create_strips_whitespace_from_title() -> None:
    payload = DepartmentCreate(title="  Finance  ")
    assert payload.title == "Finance"


def test_department_create_rejects_empty_title() -> None:
    with pytest.raises(ValueError):
        DepartmentCreate(title="   ")


# ---------------------------------------------------------------------------
# Service-level: race-condition fallback for uniqueness
# ---------------------------------------------------------------------------


def test_create_department_translates_integrity_error_to_conflict() -> None:
    class RaisingRepository(FakeDepartmentRepository):
        def create(self, obj: Department) -> Department:
            raise IntegrityError("insert", {}, Exception("unique constraint"))

    service = DepartmentService(db=FakeSession(), department_repository=RaisingRepository())

    with pytest.raises(DepartmentTitleConflictError):
        service.create_department(DepartmentCreate(title="Finance"))
