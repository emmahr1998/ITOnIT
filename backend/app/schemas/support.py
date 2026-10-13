from pydantic import BaseModel, Field, field_validator

from app.schemas.validators import validate_email_format


class SupportContactRequest(BaseModel):
    """POST /support/contact request body. Public - no authentication
    required, submitted from the Help Center's contact form.

    `website` is a honeypot, not a real field the Help Center form ever
    shows a human visitor (see HelpCenterPage.tsx) - left blank by a human,
    but a bot that blindly fills every input field in a scraped form will
    fill it too. A non-blank value marks the submission as spam; the route
    acknowledges it exactly like a real one (so a bot gets no signal to
    adjust its behavior) but never actually sends an email for it - see
    the route's own docstring.

    name/subject are rejected outright if they contain a line break
    (_reject_line_breaks below) - both end up in email headers (the body
    text and the "[ITOnIT Support] <subject>" Subject line respectively),
    and a header value should never contain one; SmtpEmailService also
    strips any anyway as defense in depth, but rejecting it here means a
    malformed submission never reaches that code at all. `message` has no
    such restriction - it's the email body, where line breaks are normal.
    """

    name: str = Field(min_length=1, max_length=100)
    email: str = Field(min_length=1, max_length=255)
    subject: str = Field(min_length=1, max_length=150)
    message: str = Field(min_length=1, max_length=5000)
    website: str | None = Field(default=None, max_length=200)

    @field_validator("name", "subject")
    @classmethod
    def _reject_line_breaks(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be empty")
        if "\r" in stripped or "\n" in stripped:
            raise ValueError("must not contain line breaks")
        return stripped

    @field_validator("message")
    @classmethod
    def _strip_message(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be empty")
        return stripped

    @field_validator("email")
    @classmethod
    def _valid_email(cls, value: str) -> str:
        return validate_email_format(value)


class SupportContactResponse(BaseModel):
    """POST /support/contact response body - just enough for the Help
    Center form to show its confirmation message."""

    message: str
