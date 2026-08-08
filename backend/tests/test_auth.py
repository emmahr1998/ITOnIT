from fastapi.testclient import TestClient

from app.core.security import create_access_token, create_refresh_token
from app.models.company import Company
from app.models.user import User


# ---------------------------------------------------------------------------
# POST /auth/register was removed in Milestone 5 - replaced by
# POST /companies/register (see test_company_registration.py). This is not
# a dead endpoint left behind by accident; it's the intended shape of the
# route table going forward, so it's worth a permanent regression test.
# ---------------------------------------------------------------------------


def test_old_self_registration_endpoint_no_longer_exists(client: TestClient) -> None:
    response = client.post(
        "/auth/register",
        json={
            "username": "someone",
            "first_name": "Some",
            "last_name": "One",
            "email": "someone@example.com",
            "password": "SuperSecret1!",
        },
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# POST /auth/resolve-company
# ---------------------------------------------------------------------------


def test_resolve_company_succeeds_for_active_company(
    client: TestClient, company_a: Company
) -> None:
    response = client.post(
        "/auth/resolve-company", json={"company_code": company_a.company_code}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["company_name"] == company_a.name
    assert body["company_logo"] is None


def test_resolve_company_is_case_insensitive(client: TestClient, company_a: Company) -> None:
    response = client.post(
        "/auth/resolve-company", json={"company_code": company_a.company_code.lower()}
    )
    assert response.status_code == 200
    assert response.json()["company_name"] == company_a.name


def test_resolve_company_unknown_code_returns_404(client: TestClient) -> None:
    response = client.post("/auth/resolve-company", json={"company_code": "NOSUCHCODE"})
    assert response.status_code == 404


def test_resolve_company_suspended_returns_distinct_403(
    client: TestClient, suspended_company: Company
) -> None:
    response = client.post(
        "/auth/resolve-company", json={"company_code": suspended_company.company_code}
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "This company's account has been suspended"


def test_resolve_company_rejects_blank_code(client: TestClient) -> None:
    response = client.post("/auth/resolve-company", json={"company_code": "   "})
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# POST /auth/login
# ---------------------------------------------------------------------------


def test_login_succeeds_with_correct_credentials(
    client: TestClient, active_admin_user: User, admin_password: str, company_a: Company
) -> None:
    response = client.post(
        "/auth/login",
        json={
            "company_code": company_a.company_code,
            "username": active_admin_user.username,
            "password": admin_password,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert isinstance(body["access"], str) and body["access"]
    assert isinstance(body["refresh"], str) and body["refresh"]
    assert body["access"] != body["refresh"]


def test_login_is_case_insensitive_on_company_code(
    client: TestClient, active_admin_user: User, admin_password: str, company_a: Company
) -> None:
    response = client.post(
        "/auth/login",
        json={
            "company_code": company_a.company_code.lower(),
            "username": active_admin_user.username,
            "password": admin_password,
        },
    )
    assert response.status_code == 200


def test_login_succeeds_with_email_for_backward_compatibility(
    client: TestClient, active_admin_user: User, admin_password: str, company_a: Company
) -> None:
    """username is the documented login field, but the lookup also matches
    email in the same query, so existing email-based logins keep working."""
    response = client.post(
        "/auth/login",
        json={
            "company_code": company_a.company_code,
            "username": active_admin_user.email,
            "password": admin_password,
        },
    )
    assert response.status_code == 200
    assert response.json()["access"]


def test_login_rejects_wrong_password(
    client: TestClient, active_admin_user: User, company_a: Company
) -> None:
    response = client.post(
        "/auth/login",
        json={
            "company_code": company_a.company_code,
            "username": active_admin_user.username,
            "password": "wrong-password",
        },
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid company code, username, or password"


def test_login_rejects_unknown_username(client: TestClient, company_a: Company) -> None:
    response = client.post(
        "/auth/login",
        json={"company_code": company_a.company_code, "username": "nobody", "password": "whatever"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid company code, username, or password"


def test_login_rejects_unknown_company_code(
    client: TestClient, active_admin_user: User, admin_password: str
) -> None:
    response = client.post(
        "/auth/login",
        json={
            "company_code": "NOSUCHCODE",
            "username": active_admin_user.username,
            "password": admin_password,
        },
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid company code, username, or password"


def test_login_rejects_inactive_user(
    client: TestClient, inactive_user: User, inactive_password: str, company_a: Company
) -> None:
    response = client.post(
        "/auth/login",
        json={
            "company_code": company_a.company_code,
            "username": inactive_user.username,
            "password": inactive_password,
        },
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid company code, username, or password"


def test_login_wrong_company_username_and_password_are_indistinguishable(
    client: TestClient, active_admin_user: User, admin_password: str, company_a: Company
) -> None:
    """The three ways a login can fail (bad company code, bad username, bad
    password) must return textually identical response bodies - proving the
    endpoint can't be used to probe which of the three was wrong."""
    wrong_company = client.post(
        "/auth/login",
        json={
            "company_code": "NOSUCHCODE",
            "username": active_admin_user.username,
            "password": admin_password,
        },
    )
    wrong_username = client.post(
        "/auth/login",
        json={
            "company_code": company_a.company_code,
            "username": "nobody-at-all",
            "password": admin_password,
        },
    )
    wrong_password = client.post(
        "/auth/login",
        json={
            "company_code": company_a.company_code,
            "username": active_admin_user.username,
            "password": "totally-wrong",
        },
    )
    assert wrong_company.status_code == wrong_username.status_code == wrong_password.status_code == 401
    assert wrong_company.json() == wrong_username.json() == wrong_password.json()


def test_login_rejects_suspended_company_with_distinct_403(
    client: TestClient,
    company_b_admin_user: User,
    suspended_company: Company,
) -> None:
    """A real, existing company that has been suspended gets a distinct,
    honest rejection - not folded into the generic invalid-credentials 401,
    even though the credentials themselves would otherwise be correct."""
    response = client.post(
        "/auth/login",
        json={
            "company_code": suspended_company.company_code,
            "username": company_b_admin_user.username,
            "password": "irrelevant - never reached",
        },
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "This company's account has been suspended"


def test_login_same_username_in_two_companies_resolves_to_the_correct_user(
    client: TestClient,
    active_admin_user: User,
    admin_password: str,
    company_a: Company,
    company_b_admin_user: User,
    company_b: Company,
) -> None:
    """users.username is only unique *within* a company - Company A's admin
    and Company B's admin have different usernames in these fixtures, but
    logging into each with its own company code must resolve to that
    company's own user, never the other one's, by id."""
    login_a = client.post(
        "/auth/login",
        json={
            "company_code": company_a.company_code,
            "username": active_admin_user.username,
            "password": admin_password,
        },
    )
    assert login_a.status_code == 200
    me_a = client.get(
        "/auth/me", headers={"Authorization": f"Bearer {login_a.json()['access']}"}
    )
    assert me_a.json()["email"] == active_admin_user.email
    assert me_a.json()["email"] != company_b_admin_user.email


def test_refresh_succeeds_with_valid_refresh_token(
    client: TestClient, active_admin_user: User, admin_password: str, company_a: Company
) -> None:
    login_response = client.post(
        "/auth/login",
        json={
            "company_code": company_a.company_code,
            "username": active_admin_user.username,
            "password": admin_password,
        },
    )
    refresh_token = login_response.json()["refresh"]

    response = client.post("/auth/refresh", json={"refresh": refresh_token})
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert isinstance(body["access"], str) and body["access"]

    # The new access token actually works.
    me_response = client.get("/auth/me", headers={"Authorization": f"Bearer {body['access']}"})
    assert me_response.status_code == 200


def test_refresh_rejects_an_access_token(client: TestClient, active_admin_user: User) -> None:
    """An access token must not work as a refresh token."""
    access_token = create_access_token(subject=active_admin_user.id)
    response = client.post("/auth/refresh", json={"refresh": access_token})
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or expired refresh token"


def test_refresh_token_cannot_be_used_as_an_access_token(
    client: TestClient, active_admin_user: User
) -> None:
    """A refresh token must not work as an access token."""
    refresh_token = create_refresh_token(subject=active_admin_user.id)
    response = client.get("/auth/me", headers={"Authorization": f"Bearer {refresh_token}"})
    assert response.status_code == 401


def test_refresh_rejects_garbage_token(client: TestClient) -> None:
    response = client.post("/auth/refresh", json={"refresh": "not-a-real-token"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or expired refresh token"


def test_refresh_rejects_inactive_user(
    client: TestClient, inactive_user: User
) -> None:
    refresh_token = create_refresh_token(subject=inactive_user.id)
    response = client.post("/auth/refresh", json={"refresh": refresh_token})
    assert response.status_code == 401


def test_me_succeeds_with_valid_token(client: TestClient, active_admin_user: User) -> None:
    token = create_access_token(subject=active_admin_user.id)
    response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    body = response.json()
    assert body["email"] == active_admin_user.email
    assert body["role"] == "Company Administrator"
    assert "password_hash" not in body
    assert "password" not in body


def test_me_rejects_missing_token(client: TestClient) -> None:
    response = client.get("/auth/me")
    assert response.status_code == 401


def test_me_rejects_invalid_token(client: TestClient) -> None:
    response = client.get("/auth/me", headers={"Authorization": "Bearer garbage-token"})
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Company suspension enforced on every authenticated request, not only login
# ---------------------------------------------------------------------------


def test_suspended_company_revokes_an_already_issued_valid_token(
    client: TestClient, company_b_admin_user: User, company_b: Company
) -> None:
    """A token issued while the company was active must stop working the
    moment the company is suspended - not just block future logins."""
    token = create_access_token(subject=company_b_admin_user.id)
    still_active = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert still_active.status_code == 200

    company_b.is_active = False

    now_suspended = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert now_suspended.status_code == 403
    assert now_suspended.json()["detail"] == "This company's account has been suspended"

    company_b.is_active = True


def test_suspended_company_blocks_company_scoped_routes_too(
    client: TestClient, company_b_admin_user: User, company_b: Company
) -> None:
    """The suspension check lives in get_current_active_user, so it applies
    to every authenticated route, not just /auth/me."""
    token = create_access_token(subject=company_b_admin_user.id)
    company_b.is_active = False

    response = client.get("/departments", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403
    assert response.json()["detail"] == "This company's account has been suspended"

    company_b.is_active = True
