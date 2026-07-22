from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient

from app.models.comment import Comment
from app.models.ticket import Ticket
from app.models.user import User
from app.schemas.comment import CommentCreate

# ---------------------------------------------------------------------------
# Add
# ---------------------------------------------------------------------------


def test_add_comment_succeeds_for_owning_employee(
    client: TestClient,
    active_employee_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    employee_ticket: Ticket,
) -> None:
    response = client.post(
        f"/tickets/{employee_ticket.id}/comments",
        json={"content": "Adding some context."},
        headers=auth_headers(active_employee_user),
    )
    assert response.status_code == 201
    body = response.json()
    assert body["content"] == "Adding some context."
    assert body["author"]["id"] == active_employee_user.id
    assert body["ticket_id"] == employee_ticket.id
    assert body["updated_at"] is None


def test_add_comment_succeeds_for_assigned_technician(
    client: TestClient,
    active_technician_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    assigned_ticket: Ticket,
) -> None:
    response = client.post(
        f"/tickets/{assigned_ticket.id}/comments",
        json={"content": "Looking into this now."},
        headers=auth_headers(active_technician_user),
    )
    assert response.status_code == 201


@pytest.mark.parametrize("role_fixture", ["active_manager_user", "active_admin_user"])
def test_add_comment_succeeds_for_manage_roles_on_any_ticket(
    client: TestClient,
    auth_headers: Callable[[User], dict[str, str]],
    employee_ticket: Ticket,
    role_fixture: str,
    request: pytest.FixtureRequest,
) -> None:
    user = request.getfixturevalue(role_fixture)
    response = client.post(
        f"/tickets/{employee_ticket.id}/comments",
        json={"content": "Manager checking in."},
        headers=auth_headers(user),
    )
    assert response.status_code == 201


def test_add_comment_forbidden_for_other_employee(
    client: TestClient,
    active_employee_user_2: User,
    auth_headers: Callable[[User], dict[str, str]],
    employee_ticket: Ticket,
) -> None:
    response = client.post(
        f"/tickets/{employee_ticket.id}/comments",
        json={"content": "Trying to comment on someone else's ticket."},
        headers=auth_headers(active_employee_user_2),
    )
    assert response.status_code == 403


def test_add_comment_forbidden_for_unassigned_technician(
    client: TestClient,
    active_technician_user_2: User,
    auth_headers: Callable[[User], dict[str, str]],
    assigned_ticket: Ticket,
) -> None:
    response = client.post(
        f"/tickets/{assigned_ticket.id}/comments",
        json={"content": "Not my ticket."},
        headers=auth_headers(active_technician_user_2),
    )
    assert response.status_code == 403


def test_add_comment_unknown_ticket_returns_404(
    client: TestClient,
    active_employee_user: User,
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    response = client.post(
        "/tickets/999999/comments",
        json={"content": "Doesn't matter."},
        headers=auth_headers(active_employee_user),
    )
    assert response.status_code == 404


def test_add_comment_requires_authentication(client: TestClient, employee_ticket: Ticket) -> None:
    response = client.post(
        f"/tickets/{employee_ticket.id}/comments", json={"content": "No token."}
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------


def test_list_comments_visible_to_owner(
    client: TestClient,
    active_employee_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    employee_ticket: Ticket,
    employee_comment: Comment,
) -> None:
    response = client.get(
        f"/tickets/{employee_ticket.id}/comments", headers=auth_headers(active_employee_user)
    )
    assert response.status_code == 200
    ids = {c["id"] for c in response.json()}
    assert employee_comment.id in ids


def test_list_comments_forbidden_for_other_employee(
    client: TestClient,
    active_employee_user_2: User,
    auth_headers: Callable[[User], dict[str, str]],
    employee_ticket: Ticket,
) -> None:
    response = client.get(
        f"/tickets/{employee_ticket.id}/comments", headers=auth_headers(active_employee_user_2)
    )
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------


def test_edit_own_comment_succeeds(
    client: TestClient,
    active_employee_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    employee_ticket: Ticket,
    employee_comment: Comment,
) -> None:
    response = client.put(
        f"/tickets/{employee_ticket.id}/comments/{employee_comment.id}",
        json={"content": "Edited content."},
        headers=auth_headers(active_employee_user),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["content"] == "Edited content."
    assert body["updated_at"] is not None


def test_edit_others_comment_forbidden_via_ticket_view_gate(
    client: TestClient,
    active_employee_user_2: User,
    auth_headers: Callable[[User], dict[str, str]],
    employee_ticket: Ticket,
    employee_comment: Comment,
) -> None:
    """A user who cannot even view the ticket is blocked before comment
    ownership is ever considered."""
    response = client.put(
        f"/tickets/{employee_ticket.id}/comments/{employee_comment.id}",
        json={"content": "Trying to edit someone else's comment."},
        headers=auth_headers(active_employee_user_2),
    )
    assert response.status_code == 403


def test_edit_others_comment_forbidden_via_comment_ownership(
    client: TestClient,
    active_technician_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    assigned_ticket: Ticket,
    assigned_ticket_comment: Comment,
) -> None:
    """active_technician_user CAN view assigned_ticket (it's assigned to
    them) but did not author assigned_ticket_comment - this exercises
    CommentService's own ownership check, distinct from the ticket-view gate."""
    response = client.put(
        f"/tickets/{assigned_ticket.id}/comments/{assigned_ticket_comment.id}",
        json={"content": "Trying to edit the employee's comment."},
        headers=auth_headers(active_technician_user),
    )
    assert response.status_code == 403


@pytest.mark.parametrize("role_fixture", ["active_manager_user", "active_admin_user"])
def test_edit_any_comment_succeeds_for_manage_roles(
    client: TestClient,
    auth_headers: Callable[[User], dict[str, str]],
    employee_ticket: Ticket,
    employee_comment: Comment,
    role_fixture: str,
    request: pytest.FixtureRequest,
) -> None:
    user = request.getfixturevalue(role_fixture)
    response = client.put(
        f"/tickets/{employee_ticket.id}/comments/{employee_comment.id}",
        json={"content": "Manager correction."},
        headers=auth_headers(user),
    )
    assert response.status_code == 200


def test_edit_comment_unknown_comment_returns_404(
    client: TestClient,
    active_employee_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    employee_ticket: Ticket,
) -> None:
    response = client.put(
        f"/tickets/{employee_ticket.id}/comments/999999",
        json={"content": "Doesn't exist."},
        headers=auth_headers(active_employee_user),
    )
    assert response.status_code == 404


def test_edit_comment_belonging_to_different_ticket_returns_404(
    client: TestClient,
    active_employee_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    assigned_ticket: Ticket,
    employee_comment: Comment,
) -> None:
    # employee_comment belongs to employee_ticket, not assigned_ticket.
    response = client.put(
        f"/tickets/{assigned_ticket.id}/comments/{employee_comment.id}",
        json={"content": "Wrong ticket."},
        headers=auth_headers(active_employee_user),
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


def test_delete_own_comment_succeeds(
    client: TestClient,
    active_employee_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    employee_ticket: Ticket,
    employee_comment: Comment,
) -> None:
    response = client.delete(
        f"/tickets/{employee_ticket.id}/comments/{employee_comment.id}",
        headers=auth_headers(active_employee_user),
    )
    assert response.status_code == 204

    follow_up = client.get(
        f"/tickets/{employee_ticket.id}/comments", headers=auth_headers(active_employee_user)
    )
    assert employee_comment.id not in {c["id"] for c in follow_up.json()}


def test_delete_others_comment_forbidden(
    client: TestClient,
    active_employee_user_2: User,
    auth_headers: Callable[[User], dict[str, str]],
    employee_ticket: Ticket,
    employee_comment: Comment,
) -> None:
    response = client.delete(
        f"/tickets/{employee_ticket.id}/comments/{employee_comment.id}",
        headers=auth_headers(active_employee_user_2),
    )
    assert response.status_code == 403


def test_delete_any_comment_succeeds_for_admin(
    client: TestClient,
    active_admin_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    employee_ticket: Ticket,
    employee_comment: Comment,
) -> None:
    response = client.delete(
        f"/tickets/{employee_ticket.id}/comments/{employee_comment.id}",
        headers=auth_headers(active_admin_user),
    )
    assert response.status_code == 204


def test_delete_comment_unknown_returns_404(
    client: TestClient,
    active_employee_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    employee_ticket: Ticket,
) -> None:
    response = client.delete(
        f"/tickets/{employee_ticket.id}/comments/999999",
        headers=auth_headers(active_employee_user),
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Schema-level validation (no HTTP, no DB)
# ---------------------------------------------------------------------------


def test_comment_create_strips_whitespace() -> None:
    payload = CommentCreate(content="  Some content.  ")
    assert payload.content == "Some content."


def test_comment_create_rejects_empty_content() -> None:
    with pytest.raises(ValueError):
        CommentCreate(content="   ")
