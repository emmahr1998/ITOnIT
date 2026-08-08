from pydantic import BaseModel, Field, field_validator

from app.schemas.validators import validate_company_code_format, validate_email_format


class CompanyRegisterRequest(BaseModel):
    """POST /companies/register request body. Public - no authentication
    required.

    Creates a brand new company (tenant) together with its first user, who
    is always the Company Administrator - see
    CompanyService.register_company. Deliberately has no role_id or
    company_id field: the caller can never choose either. Employees and
    Technicians are never created through this endpoint - only through
    POST /users, by a Company Administrator this endpoint creates.
    """

    company_name: str = Field(min_length=1, max_length=200)
    company_code: str = Field(min_length=3, max_length=20)
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

    @field_validator("company_code")
    @classmethod
    def _valid_code(cls, value: str) -> str:
        return validate_company_code_format(value)

    @field_validator("email")
    @classmethod
    def _valid_email(cls, value: str) -> str:
        return validate_email_format(value)
