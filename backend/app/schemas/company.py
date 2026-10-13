from pydantic import BaseModel, Field, field_validator

from app.schemas.auth import TokenResponse
from app.schemas.validators import validate_company_code_format, validate_email_format


class CompanyRegisterRequest(BaseModel):
    """POST /companies/register request body. Public - no authentication
    required.

    Creates a brand new company (tenant) together with its first user, who
    is always the Company Administrator - see
    CompanyService.register_company. Deliberately has no role_id,
    company_id, or company_code field: the caller can never choose any of
    them. Employees and Technicians are never created through this
    endpoint - only through POST /users, by a Company Administrator this
    endpoint creates.

    company_code is never accepted here, by design: the backend always
    generates a unique one (see CompanyService._generate_unique_company_code)
    for this endpoint. A request body that includes a "company_code" field
    anyway is not rejected - Pydantic's default behavior silently ignores
    unrecognized fields - but since this model has no such field, nothing
    reads it: register_company() is never called with that value, so it
    can never influence the resulting company code (see
    test_company_registration.py's "cannot override" test). System
    Administrator company provisioning, which does need an explicit code,
    uses its own PlatformCompanyRegisterRequest below instead of this one.
    """

    company_name: str = Field(min_length=1, max_length=200)
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    username: str = Field(min_length=1, max_length=50)
    email: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=8)

    @field_validator("company_name", "first_name", "last_name", "username", "email")
    @classmethod
    def _strip(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be empty")
        return stripped

    @field_validator("email")
    @classmethod
    def _valid_email(cls, value: str) -> str:
        return validate_email_format(value)


class PlatformCompanyRegisterRequest(CompanyRegisterRequest):
    """POST /platform/companies request body. System-Administrator-only.

    Extends the public registration fields with a required company_code:
    unlike public self-registration, a System Administrator provisioning a
    tenant on a customer's behalf chooses the code explicitly (see
    PlatformService.create_company, which passes it to
    CompanyService.register_company's own company_code parameter). Kept as
    its own schema, separate from CompanyRegisterRequest, specifically so
    the public endpoint's request type can never carry a company_code
    field at all.
    """

    company_code: str = Field(min_length=3, max_length=20)

    @field_validator("company_code")
    @classmethod
    def _valid_code(cls, value: str) -> str:
        return validate_company_code_format(value)


class CompanyRegisterResponse(TokenResponse):
    """POST /companies/register response body: the same access/refresh
    tokens POST /auth/login returns, plus the company_code the new company
    actually ended up with (always system-generated for this endpoint -
    see CompanyRegisterRequest's own docstring) - so the newly created
    Company Administrator can see and share it immediately after
    registering.
    """

    company_code: str


def company_logo_url(company_id: int, logo_path: str | None) -> str | None:
    """Turn a stored logo filename into the public, fetchable URL for it -
    never expose the raw stored filename itself (same reasoning as
    attachments never exposing stored_filename, just a fetch-by-id path).
    Relative to the API root; the frontend prefixes it with API_BASE_URL.
    """
    return f"/companies/{company_id}/logo" if logo_path else None


class CompanySettingsResponse(BaseModel):
    """GET/PATCH /companies/me and POST /companies/me/logo response body.
    Company-Administrator-only - see CompanyService.get_company.
    """

    id: int
    name: str
    company_code: str
    contact_email: str | None
    logo_url: str | None
    timezone: str
    language: str


class CompanyUpdateRequest(BaseModel):
    """PATCH /companies/me request body. Company-Administrator-only.

    Partial update: a field left out of the request body is left
    unchanged. contact_email may be explicitly cleared by sending an empty
    string. timezone/language are deliberately not editable here -
    they're simple stored settings for now (see Company model), with no
    localization/timezone-conversion system built yet.
    """

    name: str | None = Field(default=None, min_length=1, max_length=200)
    company_code: str | None = Field(default=None, min_length=3, max_length=20)
    contact_email: str | None = Field(default=None, max_length=255)

    @field_validator("name")
    @classmethod
    def _strip_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be empty")
        return stripped

    @field_validator("company_code")
    @classmethod
    def _valid_code(cls, value: str | None) -> str | None:
        return value if value is None else validate_company_code_format(value)

    @field_validator("contact_email")
    @classmethod
    def _valid_email(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            # An explicitly-sent empty string clears the field, rather than
            # being rejected as an invalid email.
            return None
        return validate_email_format(stripped)
