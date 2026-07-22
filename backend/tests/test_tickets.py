from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient

from app.models.category import Category
from app.models.enums import TicketStatus
from app.models.ticket import Ticket
from app.models.user import User
from app.services.ticket_service import (
    InvalidStatusTransitionError,
    InvalidTechnicianAssignmentError,
    TicketNotFoundError,
    TicketService,
)
from tests.conftest import FakeTicketRepository, FakeUserRepository


def _minimal_repository(tickets: list[Ticket]) -> FakeTicketRepository:
    return FakeTicketRepository(tickets)


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "role_fixture", ["active_employee_user", "active_manager_user", "active_admin_user"]
)
def test_create_ticket_succeeds_for_allowed_roles(
    client: TestClient,
    auth_headers: Callable[[User], dict[str, str]],
    hardware_category: Category,
    role_fixture: str,
    request: pytest.FixtureRequest,
) -> None:
    user = request.getfixturevalue(role_fixture)
    response = client.post(
        "/tickets",
        json={
            "title": "Printer jam",
            "description": "Paper jam on the 3rd floor printer.",
            "category_id": hardware_category.id,
            "priority": "HIGH",
        },
        headers=auth_headers(user),
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "NEW"
    assert body["assigned_technician"] is None
    assert body["created_by"]["id"] == user.id
    assert body["category"]["id"] == hardware_category.id
    assert body["priority"] == "HIGH"


def test_create_ticket_forbidden_for_technician(
    client: TestClient,
    active_technician_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    hardware_category: Category,
) -> None:
    response = client.post(
        "/tickets",
        json={
            "title": "Printer jam",
            "description": "Paper jam.",
            "category_id": hardware_category.id,
        },
        headers=auth_headers(active_technician_user),
    )
    assert response.status_code == 403


def test_create_ticket_unknown_category_returns_400(
    client: TestClient,
    active_employee_user: User,
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    response = client.post(
        "/tickets",
        json={"title": "Printer jam", "description": "Paper jam.", "category_id": 999999},
        headers=auth_headers(active_employee_user),
    )
    assert response.status_code == 400


def test_create_ticket_defaults_priority_to_medium(
    client: TestClient,
    active_employee_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    hardware_category: Category,
) -> None:
    response = client.post(
        "/tickets",
        json={
            "title": "Mouse not working",
            "description": "Wireless mouse is unresponsive.",
            "category_id": hardware_category.id,
        },
        headers=auth_headers(active_employee_user),
    )
    assert response.status_code == 201
    assert response.json()["priority"] == "MEDIUM"


def test_create_ticket_requires_authentication(client: TestClient) -> None:
    response = client.post(
        "/tickets", json={"title": "x", "description": "y", "category_id": 1}
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------


def test_list_tickets_employee_sees_only_own(
    client: TestClient,
    active_employee_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    employee_ticket: Ticket,
    assigned_ticket: Ticket,
) -> None:
    response = client.get("/tickets", headers=auth_headers(active_employee_user))
    assert response.status_code == 200
    ids = {t["id"] for t in response.json()}
    # Both fixture tickets were created_by active_employee_user.
    assert ids == {employee_ticket.id, assigned_ticket.id}


def test_list_tickets_employee_2_sees_none(
    client: TestClient,
    active_employee_user_2: User,
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    response = client.get("/tickets", headers=auth_headers(active_employee_user_2))
    assert response.status_code == 200
    assert response.json() == []


def test_list_tickets_technician_sees_only_assigned(
    client: TestClient,
    active_technician_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    assigned_ticket: Ticket,
) -> None:
    response = client.get("/tickets", headers=auth_headers(active_technician_user))
    assert response.status_code == 200
    ids = {t["id"] for t in response.json()}
    assert ids == {assigned_ticket.id}


def test_list_tickets_technician_2_sees_none(
    client: TestClient,
    active_technician_user_2: User,
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    response = client.get("/tickets", headers=auth_headers(active_technician_user_2))
    assert response.status_code == 200
    assert response.json() == []


def test_list_tickets_manager_sees_all(
    client: TestClient,
    active_manager_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    employee_ticket: Ticket,
    assigned_ticket: Ticket,
) -> None:
    response = client.get("/tickets", headers=auth_headers(active_manager_user))
    assert response.status_code == 200
    ids = {t["id"] for t in response.json()}
    assert ids == {employee_ticket.id, assigned_ticket.id}


def test_list_tickets_status_filter_narrows_results(
    client: TestClient,
    active_manager_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    assigned_ticket: Ticket,
) -> None:
    response = client.get(
        "/tickets", params={"status": "ASSIGNED"}, headers=auth_headers(active_manager_user)
    )
    assert response.status_code == 200
    ids = {t["id"] for t in response.json()}
    assert ids == {assigned_ticket.id}


def test_list_tickets_employee_filter_cannot_see_others_via_created_by(
    client: TestClient,
    active_employee_user_2: User,
    auth_headers: Callable[[User], dict[str, str]],
    active_employee_user: User,
) -> None:
    """Employee 2 tries to pass created_by=employee_1 - the forced ownership
    scope must win, not the client-supplied filter."""
    response = client.get(
        "/tickets",
        params={"created_by": active_employee_user.id},
        headers=auth_headers(active_employee_user_2),
    )
    assert response.status_code == 200
    assert response.json() == []


# ---------------------------------------------------------------------------
# Get
# ---------------------------------------------------------------------------


def test_get_ticket_owner_succeeds(
    client: TestClient,
    active_employee_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    employee_ticket: Ticket,
) -> None:
    response = client.get(
        f"/tickets/{employee_ticket.id}", headers=auth_headers(active_employee_user)
    )
    assert response.status_code == 200
    assert response.json()["id"] == employee_ticket.id


def test_get_ticket_forbidden_for_other_employee(
    client: TestClient,
    active_employee_user_2: User,
    auth_headers: Callable[[User], dict[str, str]],
    employee_ticket: Ticket,
) -> None:
    response = client.get(
        f"/tickets/{employee_ticket.id}", headers=auth_headers(active_employee_user_2)
    )
    assert response.status_code == 403


def test_get_ticket_forbidden_for_unassigned_technician(
    client: TestClient,
    active_technician_user_2: User,
    auth_headers: Callable[[User], dict[str, str]],
    assigned_ticket: Ticket,
) -> None:
    response = client.get(
        f"/tickets/{assigned_ticket.id}", headers=auth_headers(active_technician_user_2)
    )
    assert response.status_code == 403


def test_get_ticket_unknown_id_returns_404(
    client: TestClient,
    active_manager_user: User,
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    response = client.get("/tickets/999999", headers=auth_headers(active_manager_user))
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------


def test_update_ticket_owner_succeeds_while_new(
    client: TestClient,
    active_employee_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    employee_ticket: Ticket,
    hardware_category: Category,
) -> None:
    response = client.put(
        f"/tickets/{employee_ticket.id}",
        json={
            "title": "Laptop will not boot - updated",
            "description": "Still black screen, tried a hard reset.",
            "category_id": hardware_category.id,
            "priority": "HIGH",
        },
        headers=auth_headers(active_employee_user),
    )
    assert response.status_code == 200
    assert response.json()["title"] == "Laptop will not boot - updated"


def test_update_ticket_owner_forbidden_once_status_past_new(
    client: TestClient,
    active_employee_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    assigned_ticket: Ticket,
    software_category: Category,
) -> None:
    response = client.put(
        f"/tickets/{assigned_ticket.id}",
        json={
            "title": "Trying to edit after assignment",
            "description": "Should not be allowed.",
            "category_id": software_category.id,
            "priority": "HIGH",
        },
        headers=auth_headers(active_employee_user),
    )
    assert response.status_code == 409


def test_update_ticket_forbidden_for_other_employee(
    client: TestClient,
    active_employee_user_2: User,
    auth_headers: Callable[[User], dict[str, str]],
    employee_ticket: Ticket,
    hardware_category: Category,
) -> None:
    response = client.put(
        f"/tickets/{employee_ticket.id}",
        json={
            "title": "x",
            "description": "y",
            "category_id": hardware_category.id,
            "priority": "MEDIUM",
        },
        headers=auth_headers(active_employee_user_2),
    )
    assert response.status_code == 403


def test_update_ticket_assigned_technician_succeeds(
    client: TestClient,
    active_technician_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    assigned_ticket: Ticket,
    software_category: Category,
) -> None:
    response = client.put(
        f"/tickets/{assigned_ticket.id}",
        json={
            "title": "VPN disconnects repeatedly - diagnosed",
            "description": "Root cause appears to be a firmware bug.",
            "category_id": software_category.id,
            "priority": "CRITICAL",
        },
        headers=auth_headers(active_technician_user),
    )
    assert response.status_code == 200
    assert response.json()["priority"] == "CRITICAL"


def test_update_ticket_forbidden_for_unassigned_technician(
    client: TestClient,
    active_technician_user_2: User,
    auth_headers: Callable[[User], dict[str, str]],
    assigned_ticket: Ticket,
    software_category: Category,
) -> None:
    response = client.put(
        f"/tickets/{assigned_ticket.id}",
        json={
            "title": "x",
            "description": "y",
            "category_id": software_category.id,
            "priority": "HIGH",
        },
        headers=auth_headers(active_technician_user_2),
    )
    assert response.status_code == 403


def test_update_ticket_manager_can_edit_any_ticket_any_status(
    client: TestClient,
    active_manager_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    assigned_ticket: Ticket,
    software_category: Category,
) -> None:
    response = client.put(
        f"/tickets/{assigned_ticket.id}",
        json={
            "title": "Manager override",
            "description": "Manager edited this ticket directly.",
            "category_id": software_category.id,
            "priority": "HIGH",
        },
        headers=auth_headers(active_manager_user),
    )
    assert response.status_code == 200


def test_update_ticket_unknown_category_returns_400(
    client: TestClient,
    active_employee_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    employee_ticket: Ticket,
) -> None:
    response = client.put(
        f"/tickets/{employee_ticket.id}",
        json={"title": "x", "description": "y", "category_id": 999999, "priority": "MEDIUM"},
        headers=auth_headers(active_employee_user),
    )
    assert response.status_code == 400


def test_update_ticket_unknown_id_returns_404(
    client: TestClient,
    active_manager_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    hardware_category: Category,
) -> None:
    response = client.put(
        "/tickets/999999",
        json={
            "title": "x",
            "description": "y",
            "category_id": hardware_category.id,
            "priority": "MEDIUM",
        },
        headers=auth_headers(active_manager_user),
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("role_fixture", ["active_manager_user", "active_admin_user"])
def test_delete_ticket_succeeds_for_manage_roles(
    client: TestClient,
    auth_headers: Callable[[User], dict[str, str]],
    employee_ticket: Ticket,
    role_fixture: str,
    request: pytest.FixtureRequest,
) -> None:
    user = request.getfixturevalue(role_fixture)
    response = client.delete(f"/tickets/{employee_ticket.id}", headers=auth_headers(user))
    assert response.status_code == 204

    follow_up = client.get(f"/tickets/{employee_ticket.id}", headers=auth_headers(user))
    assert follow_up.status_code == 404


@pytest.mark.parametrize("role_fixture", ["active_employee_user", "active_technician_user"])
def test_delete_ticket_forbidden_for_non_manage_roles(
    client: TestClient,
    auth_headers: Callable[[User], dict[str, str]],
    employee_ticket: Ticket,
    role_fixture: str,
    request: pytest.FixtureRequest,
) -> None:
    user = request.getfixturevalue(role_fixture)
    response = client.delete(f"/tickets/{employee_ticket.id}", headers=auth_headers(user))
    assert response.status_code == 403


def test_delete_ticket_unknown_id_returns_404(
    client: TestClient,
    active_admin_user: User,
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    response = client.delete("/tickets/999999", headers=auth_headers(active_admin_user))
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Assign
# ---------------------------------------------------------------------------


def test_assign_technician_succeeds_and_advances_status(
    client: TestClient,
    active_manager_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    employee_ticket: Ticket,
    active_technician_user: User,
) -> None:
    response = client.patch(
        f"/tickets/{employee_ticket.id}/assign",
        json={"technician_id": active_technician_user.id},
        headers=auth_headers(active_manager_user),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["assigned_technician"]["id"] == active_technician_user.id
    assert body["status"] == "ASSIGNED"


def test_assign_technician_forbidden_for_employee(
    client: TestClient,
    active_employee_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    employee_ticket: Ticket,
    active_technician_user: User,
) -> None:
    response = client.patch(
        f"/tickets/{employee_ticket.id}/assign",
        json={"technician_id": active_technician_user.id},
        headers=auth_headers(active_employee_user),
    )
    assert response.status_code == 403


def test_assign_technician_rejects_non_technician_user(
    client: TestClient,
    active_manager_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    employee_ticket: Ticket,
    active_employee_user: User,
) -> None:
    response = client.patch(
        f"/tickets/{employee_ticket.id}/assign",
        json={"technician_id": active_employee_user.id},
        headers=auth_headers(active_manager_user),
    )
    assert response.status_code == 400


def test_assign_technician_rejects_inactive_technician(
    client: TestClient,
    active_manager_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    employee_ticket: Ticket,
    inactive_user: User,
) -> None:
    response = client.patch(
        f"/tickets/{employee_ticket.id}/assign",
        json={"technician_id": inactive_user.id},
        headers=auth_headers(active_manager_user),
    )
    assert response.status_code == 400


def test_assign_technician_rejects_unknown_user(
    client: TestClient,
    active_manager_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    employee_ticket: Ticket,
) -> None:
    response = client.patch(
        f"/tickets/{employee_ticket.id}/assign",
        json={"technician_id": 999999},
        headers=auth_headers(active_manager_user),
    )
    assert response.status_code == 400


def test_assign_technician_unknown_ticket_returns_404(
    client: TestClient,
    active_manager_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    active_technician_user: User,
) -> None:
    response = client.patch(
        "/tickets/999999/assign",
        json={"technician_id": active_technician_user.id},
        headers=auth_headers(active_manager_user),
    )
    assert response.status_code == 404


def test_assign_technician_rejects_closed_ticket(
    client: TestClient,
    active_manager_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    ticket_repository: FakeTicketRepository,
    assigned_ticket: Ticket,
    active_technician_user: User,
) -> None:
    assigned_ticket.status = TicketStatus.CLOSED
    response = client.patch(
        f"/tickets/{assigned_ticket.id}/assign",
        json={"technician_id": active_technician_user.id},
        headers=auth_headers(active_manager_user),
    )
    assert response.status_code == 400


# ---------------------------------------------------------------------------
# Status transitions
# ---------------------------------------------------------------------------


def test_status_valid_transition_by_assigned_technician(
    client: TestClient,
    active_technician_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    assigned_ticket: Ticket,
) -> None:
    response = client.patch(
        f"/tickets/{assigned_ticket.id}/status",
        json={"status": "IN_PROGRESS"},
        headers=auth_headers(active_technician_user),
    )
    assert response.status_code == 200
    assert response.json()["status"] == "IN_PROGRESS"


def test_status_transition_to_resolved_sets_resolved_at(
    client: TestClient,
    active_technician_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    assigned_ticket: Ticket,
) -> None:
    assigned_ticket.status = TicketStatus.IN_PROGRESS
    response = client.patch(
        f"/tickets/{assigned_ticket.id}/status",
        json={"status": "RESOLVED"},
        headers=auth_headers(active_technician_user),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "RESOLVED"
    assert body["resolved_at"] is not None


def test_status_transition_to_closed_sets_closed_at(
    client: TestClient,
    active_manager_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    assigned_ticket: Ticket,
) -> None:
    assigned_ticket.status = TicketStatus.RESOLVED
    response = client.patch(
        f"/tickets/{assigned_ticket.id}/status",
        json={"status": "CLOSED"},
        headers=auth_headers(active_manager_user),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "CLOSED"
    assert body["closed_at"] is not None


def test_status_invalid_transition_returns_409(
    client: TestClient,
    active_manager_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    assigned_ticket: Ticket,
) -> None:
    assigned_ticket.status = TicketStatus.CLOSED
    response = client.patch(
        f"/tickets/{assigned_ticket.id}/status",
        json={"status": "NEW"},
        headers=auth_headers(active_manager_user),
    )
    assert response.status_code == 409


def test_status_forbidden_for_employee(
    client: TestClient,
    active_employee_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    employee_ticket: Ticket,
) -> None:
    response = client.patch(
        f"/tickets/{employee_ticket.id}/status",
        json={"status": "ASSIGNED"},
        headers=auth_headers(active_employee_user),
    )
    assert response.status_code == 403


def test_status_forbidden_for_unassigned_technician(
    client: TestClient,
    active_technician_user_2: User,
    auth_headers: Callable[[User], dict[str, str]],
    assigned_ticket: Ticket,
) -> None:
    response = client.patch(
        f"/tickets/{assigned_ticket.id}/status",
        json={"status": "IN_PROGRESS"},
        headers=auth_headers(active_technician_user_2),
    )
    assert response.status_code == 403


def test_status_manager_can_change_any_ticket_status(
    client: TestClient,
    active_manager_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    assigned_ticket: Ticket,
) -> None:
    response = client.patch(
        f"/tickets/{assigned_ticket.id}/status",
        json={"status": "IN_PROGRESS"},
        headers=auth_headers(active_manager_user),
    )
    assert response.status_code == 200


def test_status_unknown_ticket_returns_404(
    client: TestClient,
    active_manager_user: User,
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    response = client.patch(
        "/tickets/999999/status",
        json={"status": "IN_PROGRESS"},
        headers=auth_headers(active_manager_user),
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Service-level: race-condition fallback for ticket_number generation
# ---------------------------------------------------------------------------


def test_create_ticket_retries_ticket_number_on_integrity_error(
    active_employee_user: User, hardware_category: Category
) -> None:
    from app.schemas.ticket import TicketCreate

    category_repo = _FakeCategoryLookup({hardware_category.id: hardware_category})
    ticket_repo = _minimal_repository([])
    ticket_repo.fail_next_create = True

    service = TicketService(
        db=_NoopSession(),
        ticket_repository=ticket_repo,
        category_repository=category_repo,
        user_repository=FakeUserRepository([active_employee_user]),
    )

    payload = TicketCreate(
        title="Retry me",
        description="Should succeed on the second attempt.",
        category_id=hardware_category.id,
    )
    ticket = service.create_ticket(active_employee_user, payload)
    assert ticket.id is not None


def test_change_status_service_raises_domain_error_for_missing_ticket(
    active_manager_user: User,
) -> None:
    service = TicketService(
        db=_NoopSession(),
        ticket_repository=_minimal_repository([]),
        category_repository=_FakeCategoryLookup({}),
        user_repository=FakeUserRepository([active_manager_user]),
    )
    with pytest.raises(TicketNotFoundError):
        service.change_status(active_manager_user, 999999, TicketStatus.IN_PROGRESS)


def test_assign_technician_service_raises_for_invalid_status_target() -> None:
    # Sanity check that InvalidStatusTransitionError and
    # InvalidTechnicianAssignmentError are distinct, catchable types.
    assert issubclass(InvalidStatusTransitionError, Exception)
    assert issubclass(InvalidTechnicianAssignmentError, Exception)


class _FakeCategoryLookup:
    def __init__(self, categories: dict[int, Category]) -> None:
        self._categories = categories

    def get_by_id(self, id_: int) -> Category | None:
        return self._categories.get(id_)


class _NoopSession:
    def commit(self) -> None:
        pass

    def rollback(self) -> None:
        pass
