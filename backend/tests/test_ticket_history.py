from collections.abc import Callable

from fastapi.testclient import TestClient

from app.models.category import Category
from app.models.priority import Priority
from app.models.ticket import Ticket
from app.models.user import User


def _action_map(entries: list[dict]) -> dict[str, dict]:
    """Last entry wins per action, since some actions (e.g. status) can
    legitimately recur across a test's sequence of calls."""
    return {entry["action"]: entry for entry in entries}


def test_history_records_ticket_created(
    client: TestClient,
    active_employee_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    hardware_category: Category,
    medium_priority: Priority,
) -> None:
    create_response = client.post(
        "/ticket-new",
        json={
            "title": "Monitor flickering",
            "description": "External monitor flickers intermittently.",
            "category_id": hardware_category.id,
            "priority_id": medium_priority.id,
        },
        headers=auth_headers(active_employee_user),
    )
    created_ticket = create_response.json()["data"]
    ticket_id = created_ticket["id"]

    history_response = client.get(
        f"/tickets/{ticket_id}/history", headers=auth_headers(active_employee_user)
    )
    assert history_response.status_code == 200
    entries = history_response.json()
    assert len(entries) == 1
    entry = entries[0]
    assert entry["action"] == "ticket_created"
    assert entry["old_value"] is None
    assert entry["new_value"] == created_ticket["ticket_number"]
    assert entry["performed_by"]["id"] == active_employee_user.id
    assert entry["timestamp"] is not None


def test_history_records_title_and_description_changes(
    client: TestClient,
    active_employee_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    employee_ticket: Ticket,
) -> None:
    client.patch(
        f"/tickets/{employee_ticket.id}",
        json={"title": "New title", "description": "New description text."},
        headers=auth_headers(active_employee_user),
    )

    response = client.get(
        f"/tickets/{employee_ticket.id}/history", headers=auth_headers(active_employee_user)
    )
    actions = _action_map(response.json())
    assert actions["title"]["new_value"] == "New title"
    assert actions["description"]["new_value"] == "New description text."


def test_history_records_category_change(
    client: TestClient,
    active_employee_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    employee_ticket: Ticket,
    hardware_category: Category,
    software_category: Category,
) -> None:
    client.patch(
        f"/tickets/{employee_ticket.id}",
        json={"category_id": software_category.id},
        headers=auth_headers(active_employee_user),
    )

    response = client.get(
        f"/tickets/{employee_ticket.id}/history", headers=auth_headers(active_employee_user)
    )
    actions = _action_map(response.json())
    assert actions["category"]["old_value"] == hardware_category.name
    assert actions["category"]["new_value"] == software_category.name


def test_history_records_priority_change(
    client: TestClient,
    active_employee_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    employee_ticket: Ticket,
    high_priority: Priority,
) -> None:
    client.patch(
        f"/tickets/{employee_ticket.id}",
        json={"priority_id": high_priority.id},
        headers=auth_headers(active_employee_user),
    )

    response = client.get(
        f"/tickets/{employee_ticket.id}/history", headers=auth_headers(active_employee_user)
    )
    actions = _action_map(response.json())
    assert actions["priority"]["old_value"] == "Medium"
    assert actions["priority"]["new_value"] == "High"


def test_history_records_technician_assignment_and_status_advance(
    client: TestClient,
    active_manager_user: User,
    active_employee_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    employee_ticket: Ticket,
    active_technician_user: User,
) -> None:
    client.patch(
        f"/tickets/{employee_ticket.id}/assign",
        json={"technician_id": active_technician_user.id},
        headers=auth_headers(active_manager_user),
    )

    response = client.get(
        f"/tickets/{employee_ticket.id}/history", headers=auth_headers(active_employee_user)
    )
    actions = _action_map(response.json())
    assert actions["assigned_technician"]["old_value"] is None
    assert "Tom Technician" == actions["assigned_technician"]["new_value"]
    # NEW -> ASSIGNED auto-transition also gets its own status entry.
    assert actions["status"]["old_value"] == "NEW"
    assert actions["status"]["new_value"] == "ASSIGNED"


def test_history_records_status_change(
    client: TestClient,
    active_technician_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    assigned_ticket: Ticket,
) -> None:
    client.patch(
        f"/tickets/{assigned_ticket.id}/status",
        json={"status": "IN_PROGRESS"},
        headers=auth_headers(active_technician_user),
    )

    response = client.get(
        f"/tickets/{assigned_ticket.id}/history", headers=auth_headers(active_technician_user)
    )
    actions = _action_map(response.json())
    assert actions["status"]["old_value"] == "ASSIGNED"
    assert actions["status"]["new_value"] == "IN_PROGRESS"


def test_history_records_comment_added_edited_deleted(
    client: TestClient,
    active_employee_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    employee_ticket: Ticket,
) -> None:
    add_response = client.post(
        f"/tickets/{employee_ticket.id}/comments",
        json={"content": "First draft."},
        headers=auth_headers(active_employee_user),
    )
    comment_id = add_response.json()["id"]

    client.put(
        f"/tickets/{employee_ticket.id}/comments/{comment_id}",
        json={"content": "Edited draft."},
        headers=auth_headers(active_employee_user),
    )
    client.delete(
        f"/tickets/{employee_ticket.id}/comments/{comment_id}",
        headers=auth_headers(active_employee_user),
    )

    response = client.get(
        f"/tickets/{employee_ticket.id}/history", headers=auth_headers(active_employee_user)
    )
    actions = _action_map(response.json())
    assert actions["comment_added"]["new_value"] == "First draft."
    assert actions["comment_edited"]["old_value"] == "First draft."
    assert actions["comment_edited"]["new_value"] == "Edited draft."
    assert actions["comment_deleted"]["old_value"] == "Edited draft."
    assert actions["comment_deleted"]["new_value"] is None


def test_history_entries_ordered_chronologically(
    client: TestClient,
    active_technician_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    assigned_ticket: Ticket,
) -> None:
    client.patch(
        f"/tickets/{assigned_ticket.id}/status",
        json={"status": "IN_PROGRESS"},
        headers=auth_headers(active_technician_user),
    )
    client.patch(
        f"/tickets/{assigned_ticket.id}/status",
        json={"status": "RESOLVED"},
        headers=auth_headers(active_technician_user),
    )

    response = client.get(
        f"/tickets/{assigned_ticket.id}/history", headers=auth_headers(active_technician_user)
    )
    entries = response.json()
    values = [(e["old_value"], e["new_value"]) for e in entries]
    assert values.index(("ASSIGNED", "IN_PROGRESS")) < values.index(("IN_PROGRESS", "RESOLVED"))


def test_get_history_unknown_ticket_returns_404(
    client: TestClient,
    active_manager_user: User,
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    response = client.get("/tickets/999999/history", headers=auth_headers(active_manager_user))
    assert response.status_code == 404


def test_get_history_forbidden_for_non_owner(
    client: TestClient,
    active_employee_user_2: User,
    auth_headers: Callable[[User], dict[str, str]],
    employee_ticket: Ticket,
) -> None:
    response = client.get(
        f"/tickets/{employee_ticket.id}/history", headers=auth_headers(active_employee_user_2)
    )
    assert response.status_code == 403


def test_get_history_requires_authentication(client: TestClient, employee_ticket: Ticket) -> None:
    response = client.get(f"/tickets/{employee_ticket.id}/history")
    assert response.status_code == 401
