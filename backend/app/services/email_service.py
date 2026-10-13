import smtplib
from email.message import EmailMessage

from app.core.config import settings

_WELCOME_EMAIL_SUBJECT = "Welcome to ITOnIT - Your Company Code"


def _build_welcome_email_body(company_name: str, company_code: str) -> str:
    return (
        "Welcome to ITOnIT!\n\n"
        "Your company account has been created successfully.\n\n"
        f"Company: {company_name}\n"
        f"Company Code: {company_code}\n\n"
        "Your company code is required when signing in to ITOnIT.\n"
        "Please save this code and share it only with authorized employees "
        "who need access to your company workspace.\n\n"
        "Thank you,\n"
        "ITOnIT"
    )


class EmailNotConfiguredError(Exception):
    """Raised by send_company_registered_email when SMTP_HOST/SMTP_USERNAME/
    SMTP_PASSWORD/SMTP_FROM_EMAIL aren't all set - a normal, expected state
    (e.g. a contributor's fresh local .env with no SMTP section yet), not a
    delivery failure. CompanyService checks is_configured before calling
    send_company_registered_email at all (see its own docstring), so this
    is only ever raised if a caller skips that check."""


class SmtpEmailService:
    """Sends transactional email via Gmail-compatible SMTP (STARTTLS, port
    587), using only the standard library (smtplib + email.message) - no
    external email dependency, per this project's $0-cost constraint.

    Deliberately narrow: one method, for the one transactional email this
    project sends. Deliberately does NOT swallow exceptions -
    send_company_registered_email builds the message and sends it, raising
    normally (EmailNotConfiguredError, or whatever smtplib/socket raises on
    a real delivery failure) if anything goes wrong. Isolating a delivery
    failure from an otherwise-successful, already-committed registration is
    the caller's job (CompanyService.register_company), not this class's -
    see that method's own docstring. Keeping transport behavior (this
    class) separate from failure policy (the caller) means this class's
    behavior is simple to reason about and test on its own.
    """

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        username: str | None = None,
        password: str | None = None,
        from_email: str | None = None,
        from_name: str | None = None,
    ) -> None:
        self._host = host if host is not None else settings.SMTP_HOST
        self._port = port if port is not None else settings.SMTP_PORT
        self._username = username if username is not None else settings.SMTP_USERNAME
        self._password = password if password is not None else settings.SMTP_PASSWORD
        self._from_email = from_email if from_email is not None else settings.SMTP_FROM_EMAIL
        self._from_name = from_name if from_name is not None else settings.SMTP_FROM_NAME

    @property
    def is_configured(self) -> bool:
        """True once every setting an actual send needs is present. Checked
        by CompanyService before it ever calls send_company_registered_email
        - see this class's own docstring on why "not configured" is treated
        as a distinct, expected state rather than a delivery failure."""
        return bool(self._host and self._username and self._password and self._from_email)

    def send_company_registered_email(
        self, to_email: str, company_name: str, company_code: str
    ) -> None:
        """Sends the "Welcome to ITOnIT" email containing the newly
        registered company's generated company_code to its first Company
        Administrator. Raises EmailNotConfiguredError if SMTP isn't
        configured, or propagates whatever smtplib/the socket layer raises
        on an actual send failure - never swallowed here (see the class
        docstring)."""
        if not self.is_configured:
            raise EmailNotConfiguredError(
                "SMTP is not configured (SMTP_HOST/SMTP_USERNAME/SMTP_PASSWORD/SMTP_FROM_EMAIL)"
            )

        message = EmailMessage()
        message["Subject"] = _WELCOME_EMAIL_SUBJECT
        from_header = f"{self._from_name} <{self._from_email}>" if self._from_name else self._from_email
        message["From"] = from_header
        message["To"] = to_email
        message.set_content(_build_welcome_email_body(company_name, company_code))

        with smtplib.SMTP(self._host, self._port, timeout=10) as smtp:
            smtp.starttls()
            smtp.login(self._username, self._password)
            smtp.send_message(message)
