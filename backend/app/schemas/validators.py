import re

# Deliberately not pydantic.EmailStr: that requires the optional
# `email-validator` package, which isn't a project dependency. This regex is
# intentionally permissive (it rejects obvious non-emails like "not-an-email"
# without trying to fully implement RFC 5322) - good enough to catch user
# typos without becoming its own source of false rejections.
_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def validate_email_format(value: str) -> str:
    """Shared email-shape check for every schema with an ``email`` field."""
    if not _EMAIL_PATTERN.match(value):
        raise ValueError("must be a valid email address")
    return value
