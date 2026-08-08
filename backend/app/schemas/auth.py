from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.validators import validate_email_format


class RegisterRequest(BaseModel):
    """POST /auth/register request body. Public - no authentication required.

    Deliberately has no role_id or department_id field: every self-registered
    account is created as an Employee by AuthService.register, regardless of
    what the client sends. Privileged roles (Technician/Company
    Administrator) remain admin-provisioned only, via POST /users.
    """

    username: str = Field(min_length=1, max_length=50)
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    email: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=8)

    @field_validator("username", "first_name", "last_name", "email")
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


class CompanyCodeRequest(BaseModel):
    """POST /auth/resolve-company request body."""

    company_code: str = Field(min_length=1, max_length=20)

    @field_validator("company_code")
    @classmethod
    def _strip(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be empty")
        return stripped


class CompanyResolveResponse(BaseModel):
    """POST /auth/resolve-company response body - just enough for a login
    screen to display which company a code belongs to before asking for
    credentials. Field names are prefixed (company_name/company_logo)
    rather than bare name/logo, so the shape is self-describing on a
    public, unauthenticated endpoint.
    """

    company_name: str
    company_logo: str | None = None


class LoginRequest(BaseModel):
    """POST /auth/login request body.

    company_code identifies which company to look the user up in -
    required, since username/email are only unique *within* a company
    (UNIQUE(company_id, username), UNIQUE(company_id, email)), not
    platform-wide, so there is no way to resolve a login without it.
    ``username`` is the documented login field, but the service looks it up
    against both the username and email columns in one query, so existing
    email-based logins keep working without a second documented field.
    """

    company_code: str = Field(min_length=1, max_length=20)
    username: str
    password: str

    @field_validator("company_code")
    @classmethod
    def _strip(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be empty")
        return stripped


class TokenResponse(BaseModel):
    """POST /auth/login response body."""

    access: str
    refresh: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    """POST /auth/refresh request body."""

    refresh: str


class RefreshResponse(BaseModel):
    """POST /auth/refresh response body: a new access token only."""

    access: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    """Decoded JWT payload, used internally by app.core.security."""

    sub: str
    exp: int
    iat: int | None = None
    type: str


class CurrentUserResponse(BaseModel):
    """GET /auth/me response body. Only safe, non-sensitive fields - never password_hash."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    first_name: str
    last_name: str
    is_active: bool
    role: str

    @field_validator("role", mode="before")
    @classmethod
    def _role_name(cls, value: object) -> object:
        """Accept either a Role object (from the ORM) or a plain string."""
        return value.name if hasattr(value, "name") else value
