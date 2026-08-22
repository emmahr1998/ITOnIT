from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.department import DepartmentResponse
from app.schemas.types import UTCDatetime
from app.schemas.validators import validate_email_format


class UserCreate(BaseModel):
    """POST /users request body. Admin-only.

    Never accepts a role by name or a pre-hashed password - only a
    role_id (validated against the roles table) and a plaintext password
    (hashed by the service, never stored or returned as-is).
    """

    username: str = Field(min_length=1, max_length=50)
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    email: str = Field(min_length=1, max_length=255)
    department_id: int | None = None
    phone_number: str | None = Field(default=None, max_length=30)
    password: str = Field(min_length=8)
    role_id: int
    theme: str | None = Field(default=None, max_length=20)

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


class UserUpdate(BaseModel):
    """PATCH /users/{id} request body - partial update, never a password.

    Administrative fields (username, email, role_id, is_active,
    department_id) may only be changed by a Company Administrator. A user
    editing their own profile may only change the "safe" fields:
    first_name, last_name, phone_number, theme. UserService enforces this
    split - it is never duplicated in the route.
    """

    username: str | None = Field(default=None, min_length=1, max_length=50)
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    email: str | None = Field(default=None, min_length=1, max_length=255)
    department_id: int | None = None
    phone_number: str | None = Field(default=None, max_length=30)
    role_id: int | None = None
    is_active: bool | None = None
    theme: str | None = Field(default=None, max_length=20)

    @field_validator("username", "first_name", "last_name", "email")
    @classmethod
    def _strip(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be empty")
        return stripped

    @field_validator("email")
    @classmethod
    def _valid_email(cls, value: str | None) -> str | None:
        return value if value is None else validate_email_format(value)


class PasswordChangeRequest(BaseModel):
    """PATCH /users/me/password request body."""

    current_password: str
    new_password: str = Field(min_length=8)


class AdminPasswordSetRequest(BaseModel):
    """PATCH /users/{id}/password request body. Admin-only, no current
    password check.
    """

    new_password: str = Field(min_length=8)


class UserResponse(BaseModel):
    """User representation returned by the API - never password/password_hash."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    first_name: str
    last_name: str
    email: str
    phone_number: str | None
    department: DepartmentResponse | None
    role: str
    theme: str | None
    is_active: bool
    created_at: UTCDatetime
    updated_at: UTCDatetime

    @field_validator("role", mode="before")
    @classmethod
    def _role_name(cls, value: object) -> object:
        """Accept either a Role object (from the ORM) or a plain string."""
        return value.name if hasattr(value, "name") else value
