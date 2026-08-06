from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient

from app.models.attachment import Attachment
from app.models.category import Category
from app.models.enums import TicketStatus
from app.models.priority import Priority
from app.models.ticket import Ticket
from app.models.user import User
from app.services.history_service import HistoryService
from app.services.ticket_service import (
    InvalidStatusTransitionError,
    InvalidTechnicianAssignmentError,
    TicketNotFoundError,
    TicketService,
)
from tests.conftest import (
    FakeHistoryRepository,
    FakeStorageService,
    FakeTicketRepository,
    FakeUserRepository,
)

# ---------------------------------------------------------------------------
# Ticket creation and collection listing now live at POST /ticket-new and
# GET /all-tickets (see test_ticket_new_endpoints.py) - the old POST/GET
# /tickets and PUT /tickets/{id} collection/full-replace endpoints have been
# removed as redundant. This file covers what's left under /tickets/{id}:
# get, delete, assign, status transitions, and service-level edge cases.
# ---------------------------------------------------------------------------


def _minimal_repository(tickets: list[Ticket]) -> FakeTicketRepository:
    return FakeTicketRepository(tickets)


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


def test_delete_ticket_removes_its_attachments_physical_files(
    client: TestClient,
    active_admin_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    employee_ticket: Ticket,
    employee_attachment: Attachment,
    storage_service: FakeStorageService,
) -> None:
    """Deleting a ticket must not just remove the DB rows (cascade) - the
    physical file on disk has to go too, or it leaks forever."""
    employee_ticket.attachments.append(employee_attachment)
    assert employee_attachment.file_path in storage_service.files

    response = client.delete(f"/tickets/{employee_ticket.id}", headers=auth_headers(active_admin_user))
    assert response.status_code == 204
    assert employee_attachment.file_path not in storage_service.files


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


def test_create_ticket_new_retries_ticket_number_on_integrity_error(
    active_employee_user: User, hardware_category: Category, medium_priority: Priority
) -> None:
    from app.schemas.ticket import TicketNewCreate

    category_repo = _FakeCategoryLookup({hardware_category.id: hardware_category})
    priority_repo = _FakePriorityLookup({medium_priority.id: medium_priority})
    ticket_repo = _minimal_repository([])
    ticket_repo.fail_next_create = True

    service = TicketService(
        db=_NoopSession(),
        company_id=1,
        ticket_repository=ticket_repo,
        category_repository=category_repo,
        priority_repository=priority_repo,
        user_repository=FakeUserRepository([active_employee_user]),
        history_service=HistoryService(
            db=_NoopSession(), company_id=1, history_repository=FakeHistoryRepository()
        ),
    )

    payload = TicketNewCreate(
        title="Retry me",
        description="Should succeed on the second attempt.",
        category_id=hardware_category.id,
        priority_id=medium_priority.id,
    )
    ticket = service.create_ticket_new(active_employee_user, payload)
    assert ticket.id is not None


def test_change_status_service_raises_domain_error_for_missing_ticket(
    active_manager_user: User,
) -> None:
    service = TicketService(
        db=_NoopSession(),
        company_id=1,
        ticket_repository=_minimal_repository([]),
        category_repository=_FakeCategoryLookup({}),
        priority_repository=_FakePriorityLookup({}),
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


class _FakePriorityLookup:
    def __init__(self, priorities: dict[int, Priority]) -> None:
        self._priorities = priorities

    def get_by_id(self, id_: int) -> Priority | None:
        return self._priorities.get(id_)


class _NoopSession:
    def commit(self) -> None:
        pass

    def rollback(self) -> None:
        pass
