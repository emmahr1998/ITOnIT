"""Tests for POST /companies/register - Milestone 5: Company Registration +
Default Data Seeding. Covers the whole company-creation transaction: the
company row, its first Company Administrator, and every seeded default
(priorities, categories, location, department) - see
app/services/company_service.py. The old POST /auth/register self-
registration flow this replaces is covered separately in
test_auth.py::test_old_self_registration_endpoint_no_longer_exists.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from app.models.company import Company
from app.models.role import Role
from app.models.user import User
from app.schemas.company import CompanyRegisterRequest
from app.services.company_service import CompanyCodeConflictError, CompanyService
from tests.conftest import COMPANY_A_CODE


def _payload(**overrides: object) -> dict:
    payload = {
        "company_name": "Acme Corp",
        "company_code": "ACME0001",
        "first_name": "Alice",
        "last_name": "Admin",
        "username": "aliceadmin",
        "email": "alice@acme.test",
        "password": "SuperSecret1!",
    }
    payload.update(overrides)
    return payload


def _register(client: TestClient, **overrides: object):
    return client.post("/companies/register", json=_payload(**overrides))


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_register_company_succeeds_and_returns_tokens(client: TestClient) -> None:
    response = _register(client)
    assert response.status_code == 201
    body = response.json()
    assert body["token_type"] == "bearer"
    assert isinstance(body["access"], str) and body["access"]
    assert isinstance(body["refresh"], str) and body["refresh"]
    assert body["access"] != body["refresh"]


def test_register_company_first_user_is_company_administrator(client: TestClient) -> None:
    response = _register(client, company_code="ROLECHK1", username="rolechkadmin", email="rolechk@example.com")
    access = response.json()["access"]
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {access}"})
    assert me.status_code == 200
    assert me.json()["role"] == "Company Administrator"


def test_register_company_returned_tokens_work_with_me(client: TestClient) -> None:
    response = _register(client, company_code="TOKCHK01", username="tokchkadmin", email="tokchk@example.com")
    access = response.json()["access"]
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {access}"})
    assert me.status_code == 200
    body = me.json()
    assert body["email"] == "tokchk@example.com"
    assert body["first_name"] == "Alice"
    assert "password" not in body
    assert "password_hash" not in body


def test_register_company_user_is_scoped_to_the_new_company_only(client: TestClient) -> None:
    """The new admin must be reachable by logging into the *new* company's
    own code - and nowhere else - proving it's a real, distinct tenant, not
    attached to any pre-existing company."""
    payload = _payload(company_code="SCOPECHK", username="scopechkadmin", email="scopechk@example.com")
    _register(client, **payload)

    own_login = client.post(
        "/auth/login",
        json={
            "company_code": payload["company_code"],
            "username": payload["username"],
            "password": payload["password"],
        },
    )
    assert own_login.status_code == 200

    # Same username/password does not exist under an unrelated company code.
    wrong_company_login = client.post(
        "/auth/login",
        json={
            "company_code": COMPANY_A_CODE,
            "username": payload["username"],
            "password": payload["password"],
        },
    )
    assert wrong_company_login.status_code == 401


# ---------------------------------------------------------------------------
# Default data seeding
# ---------------------------------------------------------------------------


def _register_and_headers(client: TestClient, **overrides: object) -> dict[str, str]:
    response = _register(client, **overrides)
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['access']}"}


def test_register_company_seeds_four_starter_priorities(client: TestClient) -> None:
    headers = _register_and_headers(
        client, company_code="SEEDPRI1", username="seedpriadmin", email="seedpri@example.com"
    )
    response = client.get("/priorities", headers=headers)
    assert response.status_code == 200
    priorities = response.json()["data"]
    assert len(priorities) == 4
    assert {p["title"] for p in priorities} == {"Low", "Medium", "High", "Critical"}


def test_register_company_seeds_five_starter_categories(client: TestClient) -> None:
    headers = _register_and_headers(
        client, company_code="SEEDCAT1", username="seedcatadmin", email="seedcat@example.com"
    )
    response = client.get("/categories", headers=headers)
    assert response.status_code == 200
    categories = response.json()
    assert len(categories) == 5
    assert {c["name"] for c in categories} == {
        "Hardware",
        "Software",
        "Network",
        "Account Access",
        "Other",
    }


def test_register_company_seeds_head_office_location(client: TestClient) -> None:
    headers = _register_and_headers(
        client, company_code="SEEDLOC1", username="seedlocadmin", email="seedloc@example.com"
    )
    response = client.get("/locations", headers=headers)
    assert response.status_code == 200
    locations = response.json()["data"]
    assert len(locations) == 1
    assert locations[0]["title"] == "Head Office"


def test_register_company_seeds_general_department(client: TestClient) -> None:
    headers = _register_and_headers(
        client, company_code="SEEDDEP1", username="seeddepadmin", email="seeddep@example.com"
    )
    response = client.get("/departments", headers=headers)
    assert response.status_code == 200
    departments = response.json()["data"]
    assert len(departments) == 1
    assert departments[0]["title"] == "General"


# ---------------------------------------------------------------------------
# Uniqueness rules
# ---------------------------------------------------------------------------


def test_register_company_rejects_duplicate_company_code(
    client: TestClient, company_a: Company
) -> None:
    """company_code must be unique platform-wide - company_a's fixture code
    is already taken before this test even runs a registration."""
    response = _register(
        client,
        company_code=company_a.company_code,
        username="whoever",
        email="whoever@example.com",
    )
    assert response.status_code == 409
    assert "company code" in response.json()["detail"].lower()


def test_register_company_rejects_duplicate_company_code_case_insensitively(
    client: TestClient, company_a: Company
) -> None:
    response = _register(
        client,
        company_code=company_a.company_code.lower(),
        username="whoever2",
        email="whoever2@example.com",
    )
    assert response.status_code == 409


def test_register_company_second_registration_reuses_a_freed_looking_code_still_fails(
    client: TestClient,
) -> None:
    """Registering twice with the exact same code back-to-back must fail
    the second time - proves the first registration's company_code is
    actually persisted and checked, not silently dropped."""
    first = _register(client, company_code="TAKEN001", username="firstadmin", email="first@example.com")
    assert first.status_code == 201

    second = _register(client, company_code="TAKEN001", username="secondadmin", email="second@example.com")
    assert second.status_code == 409


def test_register_company_rejects_invalid_company_code_format(client: TestClient) -> None:
    response = _register(client, company_code="not a valid code!", username="badcode", email="badcode@example.com")
    assert response.status_code == 422


def test_register_company_rejects_too_short_company_code(client: TestClient) -> None:
    response = _register(client, company_code="AB", username="shortcode", email="shortcode@example.com")
    assert response.status_code == 422


def test_register_company_rejects_short_password(client: TestClient) -> None:
    response = _register(client, company_code="WEAKPW01", username="weakpw", email="weakpw@example.com", password="short")
    assert response.status_code == 422


def test_register_company_same_username_and_email_allowed_across_two_companies(
    client: TestClient,
) -> None:
    """username/email are unique *within* a company, not platform-wide - two
    independently registered companies each choosing "owner"/the same email
    for their first admin must both succeed."""
    first = _register(
        client,
        company_code="SHARE0001",
        username="owner",
        email="owner@shared-example.com",
    )
    assert first.status_code == 201

    second = _register(
        client,
        company_code="SHARE0002",
        username="owner",
        email="owner@shared-example.com",
    )
    assert second.status_code == 201


# ---------------------------------------------------------------------------
# Client cannot choose role or company
# ---------------------------------------------------------------------------


def test_register_company_ignores_client_supplied_role_id(client: TestClient) -> None:
    """CompanyRegisterRequest has no role_id field at all - an extra field
    in the request body is silently ignored by Pydantic, never reaching
    CompanyService. The created user is still exactly a Company
    Administrator regardless of what was sent."""
    response = client.post(
        "/companies/register",
        json={**_payload(company_code="NOROLE01", username="noroleadmin", email="norole@example.com"), "role_id": 999},
    )
    assert response.status_code == 201
    access = response.json()["access"]
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {access}"})
    assert me.json()["role"] == "Company Administrator"


def test_register_company_ignores_client_supplied_company_id(
    client: TestClient, company_a: Company
) -> None:
    """CompanyRegisterRequest has no company_id field - trying to attach the
    new user to an existing company (company_a) by id has no effect. The
    new user is only reachable through the brand new company_code, never
    through company_a's."""
    payload = _payload(company_code="NOCOID01", username="nocoidadmin", email="nocoid@example.com")
    response = client.post("/companies/register", json={**payload, "company_id": company_a.id})
    assert response.status_code == 201

    wrong_company_login = client.post(
        "/auth/login",
        json={
            "company_code": company_a.company_code,
            "username": payload["username"],
            "password": payload["password"],
        },
    )
    assert wrong_company_login.status_code == 401

    own_login = client.post(
        "/auth/login",
        json={
            "company_code": payload["company_code"],
            "username": payload["username"],
            "password": payload["password"],
        },
    )
    assert own_login.status_code == 200


# ---------------------------------------------------------------------------
# Cross-company isolation, exercised through the registration entry point
# ---------------------------------------------------------------------------


def test_two_registered_companies_cannot_see_each_others_seeded_data(client: TestClient) -> None:
    """Both companies seed identically-named starter data (same four
    priority titles, same "General" department, ...), so a content-only
    check could pass even with real cross-tenant leakage - counts are what
    actually prove isolation here."""
    headers_x = _register_and_headers(
        client, company_code="ISOX0001", username="isoxadmin", email="isox@example.com"
    )
    headers_y = _register_and_headers(
        client, company_code="ISOY0001", username="isoyadmin", email="isoy@example.com"
    )

    priorities_x = client.get("/priorities", headers=headers_x).json()["data"]
    priorities_y = client.get("/priorities", headers=headers_y).json()["data"]
    assert len(priorities_x) == 4
    assert len(priorities_y) == 4
    assert {p["id"] for p in priorities_x}.isdisjoint({p["id"] for p in priorities_y})

    users_x = client.get("/users", headers=headers_x).json()["data"]
    users_y = client.get("/users", headers=headers_y).json()["data"]
    assert len(users_x) == 1
    assert len(users_y) == 1
    assert users_x[0]["email"] == "isox@example.com"
    assert users_y[0]["email"] == "isoy@example.com"


# ---------------------------------------------------------------------------
# Transaction rollback on failure (service-level - see the module docstring
# on why this uses purpose-built, rollback-aware fakes rather than the
# shared conftest ones, which don't model staged-vs-committed state).
# ---------------------------------------------------------------------------


class _StagedCompanyRepository:
    """Unlike conftest's FakeCompanyRepository, distinguishes rows created
    within the current transaction (staged) from ones actually committed -
    needed to prove a failure leaves *nothing* behind, not just that the
    right exception was raised."""

    def __init__(self) -> None:
        self._committed: dict[int, Company] = {}
        self._staged: dict[int, Company] = {}
        self._next_id = 1

    def get_by_code(self, company_code: str) -> Company | None:
        target = company_code.strip().lower()
        return next(
            (c for c in self._committed.values() if c.company_code.lower() == target), None
        )

    def create(self, obj: Company) -> Company:
        obj.id = self._next_id
        self._next_id += 1
        self._staged[obj.id] = obj
        return obj

    def commit_staged(self) -> None:
        self._committed.update(self._staged)
        self._staged.clear()

    def discard_staged(self) -> None:
        self._staged.clear()


class _StagedUserRepository:
    def __init__(self) -> None:
        self._committed: dict[int, User] = {}
        self._staged: dict[int, User] = {}
        self._next_id = 1

    def create(self, obj: User) -> User:
        obj.id = self._next_id
        self._next_id += 1
        self._staged[obj.id] = obj
        return obj

    def commit_staged(self) -> None:
        self._committed.update(self._staged)
        self._staged.clear()

    def discard_staged(self) -> None:
        self._staged.clear()

    def all_committed(self) -> list[User]:
        return list(self._committed.values())


class _FailingPriorityRepository:
    """Simulates a failure partway through default-data seeding - after the
    company and its admin user already exist in the same transaction."""

    def create(self, obj: object) -> object:
        raise IntegrityError("insert", {}, Exception("simulated seeding failure"))


class _StagedSession:
    def __init__(self, *staged_repos: _StagedCompanyRepository | _StagedUserRepository) -> None:
        self._repos = staged_repos
        self.committed = False
        self.rolled_back = False

    def commit(self) -> None:
        self.committed = True
        for repo in self._repos:
            repo.commit_staged()

    def rollback(self) -> None:
        self.rolled_back = True
        for repo in self._repos:
            repo.discard_staged()


def test_register_company_rolls_back_company_and_user_if_seeding_fails(
    role_repository,
) -> None:
    company_repository = _StagedCompanyRepository()
    user_repository = _StagedUserRepository()
    session = _StagedSession(company_repository, user_repository)

    service = CompanyService(
        db=session,
        company_repository=company_repository,
        role_repository=role_repository,
        user_repository_factory=lambda company_id: user_repository,
        priority_repository_factory=lambda company_id: _FailingPriorityRepository(),
        category_repository_factory=lambda company_id: None,
        location_repository_factory=lambda company_id: None,
        department_repository_factory=lambda company_id: None,
    )

    payload = CompanyRegisterRequest(**_payload(company_code="ROLLBACK1", username="rollbackadmin", email="rollback@example.com"))

    with pytest.raises(CompanyCodeConflictError):
        service.register_company(payload)

    assert session.rolled_back is True
    assert session.committed is False
    # Nothing survives the rollback - not the company, not its admin user.
    assert company_repository.get_by_code("ROLLBACK1") is None
    assert user_repository.all_committed() == []


def test_register_company_missing_role_raises_before_creating_anything(
    company_repository,
) -> None:
    """If the Company Administrator role somehow isn't seeded (a deployment
    invariant, not something a client can trigger), registration must fail
    loudly before touching the company table at all."""

    class _EmptyRoleRepository:
        def get_by_name(self, name: str) -> Role | None:
            return None

    service = CompanyService(
        db=_StagedSession(),
        company_repository=company_repository,
        role_repository=_EmptyRoleRepository(),
    )
    payload = CompanyRegisterRequest(**_payload(company_code="NOROLESE", username="norolesee", email="norolesee@example.com"))

    with pytest.raises(RuntimeError):
        service.register_company(payload)

    assert company_repository.get_by_code("NOROLESE") is None
