from pydantic import BaseModel, ConfigDict, field_validator


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
