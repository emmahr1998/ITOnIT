from pydantic import BaseModel, ConfigDict, field_validator


class LoginRequest(BaseModel):
    """POST /auth/login request body."""

    email: str
    password: str


class TokenResponse(BaseModel):
    """POST /auth/login response body."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenPayload(BaseModel):
    """Decoded JWT payload, used internally by app.core.security."""

    sub: str
    exp: int
    iat: int | None = None


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
