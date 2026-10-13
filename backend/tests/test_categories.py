from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from app.models.category import Category
from app.models.user import User
from app.schemas.category import CategoryCreate
from app.services.category_service import (
    CategoryInUseError,
    CategoryNameConflictError,
    CategoryService,
)
from tests.conftest import FakeCategoryRepository, FakeSession


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("role_fixture", ["active_manager_user", "active_admin_user"])
def test_create_category_succeeds_for_manage_roles(
    client: TestClient,
    auth_headers: Callable[[User], dict[str, str]],
    role_fixture: str,
    request: pytest.FixtureRequest,
) -> None:
    user = request.getfixturevalue(role_fixture)
    response = client.post(
        "/categories",
        json={"name": "Printer", "description": "Printer and scanner issues"},
        headers=auth_headers(user),
    )
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Printer"
    assert body["description"] == "Printer and scanner issues"
    assert "id" in body


@pytest.mark.parametrize(
    "role_fixture", ["active_employee_user", "active_technician_user"]
)
def test_create_category_forbidden_for_view_only_roles(
    client: TestClient,
    auth_headers: Callable[[User], dict[str, str]],
    role_fixture: str,
    request: pytest.FixtureRequest,
) -> None:
    user = request.getfixturevalue(role_fixture)
    response = client.post(
        "/categories",
        json={"name": "Printer"},
        headers=auth_headers(user),
    )
    assert response.status_code == 403


def test_create_category_duplicate_name_returns_409(
    client: TestClient,
    active_manager_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    hardware_category: Category,
) -> None:
    response = client.post(
        "/categories",
        json={"name": hardware_category.name},
        headers=auth_headers(active_manager_user),
    )
    assert response.status_code == 409


def test_create_category_case_insensitive_duplicate_returns_409(
    client: TestClient,
    active_manager_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    hardware_category: Category,
) -> None:
    response = client.post(
        "/categories",
        json={"name": hardware_category.name.upper()},
        headers=auth_headers(active_manager_user),
    )
    assert response.status_code == 409


def test_create_category_requires_authentication(client: TestClient) -> None:
    response = client.post("/categories", json={"name": "Printer"})
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# List / Get
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "role_fixture",
    [
        "active_employee_user",
        "active_technician_user",
        "active_manager_user",
        "active_admin_user",
    ],
)
def test_list_categories_allowed_for_every_role(
    client: TestClient,
    auth_headers: Callable[[User], dict[str, str]],
    role_fixture: str,
    request: pytest.FixtureRequest,
) -> None:
    user = request.getfixturevalue(role_fixture)
    response = client.get("/categories", headers=auth_headers(user))
    assert response.status_code == 200
    names = {category["name"] for category in response.json()}
    assert {"Hardware", "Software"} <= names


def test_get_category_by_id_succeeds(
    client: TestClient,
    active_employee_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    hardware_category: Category,
) -> None:
    response = client.get(
        f"/categories/{hardware_category.id}", headers=auth_headers(active_employee_user)
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Hardware"


def test_get_category_unknown_id_returns_404(
    client: TestClient,
    active_employee_user: User,
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    response = client.get("/categories/999999", headers=auth_headers(active_employee_user))
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------


def test_update_category_succeeds(
    client: TestClient,
    active_admin_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    hardware_category: Category,
) -> None:
    response = client.put(
        f"/categories/{hardware_category.id}",
        json={"name": "Hardware & Peripherals", "description": "Updated description"},
        headers=auth_headers(active_admin_user),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Hardware & Peripherals"
    assert body["description"] == "Updated description"


def test_update_category_unknown_id_returns_404(
    client: TestClient,
    active_admin_user: User,
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    response = client.put(
        "/categories/999999",
        json={"name": "Whatever"},
        headers=auth_headers(active_admin_user),
    )
    assert response.status_code == 404


def test_update_category_duplicate_name_returns_409(
    client: TestClient,
    active_admin_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    hardware_category: Category,
    software_category: Category,
) -> None:
    response = client.put(
        f"/categories/{hardware_category.id}",
        json={"name": software_category.name},
        headers=auth_headers(active_admin_user),
    )
    assert response.status_code == 409


def test_update_category_forbidden_for_view_only_role(
    client: TestClient,
    active_technician_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    hardware_category: Category,
) -> None:
    response = client.put(
        f"/categories/{hardware_category.id}",
        json={"name": "New Name"},
        headers=auth_headers(active_technician_user),
    )
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


def test_delete_category_succeeds(
    client: TestClient,
    active_admin_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    hardware_category: Category,
) -> None:
    response = client.delete(
        f"/categories/{hardware_category.id}", headers=auth_headers(active_admin_user)
    )
    assert response.status_code == 204

    follow_up = client.get(
        f"/categories/{hardware_category.id}", headers=auth_headers(active_admin_user)
    )
    assert follow_up.status_code == 404


def test_delete_category_unknown_id_returns_404(
    client: TestClient,
    active_admin_user: User,
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    response = client.delete("/categories/999999", headers=auth_headers(active_admin_user))
    assert response.status_code == 404


def test_delete_category_referenced_by_tickets_returns_409(
    client: TestClient,
    active_admin_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    hardware_category: Category,
    category_repository: FakeCategoryRepository,
) -> None:
    category_repository.referenced_category_ids.add(hardware_category.id)

    response = client.delete(
        f"/categories/{hardware_category.id}", headers=auth_headers(active_admin_user)
    )
    assert response.status_code == 409

    still_there = client.get(
        f"/categories/{hardware_category.id}", headers=auth_headers(active_admin_user)
    )
    assert still_there.status_code == 200


def test_delete_category_forbidden_for_view_only_role(
    client: TestClient,
    active_employee_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    hardware_category: Category,
) -> None:
    response = client.delete(
        f"/categories/{hardware_category.id}", headers=auth_headers(active_employee_user)
    )
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Schema-level validation (no HTTP, no DB)
# ---------------------------------------------------------------------------


def test_category_create_strips_whitespace_from_name() -> None:
    payload = CategoryCreate(name="  Hardware  ", description="  desc  ")
    assert payload.name == "Hardware"
    assert payload.description == "desc"


def test_category_create_rejects_empty_name() -> None:
    with pytest.raises(ValueError):
        CategoryCreate(name="   ")


# ---------------------------------------------------------------------------
# Service-level: race-condition fallback (not reachable through the fake's
# pre-check, since the fake never disagrees with the service's own check)
# ---------------------------------------------------------------------------


def test_create_category_translates_integrity_error_to_conflict() -> None:
    class RaisingRepository(FakeCategoryRepository):
        def create(self, obj: Category) -> Category:
            raise IntegrityError("insert", {}, Exception("unique constraint"))

    service = CategoryService(db=FakeSession(), company_id=1, category_repository=RaisingRepository())

    with pytest.raises(CategoryNameConflictError):
        service.create_category(CategoryCreate(name="Hardware"))


def test_delete_category_translates_integrity_error_to_in_use() -> None:
    """A ticket could start referencing the category between the pre-check
    and the delete reaching the database; the FK constraint catches that
    race, and the service must still report it as CategoryInUseError."""

    category = Category(id=1, name="Hardware", description=None)

    class RaisingRepository(FakeCategoryRepository):
        def delete(self, obj: Category) -> None:
            raise IntegrityError("delete", {}, Exception("FK constraint"))

    repository = RaisingRepository([category])
    service = CategoryService(db=FakeSession(), company_id=1, category_repository=repository)

    with pytest.raises(CategoryInUseError):
        service.delete_category(category.id)
