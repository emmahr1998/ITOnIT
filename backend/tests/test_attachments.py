from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.models.attachment import Attachment
from app.models.ticket import Ticket
from app.models.user import User
from tests.conftest import FakeStorageService

# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------


def test_upload_attachment_succeeds_for_owning_employee(
    client: TestClient,
    active_employee_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    employee_ticket: Ticket,
) -> None:
    response = client.post(
        f"/tickets/{employee_ticket.id}/attachments",
        files={"file": ("photo.png", b"fake-image-bytes", "image/png")},
        headers=auth_headers(active_employee_user),
    )
    assert response.status_code == 201
    body = response.json()
    assert body["original_filename"] == "photo.png"
    assert body["content_type"] == "image/png"
    assert body["file_size"] == len(b"fake-image-bytes")
    assert body["uploaded_by"]["id"] == active_employee_user.id
    # The internal storage location must never be exposed.
    assert "stored_filename" not in body
    assert "file_path" not in body


def test_upload_attachment_succeeds_for_assigned_technician(
    client: TestClient,
    active_technician_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    assigned_ticket: Ticket,
) -> None:
    response = client.post(
        f"/tickets/{assigned_ticket.id}/attachments",
        files={"file": ("log.txt", b"log contents", "text/plain")},
        headers=auth_headers(active_technician_user),
    )
    assert response.status_code == 201


@pytest.mark.parametrize("role_fixture", ["active_manager_user", "active_admin_user"])
def test_upload_attachment_succeeds_for_manage_roles_on_any_ticket(
    client: TestClient,
    auth_headers: Callable[[User], dict[str, str]],
    employee_ticket: Ticket,
    role_fixture: str,
    request: pytest.FixtureRequest,
) -> None:
    user = request.getfixturevalue(role_fixture)
    response = client.post(
        f"/tickets/{employee_ticket.id}/attachments",
        files={"file": ("notes.pdf", b"%PDF-fake-content", "application/pdf")},
        headers=auth_headers(user),
    )
    assert response.status_code == 201


def test_upload_attachment_forbidden_for_other_employee(
    client: TestClient,
    active_employee_user_2: User,
    auth_headers: Callable[[User], dict[str, str]],
    employee_ticket: Ticket,
) -> None:
    response = client.post(
        f"/tickets/{employee_ticket.id}/attachments",
        files={"file": ("photo.png", b"data", "image/png")},
        headers=auth_headers(active_employee_user_2),
    )
    assert response.status_code == 403


def test_upload_attachment_forbidden_for_unassigned_technician(
    client: TestClient,
    active_technician_user_2: User,
    auth_headers: Callable[[User], dict[str, str]],
    assigned_ticket: Ticket,
) -> None:
    response = client.post(
        f"/tickets/{assigned_ticket.id}/attachments",
        files={"file": ("photo.png", b"data", "image/png")},
        headers=auth_headers(active_technician_user_2),
    )
    assert response.status_code == 403


def test_upload_attachment_rejects_empty_file(
    client: TestClient,
    active_employee_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    employee_ticket: Ticket,
) -> None:
    response = client.post(
        f"/tickets/{employee_ticket.id}/attachments",
        files={"file": ("empty.txt", b"", "text/plain")},
        headers=auth_headers(active_employee_user),
    )
    assert response.status_code == 400


def test_upload_attachment_rejects_oversized_file(
    client: TestClient,
    active_employee_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    employee_ticket: Ticket,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "MAX_ATTACHMENT_SIZE_BYTES", 10)
    response = client.post(
        f"/tickets/{employee_ticket.id}/attachments",
        files={"file": ("big.txt", b"this is definitely more than ten bytes", "text/plain")},
        headers=auth_headers(active_employee_user),
    )
    assert response.status_code == 400


def test_upload_attachment_rejects_unsupported_file_type(
    client: TestClient,
    active_employee_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    employee_ticket: Ticket,
) -> None:
    response = client.post(
        f"/tickets/{employee_ticket.id}/attachments",
        files={"file": ("virus.exe", b"MZ-fake-executable", "application/octet-stream")},
        headers=auth_headers(active_employee_user),
    )
    assert response.status_code == 400


def test_upload_attachment_unknown_ticket_returns_404(
    client: TestClient,
    active_employee_user: User,
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    response = client.post(
        "/tickets/999999/attachments",
        files={"file": ("photo.png", b"data", "image/png")},
        headers=auth_headers(active_employee_user),
    )
    assert response.status_code == 404


def test_upload_attachment_requires_authentication(
    client: TestClient, employee_ticket: Ticket
) -> None:
    response = client.post(
        f"/tickets/{employee_ticket.id}/attachments",
        files={"file": ("photo.png", b"data", "image/png")},
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------


def test_list_attachments_visible_to_owner(
    client: TestClient,
    active_employee_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    employee_ticket: Ticket,
    employee_attachment: Attachment,
) -> None:
    response = client.get(
        f"/tickets/{employee_ticket.id}/attachments", headers=auth_headers(active_employee_user)
    )
    assert response.status_code == 200
    ids = {a["id"] for a in response.json()}
    assert employee_attachment.id in ids


def test_list_attachments_forbidden_for_other_employee(
    client: TestClient,
    active_employee_user_2: User,
    auth_headers: Callable[[User], dict[str, str]],
    employee_ticket: Ticket,
) -> None:
    response = client.get(
        f"/tickets/{employee_ticket.id}/attachments", headers=auth_headers(active_employee_user_2)
    )
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------


def test_download_attachment_succeeds(
    client: TestClient,
    active_employee_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    employee_ticket: Ticket,
    employee_attachment: Attachment,
) -> None:
    response = client.get(
        f"/tickets/{employee_ticket.id}/attachments/{employee_attachment.id}",
        headers=auth_headers(active_employee_user),
    )
    assert response.status_code == 200
    assert response.content == b"fake-png-bytes"
    assert response.headers["content-type"] == "image/png"
    disposition = response.headers["content-disposition"]
    assert "screenshot.png" in disposition
    # Never leak the internal generated filename.
    assert employee_attachment.stored_filename not in disposition


def test_download_attachment_unknown_returns_404(
    client: TestClient,
    active_employee_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    employee_ticket: Ticket,
) -> None:
    response = client.get(
        f"/tickets/{employee_ticket.id}/attachments/999999",
        headers=auth_headers(active_employee_user),
    )
    assert response.status_code == 404


def test_download_attachment_forbidden_for_other_employee(
    client: TestClient,
    active_employee_user_2: User,
    auth_headers: Callable[[User], dict[str, str]],
    employee_ticket: Ticket,
    employee_attachment: Attachment,
) -> None:
    response = client.get(
        f"/tickets/{employee_ticket.id}/attachments/{employee_attachment.id}",
        headers=auth_headers(active_employee_user_2),
    )
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


def test_delete_attachment_succeeds_and_removes_the_file(
    client: TestClient,
    active_employee_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    employee_ticket: Ticket,
    employee_attachment: Attachment,
    storage_service: FakeStorageService,
) -> None:
    response = client.delete(
        f"/tickets/{employee_ticket.id}/attachments/{employee_attachment.id}",
        headers=auth_headers(active_employee_user),
    )
    assert response.status_code == 204
    assert employee_attachment.file_path not in storage_service.files

    follow_up = client.get(
        f"/tickets/{employee_ticket.id}/attachments", headers=auth_headers(active_employee_user)
    )
    assert employee_attachment.id not in {a["id"] for a in follow_up.json()}


def test_delete_attachment_allowed_for_any_ticket_viewer_not_just_uploader(
    client: TestClient,
    active_manager_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    employee_ticket: Ticket,
    employee_attachment: Attachment,
) -> None:
    """Unlike comments, attachment deletion has no per-item ownership rule -
    the business rules only gate on ticket-view access. A Manager (who never
    uploaded this file) can delete it purely by virtue of ticket access."""
    response = client.delete(
        f"/tickets/{employee_ticket.id}/attachments/{employee_attachment.id}",
        headers=auth_headers(active_manager_user),
    )
    assert response.status_code == 204


def test_delete_attachment_forbidden_for_other_employee(
    client: TestClient,
    active_employee_user_2: User,
    auth_headers: Callable[[User], dict[str, str]],
    employee_ticket: Ticket,
    employee_attachment: Attachment,
) -> None:
    response = client.delete(
        f"/tickets/{employee_ticket.id}/attachments/{employee_attachment.id}",
        headers=auth_headers(active_employee_user_2),
    )
    assert response.status_code == 403


def test_delete_attachment_unknown_returns_404(
    client: TestClient,
    active_employee_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    employee_ticket: Ticket,
) -> None:
    response = client.delete(
        f"/tickets/{employee_ticket.id}/attachments/999999",
        headers=auth_headers(active_employee_user),
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# History integration
# ---------------------------------------------------------------------------


def test_history_records_attachment_added(
    client: TestClient,
    active_employee_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    employee_ticket: Ticket,
) -> None:
    client.post(
        f"/tickets/{employee_ticket.id}/attachments",
        files={"file": ("photo.png", b"data", "image/png")},
        headers=auth_headers(active_employee_user),
    )

    response = client.get(
        f"/tickets/{employee_ticket.id}/history", headers=auth_headers(active_employee_user)
    )
    actions = {entry["action"]: entry for entry in response.json()}
    assert actions["attachment_added"]["new_value"] == "photo.png"
    assert actions["attachment_added"]["old_value"] is None
    assert actions["attachment_added"]["performed_by"]["id"] == active_employee_user.id


def test_history_records_attachment_deleted(
    client: TestClient,
    active_employee_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    employee_ticket: Ticket,
    employee_attachment: Attachment,
) -> None:
    client.delete(
        f"/tickets/{employee_ticket.id}/attachments/{employee_attachment.id}",
        headers=auth_headers(active_employee_user),
    )

    response = client.get(
        f"/tickets/{employee_ticket.id}/history", headers=auth_headers(active_employee_user)
    )
    actions = {entry["action"]: entry for entry in response.json()}
    assert actions["attachment_deleted"]["old_value"] == "screenshot.png"
    assert actions["attachment_deleted"]["new_value"] is None
