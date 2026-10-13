"""Tests for POST /companies/register - Milestone 5: Company Registration +
Default Data Seeding. Covers the whole company-creation transaction: the
company row, its first Company Administrator, and every seeded default
(priorities, categories, location, department) - see
app/services/company_service.py. The old POST /auth/register self-
registration flow this replaces is covered separately in
test_auth.py::test_old_self_registration_endpoint_no_longer_exists.
"""

import inspect
import re
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from app.models.company import Company
from app.models.role import Role
from app.models.user import User
from app.schemas.company import CompanyRegisterRequest, PlatformCompanyRegisterRequest
from app.services.company_service import CompanyCodeConflictError, CompanyService
from app.services.email_service import SmtpEmailService
from tests.conftest import COMPANY_A_CODE, FakeCompanyRepository, FakeEmailService

# Mirrors CompanyService's own generated-code shape: "IT-" + 6 characters
# from its alphabet (digits/uppercase letters, excluding 0/O/1/I).
_GENERATED_CODE_PATTERN = re.compile(r"^IT-[2-9A-HJ-NP-Z]{6}$")


def _payload(**overrides: object) -> dict:
    """A valid POST /companies/register body. Deliberately has no
    company_code key: CompanyRegisterRequest has no such field (see its own
    docstring) - public registration always gets a system-generated one.
    Tests that need an explicit, caller-chosen code (System Administrator
    provisioning) use PlatformCompanyRegisterRequest / POST
    /platform/companies instead - see the "Explicit company_code" section
    below.
    """
    payload = {
        "company_name": "Acme Corp",
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
    response = _register(client, username="rolechkadmin", email="rolechk@example.com")
    access = response.json()["access"]
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {access}"})
    assert me.status_code == 200
    assert me.json()["role"] == "Company Administrator"


def test_register_company_returned_tokens_work_with_me(client: TestClient) -> None:
    response = _register(client, username="tokchkadmin", email="tokchk@example.com")
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
    own (system-generated) code - and nowhere else - proving it's a real,
    distinct tenant, not attached to any pre-existing company."""
    payload = _payload(username="scopechkadmin", email="scopechk@example.com")
    response = _register(client, **payload)
    assert response.status_code == 201
    generated_code = response.json()["company_code"]

    own_login = client.post(
        "/auth/login",
        json={
            "company_code": generated_code,
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
        client, username="seedpriadmin", email="seedpri@example.com"
    )
    response = client.get("/priorities", headers=headers)
    assert response.status_code == 200
    priorities = response.json()["data"]
    assert len(priorities) == 4
    assert {p["title"] for p in priorities} == {"Low", "Medium", "High", "Critical"}


def test_register_company_seeds_five_starter_categories(client: TestClient) -> None:
    headers = _register_and_headers(
        client, username="seedcatadmin", email="seedcat@example.com"
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
        client, username="seedlocadmin", email="seedloc@example.com"
    )
    response = client.get("/locations", headers=headers)
    assert response.status_code == 200
    locations = response.json()["data"]
    assert len(locations) == 1
    assert locations[0]["title"] == "Head Office"


def test_register_company_seeds_general_department(client: TestClient) -> None:
    headers = _register_and_headers(
        client, username="seeddepadmin", email="seeddep@example.com"
    )
    response = client.get("/departments", headers=headers)
    assert response.status_code == 200
    departments = response.json()["data"]
    assert len(departments) == 1
    assert departments[0]["title"] == "General"


def test_register_company_seeds_eleven_starter_inventory_categories(
    client: TestClient, inventory_category_repository
) -> None:
    """No /inventory-categories route exists yet (Phase 10.1 is model +
    migration + seeding only - see Milestone 10's approved scope), so this
    inspects the fake repository CompanyService actually wrote to, rather
    than going through an HTTP GET the way the other starter-data tests do.
    inventory_category_repository starts empty (see its fixture) and this
    test performs the only registration that touches it, so everything in
    it afterward was seeded by this one call.
    """
    response = _register(client, username="seedinvadmin", email="seedinv@example.com")
    assert response.status_code == 201

    seeded = inventory_category_repository.get_all()
    assert len(seeded) == 11
    assert {c.name for c in seeded} == {
        "Laptop",
        "Desktop",
        "Monitor",
        "Printer",
        "Keyboard",
        "Mouse",
        "Dock",
        "Phone",
        "Network Equipment",
        "Cable",
        "Other",
    }
    assert all(c.is_active for c in seeded)


# ---------------------------------------------------------------------------
# Uniqueness rules
#
# Duplicate/invalid *explicit* company_code rejection is no longer
# reachable through this public endpoint at all - CompanyRegisterRequest
# has no company_code field, so there's nothing for a public caller to
# supply a bad or taken value for (see the "cannot choose a company_code"
# section below, and PlatformCompanyRegisterRequest's own equivalent tests
# further down for the one schema that still accepts an explicit code).
# What remains in scope here is collision handling for *generated* codes,
# covered directly against CompanyService._generate_unique_company_code.
# ---------------------------------------------------------------------------


def test_register_company_rejects_short_password(client: TestClient) -> None:
    response = _register(client, username="weakpw", email="weakpw@example.com", password="short")
    assert response.status_code == 422


def test_register_company_same_username_and_email_allowed_across_two_companies(
    client: TestClient,
) -> None:
    """username/email are unique *within* a company, not platform-wide - two
    independently registered companies each choosing "owner"/the same email
    for their first admin must both succeed, even though each gets its own
    distinct system-generated company_code."""
    first = _register(client, username="owner", email="owner@shared-example.com")
    assert first.status_code == 201

    second = _register(client, username="owner", email="owner@shared-example.com")
    assert second.status_code == 201
    assert first.json()["company_code"] != second.json()["company_code"]


# ---------------------------------------------------------------------------
# Automatic company code generation - the only behavior POST
# /companies/register has at all now (see CompanyService.register_company/
# _generate_unique_company_code): CompanyRegisterRequest has no
# company_code field to omit or include, so every public registration goes
# through this path unconditionally.
# ---------------------------------------------------------------------------


def test_register_company_succeeds_without_company_code(client: TestClient) -> None:
    response = _register(client, username="autocodeadmin", email="autocode@example.com")
    assert response.status_code == 201, response.text


def test_register_company_without_code_generates_one_in_expected_format(
    client: TestClient,
) -> None:
    response = _register(client, username="formatadmin", email="format@example.com")
    body = response.json()
    assert "company_code" in body
    assert _GENERATED_CODE_PATTERN.match(body["company_code"]), body["company_code"]


def test_register_company_without_code_never_derives_it_from_the_company_name(
    client: TestClient,
) -> None:
    """The generated code must not leak/encode the company name - e.g. no
    "ACME"-looking prefix - it's drawn purely from the random alphabet."""
    response = _register(
        client,
        company_name="A Very Distinctive Company Name LLC",
        username="noderiveadmin",
        email="noderive@example.com",
    )
    code = response.json()["company_code"]
    assert "AVER" not in code.upper()
    assert _GENERATED_CODE_PATTERN.match(code)


def test_register_company_generated_code_is_returned_and_actually_usable_to_log_in(
    client: TestClient,
) -> None:
    """The code in the response isn't just cosmetic - it's the real,
    persisted company_code, usable immediately via both resolve-company and
    login."""
    response = _register(
        client,
        username="usablecodeadmin",
        email="usablecode@example.com",
        password="SuperSecret1!",
    )
    code = response.json()["company_code"]

    resolved = client.post("/auth/resolve-company", json={"company_code": code})
    assert resolved.status_code == 200
    assert resolved.json()["company_name"] == "Acme Corp"

    login = client.post(
        "/auth/login",
        json={"company_code": code, "username": "usablecodeadmin", "password": "SuperSecret1!"},
    )
    assert login.status_code == 200


def test_register_company_without_code_generates_unique_codes_across_calls(
    client: TestClient,
) -> None:
    codes = set()
    for i in range(5):
        response = _register(
            client, username=f"uniqcodeadmin{i}", email=f"uniqcode{i}@example.com"
        )
        assert response.status_code == 201, response.text
        codes.add(response.json()["company_code"])
    assert len(codes) == 5


def test_generate_unique_company_code_retries_past_a_collision(
    company_repository: FakeCompanyRepository,
) -> None:
    """Directly exercises CompanyService._generate_unique_company_code's
    retry loop: the first candidate collides with an already-taken code,
    the second doesn't, and the method must return the second one rather
    than raising or returning the taken one."""
    taken = Company(
        id=999,
        name="Already Registered Co",
        company_code="IT-AAAAAA",
        timezone="UTC",
        language="en",
        is_active=True,
    )
    company_repository.create(taken)

    service = CompanyService(db=None, company_repository=company_repository)  # type: ignore[arg-type]
    with patch(
        "app.services.company_service._generate_company_code_candidate",
        side_effect=["IT-AAAAAA", "IT-BBBBBB"],
    ) as mock_candidate:
        code = service._generate_unique_company_code()

    assert code == "IT-BBBBBB"
    assert mock_candidate.call_count == 2


def test_generate_unique_company_code_gives_up_after_max_attempts(
    company_repository: FakeCompanyRepository,
) -> None:
    """If every candidate collides (never happens in practice given the
    ~1.07 billion-code space, but must still fail loudly rather than
    silently returning a taken code or looping forever)."""
    taken = Company(
        id=999,
        name="Already Registered Co",
        company_code="IT-AAAAAA",
        timezone="UTC",
        language="en",
        is_active=True,
    )
    company_repository.create(taken)

    service = CompanyService(db=None, company_repository=company_repository)  # type: ignore[arg-type]
    with patch(
        "app.services.company_service._generate_company_code_candidate",
        return_value="IT-AAAAAA",
    ):
        with pytest.raises(RuntimeError):
            service._generate_unique_company_code()


# ---------------------------------------------------------------------------
# Public registration cannot be used to choose a company_code at all.
# CompanyRegisterRequest has no such field - structurally, not just by
# convention - so a request body that includes one anyway must have no
# effect on the result (Pydantic's default extra="ignore" silently drops
# it before CompanyService.register_company ever runs).
# ---------------------------------------------------------------------------


def test_company_register_request_schema_has_no_company_code_field() -> None:
    """The strongest guarantee here isn't behavioral, it's structural: this
    model simply has no company_code field to read, so no code path in
    register_company()/the /companies/register route could pass one
    through even by accident."""
    assert "company_code" not in CompanyRegisterRequest.model_fields


def test_register_company_cannot_choose_company_code_via_request_body(
    client: TestClient,
) -> None:
    """Sending company_code="MYCODE" in the request body must not make the
    new company's code "MYCODE" - the backend still generates a unique
    "IT-XXXXXX" code exactly as if the field had never been sent at all."""
    response = client.post(
        "/companies/register",
        json={
            **_payload(username="nocodechoice", email="nocodechoice@example.com"),
            "company_code": "MYCODE",
        },
    )
    assert response.status_code == 201, response.text
    code = response.json()["company_code"]
    assert code != "MYCODE"
    assert _GENERATED_CODE_PATTERN.match(code), code

    # "MYCODE" was never persisted as any company's code...
    not_found = client.post("/auth/resolve-company", json={"company_code": "MYCODE"})
    assert not_found.status_code == 404
    cannot_login = client.post(
        "/auth/login",
        json={"company_code": "MYCODE", "username": "nocodechoice", "password": "SuperSecret1!"},
    )
    assert cannot_login.status_code == 401

    # ...only the real, system-generated one works.
    resolved = client.post("/auth/resolve-company", json={"company_code": code})
    assert resolved.status_code == 200


# ---------------------------------------------------------------------------
# Explicit company_code: System Administrator provisioning only. Unlike
# public self-registration, POST /platform/companies uses its own
# PlatformCompanyRegisterRequest schema (extends CompanyRegisterRequest
# with a required company_code), passed through explicitly to
# CompanyService.register_company's own company_code parameter - see
# PlatformService.create_company.
# ---------------------------------------------------------------------------


def test_platform_company_register_request_requires_company_code() -> None:
    with pytest.raises(ValidationError):
        PlatformCompanyRegisterRequest(
            company_name="No Code Co",
            first_name="Pat",
            last_name="Admin",
            username="nocodeadmin",
            email="nocode@example.com",
            password="SuperSecret1!",
        )


def test_platform_company_register_request_validates_company_code_format() -> None:
    with pytest.raises(ValidationError):
        PlatformCompanyRegisterRequest(
            company_name="Bad Code Co",
            company_code="not a valid code!",
            first_name="Pat",
            last_name="Admin",
            username="badcodeadmin",
            email="badcode@example.com",
            password="SuperSecret1!",
        )


def test_platform_provisioning_with_explicit_code_does_not_generate_one(
    client: TestClient, auth_headers, active_system_administrator_user
) -> None:
    """System Administrator provisioning (POST /platform/companies) still
    lets the caller choose company_code explicitly - the one route whose
    request schema still has that field at all."""
    response = client.post(
        "/platform/companies",
        json={
            "company_name": "Provisioned By Admin",
            "company_code": "EXPLICIT1",
            "first_name": "Pat",
            "last_name": "Admin",
            "username": "explicitadmin",
            "email": "explicit@example.com",
            "password": "SuperSecret1!",
        },
        headers=auth_headers(active_system_administrator_user),
    )
    assert response.status_code == 201, response.text
    assert response.json()["data"]["company_code"] == "EXPLICIT1"


# ---------------------------------------------------------------------------
# Client cannot choose role or company (company_code is covered in its own
# dedicated section above).
# ---------------------------------------------------------------------------


def test_register_company_ignores_client_supplied_role_id(client: TestClient) -> None:
    """CompanyRegisterRequest has no role_id field at all - an extra field
    in the request body is silently ignored by Pydantic, never reaching
    CompanyService. The created user is still exactly a Company
    Administrator regardless of what was sent."""
    response = client.post(
        "/companies/register",
        json={**_payload(username="noroleadmin", email="norole@example.com"), "role_id": 999},
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
    new user is only reachable through the brand new, system-generated
    company_code, never through company_a's."""
    payload = _payload(username="nocoidadmin", email="nocoid@example.com")
    response = client.post("/companies/register", json={**payload, "company_id": company_a.id})
    assert response.status_code == 201
    generated_code = response.json()["company_code"]

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
            "company_code": generated_code,
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
    headers_x = _register_and_headers(client, username="isoxadmin", email="isox@example.com")
    headers_y = _register_and_headers(client, username="isoyadmin", email="isoy@example.com")

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

    payload = CompanyRegisterRequest(**_payload(username="rollbackadmin", email="rollback@example.com"))

    with pytest.raises(CompanyCodeConflictError):
        service.register_company(payload, company_code="ROLLBACK1")

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
    payload = CompanyRegisterRequest(**_payload(username="norolesee", email="norolesee@example.com"))

    with pytest.raises(RuntimeError):
        service.register_company(payload, company_code="NOROLESE")

    assert company_repository.get_by_code("NOROLESE") is None


# ---------------------------------------------------------------------------
# Public-registration welcome email (the generated company code, sent to
# the new Company Administrator's email address) - see
# app/services/email_service.py and
# CompanyService._send_welcome_email_best_effort. Every test below uses
# FakeEmailService (see conftest.py's client fixture, which wires it into
# the same CompanyService instance both POST /companies/register and POST
# /platform/companies use) - no test anywhere in this suite ever opens a
# real SMTP connection.
# ---------------------------------------------------------------------------


def test_register_company_sends_exactly_one_welcome_email_to_the_admin(
    client: TestClient, email_service: FakeEmailService
) -> None:
    """Covers: triggers exactly one email, to the correct recipient,
    with the correct company name and the exact generated code the
    registration response itself returned."""
    response = _register(client, username="welcomeemailadmin", email="welcomeemail@example.com")
    assert response.status_code == 201, response.text
    generated_code = response.json()["company_code"]

    assert len(email_service.sent) == 1
    to_email, company_name, company_code = email_service.sent[0]
    assert to_email == "welcomeemail@example.com"
    assert company_name == "Acme Corp"
    assert company_code == generated_code


def test_welcome_email_signature_has_no_password_or_token_parameters() -> None:
    """Structural guarantee, not just behavioral: send_company_registered_email
    has no password/token parameter at all - no code path anywhere could
    pass one through even by accident."""
    sig = inspect.signature(SmtpEmailService.send_company_registered_email)
    assert set(sig.parameters) - {"self"} == {"to_email", "company_name", "company_code"}


def test_register_company_welcome_email_contains_no_password_or_tokens(
    client: TestClient, email_service: FakeEmailService
) -> None:
    response = _register(
        client,
        username="emailsecretcheck",
        email="emailsecretcheck@example.com",
        password="SuperSecret1!",
    )
    assert response.status_code == 201
    body = response.json()
    access, refresh = body["access"], body["refresh"]

    assert len(email_service.sent) == 1
    for value in email_service.sent[0]:
        assert "SuperSecret1!" not in value
        assert access not in value
        assert refresh not in value


def test_register_company_email_delivery_failure_does_not_fail_registration(
    client: TestClient, email_service: FakeEmailService
) -> None:
    """Covers: email-service failure does not fail registration, and
    afterward the company still exists and its generated code still works
    for login - registration is fully unaffected by the simulated SMTP
    failure."""
    email_service.fail_next_send = True

    response = _register(client, username="emailfailadmin", email="emailfail@example.com")
    assert response.status_code == 201, response.text
    code = response.json()["company_code"]

    login = client.post(
        "/auth/login",
        json={"company_code": code, "username": "emailfailadmin", "password": "SuperSecret1!"},
    )
    assert login.status_code == 200


def test_register_company_succeeds_when_smtp_not_configured(
    client: TestClient, email_service: FakeEmailService
) -> None:
    """"Not configured" (e.g. a fresh local .env with no SMTP section) must
    never crash or block registration - sending is simply skipped."""
    email_service.is_configured = False

    response = _register(client, username="nosmtpadmin", email="nosmtp@example.com")
    assert response.status_code == 201, response.text
    assert email_service.sent == []


def test_platform_provisioning_does_not_send_public_registration_email(
    client: TestClient,
    auth_headers,
    active_system_administrator_user,
    email_service: FakeEmailService,
) -> None:
    """System Administrator provisioning (POST /platform/companies) shares
    CompanyService.register_company with public self-registration, but
    never passes send_welcome_email=True - this welcome email is specific
    to public registration, not a general consequence of company
    creation."""
    response = client.post(
        "/platform/companies",
        json={
            "company_name": "No Email Co",
            "company_code": "NOEMAIL1",
            "first_name": "Pat",
            "last_name": "Admin",
            "username": "noemailadmin",
            "email": "noemail@example.com",
            "password": "SuperSecret1!",
        },
        headers=auth_headers(active_system_administrator_user),
    )
    assert response.status_code == 201, response.text
    assert email_service.sent == []
