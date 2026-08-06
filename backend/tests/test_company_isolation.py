"""Cross-company (multi-tenant) isolation tests.

Every test here plays Company A (the pre-existing fixtures) against Company
B (the company_b_* fixtures added for this milestone) and asserts that
nothing Company A does can observe, modify, or reference Company B's data -
and vice versa where it matters. See CompanyScopedRepository
(app/repositories/base.py) and get_current_company_id
(app/dependencies/auth.py) for the enforcement mechanism these tests verify;
scoping happens in the repository/service layer, not in these routes, so a
malicious id or query parameter cannot bypass it no matter how it is spelled.
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
# Departments
# ---------------------------------------------------------------------------


def test_company_a_list_departments_excludes_company_b(
    client: TestClient,
    active_employee_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    company_b_department: Department,
) -> None:
    response = client.get("/departments", headers=auth_headers(active_employee_user))
    assert response.status_code == 200
    titles = {d["title"] for d in response.json()["data"]}
    assert company_b_department.title not in titles


def test_company_a_cannot_fetch_company_b_department_by_id(
    client: TestClient,
    active_employee_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    company_b_department: Department,
) -> None:
    response = client.get(
        f"/departments/{company_b_department.id}", headers=auth_headers(active_employee_user)
    )
    assert response.status_code == 404


def test_company_a_cannot_update_company_b_department(
    client: TestClient,
    active_admin_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    company_b_department: Department,
) -> None:
    response = client.patch(
        f"/departments/{company_b_department.id}",
        json={"title": "Hijacked"},
        headers=auth_headers(active_admin_user),
    )
    assert response.status_code == 404


def test_company_a_malicious_id_bypass_returns_same_404_as_nonexistent(
    client: TestClient,
    active_employee_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    company_b_department: Department,
) -> None:
    """A real (existing, in another company) id and a wholly fictitious id
    must be indistinguishable to the caller."""
    real_cross_company = client.get(
        f"/departments/{company_b_department.id}", headers=auth_headers(active_employee_user)
    )
    fictitious = client.get("/departments/999999", headers=auth_headers(active_employee_user))
    assert real_cross_company.status_code == fictitious.status_code == 404
    assert real_cross_company.json() == fictitious.json()


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------


def test_company_a_list_categories_excludes_company_b(
    client: TestClient,
    active_employee_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    company_b_category: Category,
) -> None:
    response = client.get("/categories", headers=auth_headers(active_employee_user))
    assert response.status_code == 200
    names = {c["name"] for c in response.json()}
    assert company_b_category.name not in names


def test_company_a_cannot_fetch_company_b_category_by_id(
    client: TestClient,
    active_employee_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    company_b_category: Category,
) -> None:
    response = client.get(
        f"/categories/{company_b_category.id}", headers=auth_headers(active_employee_user)
    )
    assert response.status_code == 404


def test_company_a_cannot_update_company_b_category(
    client: TestClient,
    active_admin_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    company_b_category: Category,
) -> None:
    response = client.put(
        f"/categories/{company_b_category.id}",
        json={"name": "Hijacked"},
        headers=auth_headers(active_admin_user),
    )
    assert response.status_code == 404


def test_company_a_cannot_delete_company_b_category(
    client: TestClient,
    active_admin_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    company_b_category: Category,
) -> None:
    response = client.delete(
        f"/categories/{company_b_category.id}", headers=auth_headers(active_admin_user)
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Locations
# ---------------------------------------------------------------------------


def test_company_a_list_locations_excludes_company_b(
    client: TestClient,
    active_employee_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    company_b_location: Location,
) -> None:
    response = client.get("/locations", headers=auth_headers(active_employee_user))
    assert response.status_code == 200
    titles = {loc["title"] for loc in response.json()["data"]}
    assert company_b_location.title not in titles


def test_company_a_cannot_fetch_company_b_location_by_id(
    client: TestClient,
    active_employee_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    company_b_location: Location,
) -> None:
    response = client.get(
        f"/locations/{company_b_location.id}", headers=auth_headers(active_employee_user)
    )
    assert response.status_code == 404


def test_company_a_cannot_update_company_b_location(
    client: TestClient,
    active_admin_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    company_b_location: Location,
) -> None:
    response = client.patch(
        f"/locations/{company_b_location.id}",
        json={"title": "Hijacked"},
        headers=auth_headers(active_admin_user),
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Priorities
# ---------------------------------------------------------------------------


def test_company_a_list_priorities_excludes_company_b(
    client: TestClient,
    active_employee_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    company_b_priority: Priority,
) -> None:
    response = client.get("/priorities", headers=auth_headers(active_employee_user))
    assert response.status_code == 200
    titles = {p["title"] for p in response.json()["data"]}
    assert company_b_priority.title not in titles


def test_company_a_cannot_fetch_company_b_priority_by_id(
    client: TestClient,
    active_employee_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    company_b_priority: Priority,
) -> None:
    response = client.get(
        f"/priorities/{company_b_priority.id}", headers=auth_headers(active_employee_user)
    )
    assert response.status_code == 404


def test_company_a_cannot_update_company_b_priority(
    client: TestClient,
    active_admin_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    company_b_priority: Priority,
) -> None:
    response = client.patch(
        f"/priorities/{company_b_priority.id}",
        json={"title": "Hijacked"},
        headers=auth_headers(active_admin_user),
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------


def test_company_a_list_users_excludes_company_b(
    client: TestClient,
    active_manager_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    company_b_admin_user: User,
) -> None:
    response = client.get("/users", headers=auth_headers(active_manager_user))
    assert response.status_code == 200
    usernames = {u["username"] for u in response.json()["data"]}
    assert company_b_admin_user.username not in usernames


def test_company_a_cannot_fetch_company_b_user_by_id(
    client: TestClient,
    active_manager_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    company_b_employee_user: User,
) -> None:
    response = client.get(
        f"/users/{company_b_employee_user.id}", headers=auth_headers(active_manager_user)
    )
    assert response.status_code == 404


def test_company_a_cannot_update_company_b_user(
    client: TestClient,
    active_admin_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    company_b_employee_user: User,
) -> None:
    response = client.patch(
        f"/users/{company_b_employee_user.id}",
        json={"first_name": "Hijacked"},
        headers=auth_headers(active_admin_user),
    )
    assert response.status_code == 404


def test_company_a_admin_cannot_set_company_b_user_password(
    client: TestClient,
    active_admin_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    company_b_employee_user: User,
) -> None:
    response = client.patch(
        f"/users/{company_b_employee_user.id}/password",
        json={"new_password": "NewPassword1!"},
        headers=auth_headers(active_admin_user),
    )
    assert response.status_code == 404


def test_company_a_cannot_create_user_with_company_b_department(
    client: TestClient,
    active_admin_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    company_b_department: Department,
    employee_role: object,
) -> None:
    response = client.post(
        "/users",
        json={
            "username": "newhire",
            "first_name": "New",
            "last_name": "Hire",
            "email": "newhire@itonit.test",
            "department_id": company_b_department.id,
            "password": "SomePassword1!",
            "role_id": 2,
        },
        headers=auth_headers(active_admin_user),
    )
    assert response.status_code == 400


def test_company_a_cannot_reassign_user_to_company_b_department(
    client: TestClient,
    active_admin_user: User,
    active_employee_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    company_b_department: Department,
) -> None:
    response = client.patch(
        f"/users/{active_employee_user.id}",
        json={"department_id": company_b_department.id},
        headers=auth_headers(active_admin_user),
    )
    assert response.status_code == 400


# ---------------------------------------------------------------------------
# Tickets
# ---------------------------------------------------------------------------


def test_company_a_list_tickets_excludes_company_b(
    client: TestClient,
    active_manager_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    company_b_ticket: Ticket,
) -> None:
    response = client.get("/all-tickets", headers=auth_headers(active_manager_user))
    assert response.status_code == 200
    ticket_numbers = {t["ticket_number"] for t in response.json()["data"]}
    ids = {t["id"] for t in response.json()["data"]}
    assert company_b_ticket.id not in ids
    # Both companies independently number from IT-<year>-000001, so a
    # colliding ticket_number string is expected and does not itself leak
    # anything - the id exclusion above is the real assertion.
    assert len(ticket_numbers) == len(ids)


def test_company_a_cannot_fetch_company_b_ticket_by_id(
    client: TestClient,
    active_manager_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    company_b_ticket: Ticket,
) -> None:
    response = client.get(
        f"/tickets/{company_b_ticket.id}", headers=auth_headers(active_manager_user)
    )
    assert response.status_code == 404


def test_company_a_cannot_update_company_b_ticket(
    client: TestClient,
    active_manager_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    company_b_ticket: Ticket,
) -> None:
    response = client.patch(
        f"/tickets/{company_b_ticket.id}",
        json={"title": "Hijacked"},
        headers=auth_headers(active_manager_user),
    )
    assert response.status_code == 404


def test_company_a_cannot_delete_company_b_ticket(
    client: TestClient,
    active_admin_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    company_b_ticket: Ticket,
) -> None:
    response = client.delete(
        f"/tickets/{company_b_ticket.id}", headers=auth_headers(active_admin_user)
    )
    assert response.status_code == 404


def test_company_a_cannot_assign_company_b_technician(
    client: TestClient,
    active_manager_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    employee_ticket: Ticket,
    company_b_technician_user: User,
) -> None:
    response = client.patch(
        f"/tickets/{employee_ticket.id}/assign",
        json={"technician_id": company_b_technician_user.id},
        headers=auth_headers(active_manager_user),
    )
    assert response.status_code == 400


def test_company_a_cannot_assign_technician_to_company_b_ticket(
    client: TestClient,
    active_manager_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    active_technician_user: User,
    company_b_ticket: Ticket,
) -> None:
    """The ticket lookup itself must 404 before the technician is even
    validated - a Company A manager has no route to touch a Company B
    ticket at all, regardless of who they try to assign to it."""
    response = client.patch(
        f"/tickets/{company_b_ticket.id}/assign",
        json={"technician_id": active_technician_user.id},
        headers=auth_headers(active_manager_user),
    )
    assert response.status_code == 404


def test_company_a_cannot_create_ticket_with_company_b_category(
    client: TestClient,
    active_employee_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    company_b_category: Category,
    medium_priority: Priority,
) -> None:
    response = client.post(
        "/ticket-new",
        json={
            "title": "Cross-company category attempt",
            "description": "Should be rejected.",
            "category_id": company_b_category.id,
            "priority_id": medium_priority.id,
        },
        headers=auth_headers(active_employee_user),
    )
    assert response.status_code == 400


def test_company_a_cannot_create_ticket_with_company_b_priority(
    client: TestClient,
    active_employee_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    hardware_category: Category,
    company_b_priority: Priority,
) -> None:
    response = client.post(
        "/ticket-new",
        json={
            "title": "Cross-company priority attempt",
            "description": "Should be rejected.",
            "category_id": hardware_category.id,
            "priority_id": company_b_priority.id,
        },
        headers=auth_headers(active_employee_user),
    )
    assert response.status_code == 400


def test_company_a_cannot_create_ticket_with_company_b_location(
    client: TestClient,
    active_employee_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    hardware_category: Category,
    medium_priority: Priority,
    company_b_location: Location,
) -> None:
    response = client.post(
        "/ticket-new",
        json={
            "title": "Cross-company location attempt",
            "description": "Should be rejected.",
            "category_id": hardware_category.id,
            "priority_id": medium_priority.id,
            "location_id": company_b_location.id,
        },
        headers=auth_headers(active_employee_user),
    )
    assert response.status_code == 400


def test_company_a_manager_cannot_create_ticket_for_company_b_requester(
    client: TestClient,
    active_manager_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    hardware_category: Category,
    medium_priority: Priority,
    company_b_employee_user: User,
) -> None:
    response = client.post(
        "/ticket-new",
        json={
            "title": "Cross-company requester attempt",
            "description": "Should be rejected.",
            "category_id": hardware_category.id,
            "priority_id": medium_priority.id,
            "requester_user_id": company_b_employee_user.id,
        },
        headers=auth_headers(active_manager_user),
    )
    assert response.status_code == 400


def test_company_a_malicious_query_param_cannot_leak_company_b_tickets(
    client: TestClient,
    active_manager_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    company_b_ticket: Ticket,
    company_b_employee_user: User,
) -> None:
    """Filtering by a real Company B user id must not surface Company B's
    ticket - the company scope is applied independently of, and before,
    any client-supplied filter."""
    response = client.get(
        "/all-tickets",
        params={"requester": company_b_employee_user.id},
        headers=auth_headers(active_manager_user),
    )
    assert response.status_code == 200
    assert response.json()["data"] == []


# ---------------------------------------------------------------------------
# Comments
# ---------------------------------------------------------------------------


def test_company_a_cannot_list_comments_on_company_b_ticket(
    client: TestClient,
    active_manager_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    company_b_ticket: Ticket,
) -> None:
    response = client.get(
        f"/tickets/{company_b_ticket.id}/comments", headers=auth_headers(active_manager_user)
    )
    assert response.status_code == 404


def test_company_a_cannot_comment_on_company_b_ticket(
    client: TestClient,
    active_employee_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    company_b_ticket: Ticket,
) -> None:
    response = client.post(
        f"/tickets/{company_b_ticket.id}/comments",
        json={"content": "Trying to comment cross-company."},
        headers=auth_headers(active_employee_user),
    )
    assert response.status_code == 404


def test_company_a_cannot_edit_company_b_comment(
    client: TestClient,
    active_manager_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    company_b_ticket: Ticket,
    company_b_comment: object,
) -> None:
    response = client.put(
        f"/tickets/{company_b_ticket.id}/comments/{company_b_comment.id}",
        json={"content": "Hijacked"},
        headers=auth_headers(active_manager_user),
    )
    assert response.status_code == 404


def test_company_a_cannot_delete_company_b_comment(
    client: TestClient,
    active_manager_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    company_b_ticket: Ticket,
    company_b_comment: object,
) -> None:
    response = client.delete(
        f"/tickets/{company_b_ticket.id}/comments/{company_b_comment.id}",
        headers=auth_headers(active_manager_user),
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Attachments
# ---------------------------------------------------------------------------


def test_company_a_cannot_list_attachments_on_company_b_ticket(
    client: TestClient,
    active_manager_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    company_b_ticket: Ticket,
) -> None:
    response = client.get(
        f"/tickets/{company_b_ticket.id}/attachments", headers=auth_headers(active_manager_user)
    )
    assert response.status_code == 404


def test_company_a_cannot_upload_attachment_to_company_b_ticket(
    client: TestClient,
    active_employee_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    company_b_ticket: Ticket,
) -> None:
    response = client.post(
        f"/tickets/{company_b_ticket.id}/attachments",
        files={"file": ("evil.png", b"fake-bytes", "image/png")},
        headers=auth_headers(active_employee_user),
    )
    assert response.status_code == 404


def test_company_a_cannot_download_company_b_attachment(
    client: TestClient,
    active_manager_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    company_b_ticket: Ticket,
    company_b_attachment: object,
) -> None:
    response = client.get(
        f"/tickets/{company_b_ticket.id}/attachments/{company_b_attachment.id}",
        headers=auth_headers(active_manager_user),
    )
    assert response.status_code == 404


def test_company_a_cannot_delete_company_b_attachment(
    client: TestClient,
    active_manager_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    company_b_ticket: Ticket,
    company_b_attachment: object,
) -> None:
    response = client.delete(
        f"/tickets/{company_b_ticket.id}/attachments/{company_b_attachment.id}",
        headers=auth_headers(active_manager_user),
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Ticket history
# ---------------------------------------------------------------------------


def test_company_a_cannot_view_history_for_company_b_ticket(
    client: TestClient,
    active_manager_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    company_b_ticket: Ticket,
) -> None:
    response = client.get(
        f"/tickets/{company_b_ticket.id}/history", headers=auth_headers(active_manager_user)
    )
    assert response.status_code == 404


def test_company_a_ticket_history_never_contains_company_b_entries(
    client: TestClient,
    active_manager_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    employee_ticket: Ticket,
    company_b_ticket: Ticket,
) -> None:
    """A Company A ticket's own history must only ever contain entries
    company-scoped to Company A, even though both companies' history rows
    physically coexist in the same table."""
    response = client.get(
        f"/tickets/{employee_ticket.id}/history", headers=auth_headers(active_manager_user)
    )
    assert response.status_code == 200
    for entry in response.json():
        assert entry["ticket_id"] == employee_ticket.id


# ---------------------------------------------------------------------------
# Reverse direction - Company B must be equally blind to Company A, proving
# the scoping is symmetric and not an artifact of fixture ordering/ids.
# ---------------------------------------------------------------------------


def test_company_b_cannot_fetch_company_a_ticket_by_id(
    client: TestClient,
    company_b_admin_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    employee_ticket: Ticket,
) -> None:
    response = client.get(
        f"/tickets/{employee_ticket.id}", headers=auth_headers(company_b_admin_user)
    )
    assert response.status_code == 404


def test_company_b_list_departments_excludes_company_a(
    client: TestClient,
    company_b_employee_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    it_department: Department,
) -> None:
    response = client.get("/departments", headers=auth_headers(company_b_employee_user))
    assert response.status_code == 200
    titles = {d["title"] for d in response.json()["data"]}
    assert it_department.title not in titles


def test_company_b_admin_cannot_view_company_a_user(
    client: TestClient,
    company_b_admin_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    active_employee_user: User,
) -> None:
    response = client.get(
        f"/users/{active_employee_user.id}", headers=auth_headers(company_b_admin_user)
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# No customer-facing endpoint accepts a company_id override from the client.
# ---------------------------------------------------------------------------


def test_ticket_create_payload_cannot_override_company_id(
    client: TestClient,
    active_employee_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    hardware_category: Category,
    medium_priority: Priority,
) -> None:
    """Even if a client sends a company_id field, TicketNewCreate has no
    such field to bind it to - it is silently ignored, not honored, and the
    created ticket is always scoped to the caller's own company."""
    response = client.post(
        "/ticket-new",
        json={
            "title": "No override possible",
            "description": "company_id in the body must be ignored.",
            "category_id": hardware_category.id,
            "priority_id": medium_priority.id,
            "company_id": 999999,
        },
        headers=auth_headers(active_employee_user),
    )
    assert response.status_code == 201
    # The created ticket must still be visible to Company A (proving it
    # landed in Company A, not vanished into a bogus company_id 999999).
    ticket_id = response.json()["data"]["id"]
    fetch = client.get(f"/tickets/{ticket_id}", headers=auth_headers(active_employee_user))
    assert fetch.status_code == 200


def test_user_create_payload_cannot_override_company_id(
    client: TestClient,
    active_admin_user: User,
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    response = client.post(
        "/users",
        json={
            "username": "nocompanyoverride",
            "first_name": "No",
            "last_name": "Override",
            "email": "nocompanyoverride@itonit.test",
            "password": "SomePassword1!",
            "role_id": 2,
            "company_id": 999999,
        },
        headers=auth_headers(active_admin_user),
    )
    assert response.status_code == 201
    user_id = response.json()["data"]["id"]
    # Visible to a Company A manager, proving it was scoped to Company A
    # despite the ignored company_id in the payload.
    fetch = client.get(f"/users/{user_id}", headers=auth_headers(active_admin_user))
    assert fetch.status_code == 200
