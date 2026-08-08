"""Tests for Milestone 6 - Company Settings: GET/PATCH /companies/me,
POST /companies/me/logo, and the public GET /companies/{id}/logo.
"""

from collections.abc import Callable

from fastapi.testclient import TestClient

from app.models.company import Company
from app.models.user import User


def test_get_settings_returns_current_company(
    client: TestClient, active_admin_user: User, auth_headers: Callable[[User], dict[str, str]], company_a: Company
) -> None:
    response = client.get("/companies/me", headers=auth_headers(active_admin_user))
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == company_a.name
    assert body["company_code"] == company_a.company_code
    assert body["theme"] == "light"
    assert body["timezone"] == "UTC"
    assert body["language"] == "en"
    assert body["logo_url"] is None


def test_get_settings_requires_authentication(client: TestClient) -> None:
    response = client.get("/companies/me")
    assert response.status_code == 401


def test_get_settings_forbidden_for_employee(
    client: TestClient, active_employee_user: User, auth_headers: Callable[[User], dict[str, str]]
) -> None:
    response = client.get("/companies/me", headers=auth_headers(active_employee_user))
    assert response.status_code == 403


def test_get_settings_forbidden_for_technician(
    client: TestClient, active_technician_user: User, auth_headers: Callable[[User], dict[str, str]]
) -> None:
    response = client.get("/companies/me", headers=auth_headers(active_technician_user))
    assert response.status_code == 403


def test_patch_settings_updates_name(
    client: TestClient, active_admin_user: User, auth_headers: Callable[[User], dict[str, str]]
) -> None:
    response = client.patch(
        "/companies/me", json={"name": "Renamed Co"}, headers=auth_headers(active_admin_user)
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Renamed Co"

    refetched = client.get("/companies/me", headers=auth_headers(active_admin_user))
    assert refetched.json()["name"] == "Renamed Co"


def test_patch_settings_updates_company_code(
    client: TestClient, active_admin_user: User, auth_headers: Callable[[User], dict[str, str]]
) -> None:
    response = client.patch(
        "/companies/me",
        json={"company_code": "RENAMEDCODE1"},
        headers=auth_headers(active_admin_user),
    )
    assert response.status_code == 200
    assert response.json()["company_code"] == "RENAMEDCODE1"


def test_patch_settings_new_company_code_works_for_login_and_resolve(
    client: TestClient,
    active_admin_user: User,
    admin_password: str,
    auth_headers: Callable[[User], dict[str, str]],
    company_a: Company,
) -> None:
    old_code = company_a.company_code
    client.patch(
        "/companies/me",
        json={"company_code": "NEWLOGINCODE"},
        headers=auth_headers(active_admin_user),
    )

    # The old code no longer resolves or logs in.
    old_resolve = client.post("/auth/resolve-company", json={"company_code": old_code})
    assert old_resolve.status_code == 404
    old_login = client.post(
        "/auth/login",
        json={
            "company_code": old_code,
            "username": active_admin_user.username,
            "password": admin_password,
        },
    )
    assert old_login.status_code == 401

    # The new code works for both.
    new_resolve = client.post(
        "/auth/resolve-company", json={"company_code": "NEWLOGINCODE"}
    )
    assert new_resolve.status_code == 200
    new_login = client.post(
        "/auth/login",
        json={
            "company_code": "NEWLOGINCODE",
            "username": active_admin_user.username,
            "password": admin_password,
        },
    )
    assert new_login.status_code == 200


def test_patch_settings_rejects_duplicate_company_code(
    client: TestClient,
    active_admin_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    company_b: Company,
) -> None:
    response = client.patch(
        "/companies/me",
        json={"company_code": company_b.company_code},
        headers=auth_headers(active_admin_user),
    )
    assert response.status_code == 409


def test_patch_settings_rejects_duplicate_company_code_case_insensitively(
    client: TestClient,
    active_admin_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    company_b: Company,
) -> None:
    response = client.patch(
        "/companies/me",
        json={"company_code": company_b.company_code.lower()},
        headers=auth_headers(active_admin_user),
    )
    assert response.status_code == 409


def test_patch_settings_keeping_the_same_code_is_not_a_conflict(
    client: TestClient,
    active_admin_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    company_a: Company,
) -> None:
    """PATCHing with the company's own current code (e.g. submitting the
    whole form unchanged) must succeed, not 409 against itself."""
    response = client.patch(
        "/companies/me",
        json={"name": "Still Company A", "company_code": company_a.company_code},
        headers=auth_headers(active_admin_user),
    )
    assert response.status_code == 200


def test_patch_settings_rejects_invalid_company_code_format(
    client: TestClient, active_admin_user: User, auth_headers: Callable[[User], dict[str, str]]
) -> None:
    response = client.patch(
        "/companies/me",
        json={"company_code": "not a valid code!"},
        headers=auth_headers(active_admin_user),
    )
    assert response.status_code == 422


def test_patch_settings_updates_contact_email(
    client: TestClient, active_admin_user: User, auth_headers: Callable[[User], dict[str, str]]
) -> None:
    response = client.patch(
        "/companies/me",
        json={"contact_email": "support@company-a.test"},
        headers=auth_headers(active_admin_user),
    )
    assert response.status_code == 200
    assert response.json()["contact_email"] == "support@company-a.test"


def test_patch_settings_rejects_invalid_contact_email(
    client: TestClient, active_admin_user: User, auth_headers: Callable[[User], dict[str, str]]
) -> None:
    response = client.patch(
        "/companies/me",
        json={"contact_email": "not-an-email"},
        headers=auth_headers(active_admin_user),
    )
    assert response.status_code == 422


def test_patch_settings_clears_contact_email_with_empty_string(
    client: TestClient, active_admin_user: User, auth_headers: Callable[[User], dict[str, str]]
) -> None:
    client.patch(
        "/companies/me",
        json={"contact_email": "support@company-a.test"},
        headers=auth_headers(active_admin_user),
    )
    response = client.patch(
        "/companies/me", json={"contact_email": ""}, headers=auth_headers(active_admin_user)
    )
    assert response.status_code == 200
    assert response.json()["contact_email"] is None


def test_patch_settings_omitted_fields_are_left_unchanged(
    client: TestClient,
    active_admin_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    company_a: Company,
) -> None:
    response = client.patch(
        "/companies/me", json={"name": "Only Name Changed"}, headers=auth_headers(active_admin_user)
    )
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Only Name Changed"
    assert body["company_code"] == company_a.company_code


def test_patch_settings_requires_authentication(client: TestClient) -> None:
    response = client.patch("/companies/me", json={"name": "Nope"})
    assert response.status_code == 401


def test_patch_settings_forbidden_for_employee(
    client: TestClient, active_employee_user: User, auth_headers: Callable[[User], dict[str, str]]
) -> None:
    response = client.patch(
        "/companies/me", json={"name": "Nope"}, headers=auth_headers(active_employee_user)
    )
    assert response.status_code == 403


def test_patch_settings_forbidden_for_technician(
    client: TestClient, active_technician_user: User, auth_headers: Callable[[User], dict[str, str]]
) -> None:
    response = client.patch(
        "/companies/me", json={"name": "Nope"}, headers=auth_headers(active_technician_user)
    )
    assert response.status_code == 403


def test_patch_settings_cannot_set_client_supplied_company_id(
    client: TestClient, active_admin_user: User, auth_headers: Callable[[User], dict[str, str]]
) -> None:
    """CompanyUpdateRequest has no company_id field - the row updated is
    always the caller's own (get_current_company_id), never one the client
    tries to name."""
    response = client.patch(
        "/companies/me",
        json={"name": "Still Mine", "company_id": 999999},
        headers=auth_headers(active_admin_user),
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Still Mine"


# ---------------------------------------------------------------------------
# POST /companies/me/logo, GET /companies/{id}/logo
# ---------------------------------------------------------------------------


def test_upload_logo_succeeds(
    client: TestClient, active_admin_user: User, auth_headers: Callable[[User], dict[str, str]]
) -> None:
    response = client.post(
        "/companies/me/logo",
        files={"file": ("logo.png", b"fake-png-bytes", "image/png")},
        headers=auth_headers(active_admin_user),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["logo_url"] is not None
    assert body["logo_url"].startswith("/companies/")
    assert body["logo_url"].endswith("/logo")
    # The internal storage location must never be exposed.
    assert "logo_path" not in body


def test_uploaded_logo_is_publicly_fetchable(
    client: TestClient, active_admin_user: User, auth_headers: Callable[[User], dict[str, str]]
) -> None:
    upload = client.post(
        "/companies/me/logo",
        files={"file": ("logo.png", b"fake-png-bytes", "image/png")},
        headers=auth_headers(active_admin_user),
    )
    logo_url = upload.json()["logo_url"]

    # No Authorization header - this must be publicly reachable, since the
    # pre-login screen needs to display it.
    response = client.get(logo_url)
    assert response.status_code == 200
    assert response.content == b"fake-png-bytes"
    assert response.headers["content-type"] == "image/png"


def test_get_logo_returns_404_when_none_uploaded(
    client: TestClient, company_a: Company
) -> None:
    response = client.get(f"/companies/{company_a.id}/logo")
    assert response.status_code == 404


def test_get_logo_returns_404_for_unknown_company(client: TestClient) -> None:
    response = client.get("/companies/999999/logo")
    assert response.status_code == 404


def test_upload_logo_replaces_previous_logo(
    client: TestClient, active_admin_user: User, auth_headers: Callable[[User], dict[str, str]]
) -> None:
    first = client.post(
        "/companies/me/logo",
        files={"file": ("logo1.png", b"first-logo-bytes", "image/png")},
        headers=auth_headers(active_admin_user),
    )
    first_url = first.json()["logo_url"]

    second = client.post(
        "/companies/me/logo",
        files={"file": ("logo2.png", b"second-logo-bytes", "image/png")},
        headers=auth_headers(active_admin_user),
    )
    second_url = second.json()["logo_url"]

    fetched = client.get(second_url)
    assert fetched.status_code == 200
    assert fetched.content == b"second-logo-bytes"
    # Same company -> same fetch-by-id URL both times.
    assert first_url == second_url


def test_upload_logo_rejects_empty_file(
    client: TestClient, active_admin_user: User, auth_headers: Callable[[User], dict[str, str]]
) -> None:
    response = client.post(
        "/companies/me/logo",
        files={"file": ("logo.png", b"", "image/png")},
        headers=auth_headers(active_admin_user),
    )
    assert response.status_code == 400


def test_upload_logo_rejects_unsupported_file_type(
    client: TestClient, active_admin_user: User, auth_headers: Callable[[User], dict[str, str]]
) -> None:
    response = client.post(
        "/companies/me/logo",
        files={"file": ("logo.svg", b"<svg></svg>", "image/svg+xml")},
        headers=auth_headers(active_admin_user),
    )
    assert response.status_code == 400


def test_upload_logo_rejects_oversized_file(
    client: TestClient, active_admin_user: User, auth_headers: Callable[[User], dict[str, str]]
) -> None:
    from app.core.config import settings

    oversized = b"x" * (settings.MAX_LOGO_SIZE_BYTES + 1)
    response = client.post(
        "/companies/me/logo",
        files={"file": ("logo.png", oversized, "image/png")},
        headers=auth_headers(active_admin_user),
    )
    assert response.status_code == 400


def test_upload_logo_requires_authentication(client: TestClient) -> None:
    response = client.post(
        "/companies/me/logo", files={"file": ("logo.png", b"bytes", "image/png")}
    )
    assert response.status_code == 401


def test_upload_logo_forbidden_for_employee(
    client: TestClient, active_employee_user: User, auth_headers: Callable[[User], dict[str, str]]
) -> None:
    response = client.post(
        "/companies/me/logo",
        files={"file": ("logo.png", b"bytes", "image/png")},
        headers=auth_headers(active_employee_user),
    )
    assert response.status_code == 403


def test_upload_logo_forbidden_for_technician(
    client: TestClient, active_technician_user: User, auth_headers: Callable[[User], dict[str, str]]
) -> None:
    response = client.post(
        "/companies/me/logo",
        files={"file": ("logo.png", b"bytes", "image/png")},
        headers=auth_headers(active_technician_user),
    )
    assert response.status_code == 403


def test_resolve_company_reflects_updated_name_immediately(
    client: TestClient,
    active_admin_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    company_a: Company,
) -> None:
    client.patch(
        "/companies/me",
        json={"name": "Freshly Renamed"},
        headers=auth_headers(active_admin_user),
    )
    resolved = client.post(
        "/auth/resolve-company", json={"company_code": company_a.company_code}
    )
    assert resolved.status_code == 200
    assert resolved.json()["company_name"] == "Freshly Renamed"


def test_resolve_company_reflects_uploaded_logo_immediately(
    client: TestClient,
    active_admin_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    company_a: Company,
) -> None:
    upload = client.post(
        "/companies/me/logo",
        files={"file": ("logo.png", b"fake-png-bytes", "image/png")},
        headers=auth_headers(active_admin_user),
    )
    expected_logo_url = upload.json()["logo_url"]

    resolved = client.post(
        "/auth/resolve-company", json={"company_code": company_a.company_code}
    )
    assert resolved.status_code == 200
    assert resolved.json()["company_logo"] == expected_logo_url


def test_settings_changes_do_not_affect_another_company(
    client: TestClient,
    active_admin_user: User,
    company_b_admin_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    company_b: Company,
) -> None:
    client.patch(
        "/companies/me", json={"name": "Company A Renamed"}, headers=auth_headers(active_admin_user)
    )
    still_b = client.get("/companies/me", headers=auth_headers(company_b_admin_user))
    assert still_b.json()["name"] == company_b.name
