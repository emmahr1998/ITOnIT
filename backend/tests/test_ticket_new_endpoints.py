"""Tests for the Milestone 9 ticket endpoints: POST /ticket-new,
GET /all-tickets, and PATCH /tickets/{id}.

The exact path names (/ticket-new, /all-tickets - not nested under
/tickets) are a hard requirement, so a couple of tests assert directly on
that instead of just exercising behavior.
"""

from collections.abc import Callable

from fastapi.testclient import TestClient

from app.models.category import Category
from app.models.department import Department
from app.models.location import Location
from app.models.priority import Priority
from app.models.ticket import Ticket
from app.models.user import User

# ---------------------------------------------------------------------------
# POST /ticket-new
# ---------------------------------------------------------------------------


def test_ticket_new_creates_ticket_for_caller(
    client: TestClient,
    active_employee_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    hardware_category: Category,
    high_priority: Priority,
    head_office_location: Location,
) -> None:
    response = client.post(
        "/ticket-new",
        json={
            "title": "Keyboard keys sticking",
            "description": "Several keys need excessive force to register.",
            "location_id": head_office_location.id,
            "category_id": hardware_category.id,
            "priority_id": high_priority.id,
        },
        headers=auth_headers(active_employee_user),
    )
    assert response.status_code == 201
    body = response.json()["data"]
    assert body["created_by"]["id"] == active_employee_user.id
    assert body["location"]["id"] == head_office_location.id
    assert body["location"]["title"] == head_office_location.title
    assert body["priority"]["id"] == high_priority.id
    assert body["status"] == "NEW"


def test_ticket_new_employee_cannot_set_another_requester(
    client: TestClient,
    active_employee_user: User,
    active_employee_user_2: User,
    auth_headers: Callable[[User], dict[str, str]],
    hardware_category: Category,
    medium_priority: Priority,
) -> None:
    response = client.post(
        "/ticket-new",
        json={
            "title": "Trying to submit for someone else",
            "description": "Should be rejected.",
            "category_id": hardware_category.id,
            "priority_id": medium_priority.id,
            "requester_user_id": active_employee_user_2.id,
        },
        headers=auth_headers(active_employee_user),
    )
    assert response.status_code == 403


def test_ticket_new_manager_can_set_another_requester(
    client: TestClient,
    active_manager_user: User,
    active_employee_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    hardware_category: Category,
    medium_priority: Priority,
) -> None:
    response = client.post(
        "/ticket-new",
        json={
            "title": "Filed on behalf of an employee",
            "description": "The employee called this in over the phone.",
            "category_id": hardware_category.id,
            "priority_id": medium_priority.id,
            "requester_user_id": active_employee_user.id,
        },
        headers=auth_headers(active_manager_user),
    )
    assert response.status_code == 201
    body = response.json()["data"]
    assert body["created_by"]["id"] == active_employee_user.id


def test_ticket_new_unknown_requester_returns_400(
    client: TestClient,
    active_manager_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    hardware_category: Category,
    medium_priority: Priority,
) -> None:
    response = client.post(
        "/ticket-new",
        json={
            "title": "x",
            "description": "y",
            "category_id": hardware_category.id,
            "priority_id": medium_priority.id,
            "requester_user_id": 999999,
        },
        headers=auth_headers(active_manager_user),
    )
    assert response.status_code == 400


def test_ticket_new_unknown_category_returns_400(
    client: TestClient,
    active_employee_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    medium_priority: Priority,
) -> None:
    response = client.post(
        "/ticket-new",
        json={
            "title": "x",
            "description": "y",
            "category_id": 999999,
            "priority_id": medium_priority.id,
        },
        headers=auth_headers(active_employee_user),
    )
    assert response.status_code == 400


def test_ticket_new_forbidden_for_technician(
    client: TestClient,
    active_technician_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    hardware_category: Category,
    medium_priority: Priority,
) -> None:
    response = client.post(
        "/ticket-new",
        json={
            "title": "x",
            "description": "y",
            "category_id": hardware_category.id,
            "priority_id": medium_priority.id,
        },
        headers=auth_headers(active_technician_user),
    )
    assert response.status_code == 403


def test_ticket_new_requires_authentication(client: TestClient) -> None:
    response = client.post(
        "/ticket-new", json={"title": "x", "description": "y", "category_id": 1, "priority_id": 1}
    )
    assert response.status_code == 401


def test_ticket_new_unknown_priority_returns_400(
    client: TestClient,
    active_employee_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    hardware_category: Category,
) -> None:
    response = client.post(
        "/ticket-new",
        json={
            "title": "x",
            "description": "y",
            "category_id": hardware_category.id,
            "priority_id": 999999,
        },
        headers=auth_headers(active_employee_user),
    )
    assert response.status_code == 400


def test_ticket_new_rejects_inactive_location(
    client: TestClient,
    active_employee_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    hardware_category: Category,
    medium_priority: Priority,
    inactive_location: Location,
) -> None:
    response = client.post(
        "/ticket-new",
        json={
            "title": "x",
            "description": "y",
            "category_id": hardware_category.id,
            "priority_id": medium_priority.id,
            "location_id": inactive_location.id,
        },
        headers=auth_headers(active_employee_user),
    )
    assert response.status_code == 400


def test_ticket_new_missing_priority_id_returns_422(
    client: TestClient,
    active_employee_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    hardware_category: Category,
) -> None:
    response = client.post(
        "/ticket-new",
        json={"title": "x", "description": "y", "category_id": hardware_category.id},
        headers=auth_headers(active_employee_user),
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# GET /all-tickets
# ---------------------------------------------------------------------------


def test_all_tickets_employee_sees_only_own(
    client: TestClient,
    active_employee_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    employee_ticket: Ticket,
    assigned_ticket: Ticket,
) -> None:
    response = client.get("/all-tickets", headers=auth_headers(active_employee_user))
    assert response.status_code == 200
    ids = {t["id"] for t in response.json()["data"]}
    assert ids == {employee_ticket.id, assigned_ticket.id}


def test_all_tickets_employee_2_sees_none(
    client: TestClient,
    active_employee_user_2: User,
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    response = client.get("/all-tickets", headers=auth_headers(active_employee_user_2))
    assert response.status_code == 200
    assert response.json()["data"] == []


def test_all_tickets_technician_sees_only_assigned(
    client: TestClient,
    active_technician_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    assigned_ticket: Ticket,
) -> None:
    response = client.get("/all-tickets", headers=auth_headers(active_technician_user))
    assert response.status_code == 200
    ids = {t["id"] for t in response.json()["data"]}
    assert ids == {assigned_ticket.id}


def test_all_tickets_technician_2_sees_none(
    client: TestClient,
    active_technician_user_2: User,
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    response = client.get("/all-tickets", headers=auth_headers(active_technician_user_2))
    assert response.status_code == 200
    assert response.json()["data"] == []


def test_all_tickets_status_filter_narrows_results(
    client: TestClient,
    active_manager_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    assigned_ticket: Ticket,
) -> None:
    response = client.get(
        "/all-tickets", params={"status": "ASSIGNED"}, headers=auth_headers(active_manager_user)
    )
    assert response.status_code == 200
    ids = {t["id"] for t in response.json()["data"]}
    assert ids == {assigned_ticket.id}


def test_all_tickets_manager_sees_all(
    client: TestClient,
    active_manager_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    employee_ticket: Ticket,
    assigned_ticket: Ticket,
) -> None:
    response = client.get("/all-tickets", headers=auth_headers(active_manager_user))
    assert response.status_code == 200
    ids = {t["id"] for t in response.json()["data"]}
    assert ids == {employee_ticket.id, assigned_ticket.id}


def test_all_tickets_supports_search_by_title(
    client: TestClient,
    active_manager_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    employee_ticket: Ticket,
    assigned_ticket: Ticket,
) -> None:
    response = client.get(
        "/all-tickets", params={"search": "VPN"}, headers=auth_headers(active_manager_user)
    )
    assert response.status_code == 200
    ids = {t["id"] for t in response.json()["data"]}
    assert ids == {assigned_ticket.id}


def test_all_tickets_supports_priority_filter(
    client: TestClient,
    active_manager_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    employee_ticket: Ticket,
    assigned_ticket: Ticket,
    high_priority: Priority,
) -> None:
    response = client.get(
        "/all-tickets",
        params={"priority_id": high_priority.id},
        headers=auth_headers(active_manager_user),
    )
    assert response.status_code == 200
    ids = {t["id"] for t in response.json()["data"]}
    assert ids == {assigned_ticket.id}


def test_all_tickets_supports_department_filter(
    client: TestClient,
    active_manager_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    employee_ticket: Ticket,
    assigned_ticket: Ticket,
    it_department: Department,
) -> None:
    """Both fixture tickets are created by active_employee_user, who is in
    the IT department - filtering by that department returns both."""
    response = client.get(
        "/all-tickets",
        params={"department_id": it_department.id},
        headers=auth_headers(active_manager_user),
    )
    assert response.status_code == 200
    ids = {t["id"] for t in response.json()["data"]}
    assert ids == {employee_ticket.id, assigned_ticket.id}


def test_all_tickets_supports_pagination(
    client: TestClient,
    active_manager_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    employee_ticket: Ticket,
    assigned_ticket: Ticket,
) -> None:
    response = client.get(
        "/all-tickets", params={"limit": 1, "skip": 0}, headers=auth_headers(active_manager_user)
    )
    assert response.status_code == 200
    assert len(response.json()["data"]) == 1


def test_all_tickets_employee_cannot_bypass_scope_via_filter(
    client: TestClient,
    active_employee_user_2: User,
    active_employee_user: User,
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    response = client.get(
        "/all-tickets",
        params={"requester": active_employee_user.id},
        headers=auth_headers(active_employee_user_2),
    )
    assert response.status_code == 200
    assert response.json()["data"] == []


def test_all_tickets_requires_authentication(client: TestClient) -> None:
    response = client.get("/all-tickets")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# PATCH /tickets/{id}
# ---------------------------------------------------------------------------


def test_patch_ticket_partial_update_changes_only_given_fields(
    client: TestClient,
    active_employee_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    employee_ticket: Ticket,
    branch_office_location: Location,
) -> None:
    response = client.patch(
        f"/tickets/{employee_ticket.id}",
        json={"location_id": branch_office_location.id},
        headers=auth_headers(active_employee_user),
    )
    assert response.status_code == 200
    body = response.json()["data"]
    assert body["location"]["id"] == branch_office_location.id
    assert body["title"] == employee_ticket.title
    assert body["description"] == employee_ticket.description


def test_patch_ticket_rejects_inactive_location(
    client: TestClient,
    active_employee_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    employee_ticket: Ticket,
    inactive_location: Location,
) -> None:
    response = client.patch(
        f"/tickets/{employee_ticket.id}",
        json={"location_id": inactive_location.id},
        headers=auth_headers(active_employee_user),
    )
    assert response.status_code == 400


def test_patch_ticket_changes_priority(
    client: TestClient,
    active_employee_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    employee_ticket: Ticket,
    high_priority: Priority,
) -> None:
    response = client.patch(
        f"/tickets/{employee_ticket.id}",
        json={"priority_id": high_priority.id},
        headers=auth_headers(active_employee_user),
    )
    assert response.status_code == 200
    assert response.json()["data"]["priority"]["id"] == high_priority.id


def test_patch_ticket_empty_body_is_a_noop(
    client: TestClient,
    active_employee_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    employee_ticket: Ticket,
) -> None:
    response = client.patch(
        f"/tickets/{employee_ticket.id}", json={}, headers=auth_headers(active_employee_user)
    )
    assert response.status_code == 200
    body = response.json()["data"]
    assert body["title"] == employee_ticket.title
    assert body["status"] == employee_ticket.status.value


def test_patch_ticket_does_not_touch_status_or_assignment(
    client: TestClient,
    active_employee_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    employee_ticket: Ticket,
) -> None:
    response = client.patch(
        f"/tickets/{employee_ticket.id}",
        json={"title": "Updated title only"},
        headers=auth_headers(active_employee_user),
    )
    assert response.status_code == 200
    body = response.json()["data"]
    assert body["status"] == "NEW"
    assert body["assigned_technician"] is None


def test_patch_ticket_forbidden_for_other_employee(
    client: TestClient,
    active_employee_user_2: User,
    auth_headers: Callable[[User], dict[str, str]],
    employee_ticket: Ticket,
) -> None:
    response = client.patch(
        f"/tickets/{employee_ticket.id}",
        json={"title": "Hijacked"},
        headers=auth_headers(active_employee_user_2),
    )
    assert response.status_code == 403


def test_patch_ticket_owner_forbidden_once_status_past_new(
    client: TestClient,
    active_employee_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    assigned_ticket: Ticket,
) -> None:
    response = client.patch(
        f"/tickets/{assigned_ticket.id}",
        json={"title": "Trying to edit after assignment"},
        headers=auth_headers(active_employee_user),
    )
    assert response.status_code == 409


def test_patch_ticket_unknown_category_returns_400(
    client: TestClient,
    active_employee_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    employee_ticket: Ticket,
) -> None:
    response = client.patch(
        f"/tickets/{employee_ticket.id}",
        json={"category_id": 999999},
        headers=auth_headers(active_employee_user),
    )
    assert response.status_code == 400


def test_patch_ticket_unknown_priority_returns_400(
    client: TestClient,
    active_employee_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    employee_ticket: Ticket,
) -> None:
    response = client.patch(
        f"/tickets/{employee_ticket.id}",
        json={"priority_id": 999999},
        headers=auth_headers(active_employee_user),
    )
    assert response.status_code == 400


def test_patch_ticket_assigned_technician_succeeds(
    client: TestClient,
    active_technician_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    assigned_ticket: Ticket,
) -> None:
    response = client.patch(
        f"/tickets/{assigned_ticket.id}",
        json={"title": "Diagnosed root cause"},
        headers=auth_headers(active_technician_user),
    )
    assert response.status_code == 200
    assert response.json()["data"]["title"] == "Diagnosed root cause"


def test_patch_ticket_forbidden_for_unassigned_technician(
    client: TestClient,
    active_technician_user_2: User,
    auth_headers: Callable[[User], dict[str, str]],
    assigned_ticket: Ticket,
) -> None:
    response = client.patch(
        f"/tickets/{assigned_ticket.id}",
        json={"title": "x"},
        headers=auth_headers(active_technician_user_2),
    )
    assert response.status_code == 403


def test_patch_ticket_manager_can_edit_any_ticket_any_status(
    client: TestClient,
    active_manager_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    assigned_ticket: Ticket,
) -> None:
    response = client.patch(
        f"/tickets/{assigned_ticket.id}",
        json={"title": "Manager override"},
        headers=auth_headers(active_manager_user),
    )
    assert response.status_code == 200
    assert response.json()["data"]["title"] == "Manager override"


def test_patch_ticket_unknown_id_returns_404(
    client: TestClient,
    active_manager_user: User,
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    response = client.patch(
        "/tickets/999999", json={"title": "x"}, headers=auth_headers(active_manager_user)
    )
    assert response.status_code == 404


def test_patch_ticket_records_history(
    client: TestClient,
    active_employee_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    employee_ticket: Ticket,
) -> None:
    client.patch(
        f"/tickets/{employee_ticket.id}",
        json={"title": "History-tracked change"},
        headers=auth_headers(active_employee_user),
    )
    history_response = client.get(
        f"/tickets/{employee_ticket.id}/history", headers=auth_headers(active_employee_user)
    )
    actions = {entry["action"]: entry for entry in history_response.json()}
    assert actions["title"]["new_value"] == "History-tracked change"


def test_patch_ticket_requires_authentication(client: TestClient, employee_ticket: Ticket) -> None:
    response = client.patch(f"/tickets/{employee_ticket.id}", json={"title": "x"})
    assert response.status_code == 401
