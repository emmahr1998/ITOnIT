from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from app.models.location import Location
from app.models.user import User
from app.schemas.location import LocationCreate
from app.services.location_service import LocationService, LocationTitleConflictError
from tests.conftest import FakeLocationRepository, FakeSession

# ---------------------------------------------------------------------------
# Create - Administrator only (unlike Departments/Priorities, Manager is NOT
# allowed to manage locations, per the explicit "Admin can create/edit/
# deactivate" requirement).
# ---------------------------------------------------------------------------


def test_create_location_succeeds_for_admin(
    client: TestClient,
    active_admin_user: User,
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    response = client.post(
        "/locations", json={"title": "Warehouse B"}, headers=auth_headers(active_admin_user)
    )
    assert response.status_code == 201
    body = response.json()
    assert body["data"]["title"] == "Warehouse B"
    assert body["data"]["is_active"] is True
    assert "id" in body["data"]
    assert body["msg"]


@pytest.mark.parametrize(
    "role_fixture", ["active_employee_user", "active_technician_user", "active_manager_user"]
)
def test_create_location_forbidden_for_non_admin_roles(
    client: TestClient,
    auth_headers: Callable[[User], dict[str, str]],
    role_fixture: str,
    request: pytest.FixtureRequest,
) -> None:
    """Unlike Departments/Priorities, a Manager may not manage locations."""
    user = request.getfixturevalue(role_fixture)
    response = client.post(
        "/locations", json={"title": "Warehouse B"}, headers=auth_headers(user)
    )
    assert response.status_code == 403


def test_create_location_duplicate_title_returns_409(
    client: TestClient,
    active_admin_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    head_office_location: Location,
) -> None:
    response = client.post(
        "/locations",
        json={"title": head_office_location.title},
        headers=auth_headers(active_admin_user),
    )
    assert response.status_code == 409


def test_create_location_case_insensitive_duplicate_returns_409(
    client: TestClient,
    active_admin_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    head_office_location: Location,
) -> None:
    response = client.post(
        "/locations",
        json={"title": head_office_location.title.upper()},
        headers=auth_headers(active_admin_user),
    )
    assert response.status_code == 409


def test_create_location_blank_title_returns_422(
    client: TestClient,
    active_admin_user: User,
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    response = client.post(
        "/locations", json={"title": "   "}, headers=auth_headers(active_admin_user)
    )
    assert response.status_code == 422


def test_create_location_requires_authentication(client: TestClient) -> None:
    response = client.post("/locations", json={"title": "Warehouse B"})
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# List / Get - any authenticated user (employees need to see the list to
# choose a location when creating a ticket).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "role_fixture",
    ["active_employee_user", "active_technician_user", "active_manager_user", "active_admin_user"],
)
def test_list_locations_allowed_for_every_role(
    client: TestClient,
    auth_headers: Callable[[User], dict[str, str]],
    role_fixture: str,
    request: pytest.FixtureRequest,
) -> None:
    user = request.getfixturevalue(role_fixture)
    response = client.get("/locations", headers=auth_headers(user))
    assert response.status_code == 200
    titles = {loc["title"] for loc in response.json()["data"]}
    assert {"Head Office - Floor 2", "Branch Office", "Old Warehouse"} <= titles


def test_list_locations_requires_authentication(client: TestClient) -> None:
    response = client.get("/locations")
    assert response.status_code == 401


def test_get_location_by_id_succeeds(
    client: TestClient,
    active_employee_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    head_office_location: Location,
) -> None:
    response = client.get(
        f"/locations/{head_office_location.id}", headers=auth_headers(active_employee_user)
    )
    assert response.status_code == 200
    assert response.json()["data"]["title"] == head_office_location.title


def test_get_location_unknown_id_returns_404(
    client: TestClient,
    active_employee_user: User,
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    response = client.get("/locations/999999", headers=auth_headers(active_employee_user))
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Update / Deactivate - Administrator only. There is no DELETE endpoint:
# "deactivating" is a PATCH with is_active=False.
# ---------------------------------------------------------------------------


def test_update_location_succeeds_for_admin(
    client: TestClient,
    active_admin_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    head_office_location: Location,
) -> None:
    response = client.patch(
        f"/locations/{head_office_location.id}",
        json={"title": "Head Office - Floor 3"},
        headers=auth_headers(active_admin_user),
    )
    assert response.status_code == 200
    assert response.json()["data"]["title"] == "Head Office - Floor 3"


def test_deactivate_location_succeeds_for_admin(
    client: TestClient,
    active_admin_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    head_office_location: Location,
) -> None:
    response = client.patch(
        f"/locations/{head_office_location.id}",
        json={"is_active": False},
        headers=auth_headers(active_admin_user),
    )
    assert response.status_code == 200
    body = response.json()["data"]
    assert body["is_active"] is False
    # Title is untouched by a deactivation-only patch.
    assert body["title"] == head_office_location.title


def test_reactivate_location_succeeds_for_admin(
    client: TestClient,
    active_admin_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    inactive_location: Location,
) -> None:
    response = client.patch(
        f"/locations/{inactive_location.id}",
        json={"is_active": True},
        headers=auth_headers(active_admin_user),
    )
    assert response.status_code == 200
    assert response.json()["data"]["is_active"] is True


def test_update_location_unknown_id_returns_404(
    client: TestClient,
    active_admin_user: User,
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    response = client.patch(
        "/locations/999999", json={"title": "Whatever"}, headers=auth_headers(active_admin_user)
    )
    assert response.status_code == 404


def test_update_location_duplicate_title_returns_409(
    client: TestClient,
    active_admin_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    head_office_location: Location,
    branch_office_location: Location,
) -> None:
    response = client.patch(
        f"/locations/{head_office_location.id}",
        json={"title": branch_office_location.title},
        headers=auth_headers(active_admin_user),
    )
    assert response.status_code == 409


@pytest.mark.parametrize(
    "role_fixture", ["active_employee_user", "active_technician_user", "active_manager_user"]
)
def test_update_location_forbidden_for_non_admin_roles(
    client: TestClient,
    auth_headers: Callable[[User], dict[str, str]],
    head_office_location: Location,
    role_fixture: str,
    request: pytest.FixtureRequest,
) -> None:
    user = request.getfixturevalue(role_fixture)
    response = client.patch(
        f"/locations/{head_office_location.id}",
        json={"is_active": False},
        headers=auth_headers(user),
    )
    assert response.status_code == 403


def test_update_location_partial_update_is_a_noop_when_omitted(
    client: TestClient,
    active_admin_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    head_office_location: Location,
) -> None:
    response = client.patch(
        f"/locations/{head_office_location.id}", json={}, headers=auth_headers(active_admin_user)
    )
    assert response.status_code == 200
    body = response.json()["data"]
    assert body["title"] == head_office_location.title
    assert body["is_active"] == head_office_location.is_active


# ---------------------------------------------------------------------------
# Schema-level validation (no HTTP, no DB)
# ---------------------------------------------------------------------------


def test_location_create_strips_whitespace_from_title() -> None:
    payload = LocationCreate(title="  Warehouse B  ")
    assert payload.title == "Warehouse B"


def test_location_create_rejects_empty_title() -> None:
    with pytest.raises(ValueError):
        LocationCreate(title="   ")


# ---------------------------------------------------------------------------
# Service-level: race-condition fallback for uniqueness
# ---------------------------------------------------------------------------


def test_create_location_translates_integrity_error_to_conflict() -> None:
    class RaisingRepository(FakeLocationRepository):
        def create(self, obj: Location) -> Location:
            raise IntegrityError("insert", {}, Exception("unique constraint"))

    service = LocationService(db=FakeSession(), location_repository=RaisingRepository())

    with pytest.raises(LocationTitleConflictError):
        service.create_location(LocationCreate(title="Warehouse B"))
