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


class LoginRequest(BaseModel):
    """POST /auth/login request body.

    ``username`` is the documented login field, but the service looks it up
    against both the username and email columns in one query, so existing
    email-based logins keep working without a second documented field.
    """

    username: str
    password: str


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
