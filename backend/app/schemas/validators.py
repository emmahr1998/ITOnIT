import re

# Deliberately not pydantic.EmailStr: that requires the optional
# `email-validator` package, which isn't a project dependency. This regex is
# intentionally permissive (it rejects obvious non-emails like "not-an-email"
# without trying to fully implement RFC 5322) - good enough to catch user
# typos without becoming its own source of false rejections.
_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# Only enforced at company *registration* (POST /companies/register), which
# is the one place a company_code is ever chosen rather than typed in to
# look an existing company up - login/resolve-company deliberately keep
# accepting anything non-blank (see LoginRequest/CompanyCodeRequest below),
# so this stays out of their validation to avoid retroactively rejecting a
# code that was valid when its company registered.
_COMPANY_CODE_PATTERN = re.compile(r"^[A-Za-z0-9_-]{3,20}$")


def validate_email_format(value: str) -> str:
    """Shared email-shape check for every schema with an ``email`` field."""
    if not _EMAIL_PATTERN.match(value):
        raise ValueError("must be a valid email address")
    return value


def validate_company_code_format(value: str) -> str:
    """Shape check for a newly chosen company_code: 3-20 characters, letters/
    digits/hyphens/underscores only - no spaces or symbols that would make a
    code awkward to read aloud or type in on a login screen."""
    stripped = value.strip()
    if not _COMPANY_CODE_PATTERN.match(stripped):
        raise ValueError(
            "must be 3-20 characters: letters, numbers, hyphens, or underscores only"
        )
    return stripped
