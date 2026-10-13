import smtplib
from datetime import datetime, timezone
from email.message import EmailMessage

from app.core.config import settings

_WELCOME_EMAIL_SUBJECT = "Welcome to ITOnIT - Your Company Code"
_SUPPORT_EMAIL_SUBJECT_PREFIX = "[ITOnIT Support] "


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


def _build_support_contact_email_body(sender_name: str, sender_email: str, message: str) -> str:
    sent_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return (
        "New message from the ITOnIT public contact form.\n\n"
        f"Name: {sender_name}\n"
        f"Email: {sender_email}\n"
        f"Sent: {sent_at}\n\n"
        "Message:\n"
        f"{message}"
    )


def _sanitize_header_value(value: str) -> str:
    """Strips CR/LF from a value before it's ever placed in an email
    header - defense in depth against header injection, on top of (not
    instead of) the request schema's own validation (SupportContactRequest
    rejects a name/subject containing a line break at the API boundary
    already - see app/schemas/support.py). A header value genuinely never
    needs an embedded newline, so collapsing one to a space can't lose any
    legitimate content."""
    return value.replace("\r", " ").replace("\n", " ").strip()


class EmailNotConfiguredError(Exception):
    """Raised when SMTP_HOST/SMTP_USERNAME/SMTP_PASSWORD/SMTP_FROM_EMAIL
    aren't all set - a normal, expected state (e.g. a contributor's fresh
    local .env with no SMTP section yet), not a delivery failure. Callers
    check is_configured before calling either send method at all (see each
    one's own docstring), so this is only ever raised if a caller skips
    that check."""


class SmtpEmailService:
    """Sends transactional email via Gmail-compatible SMTP (STARTTLS, port
    587), using only the standard library (smtplib + email.message) - no
    external email dependency, per this project's $0-cost constraint.

    Two narrow methods, one per transactional email this project sends -
    company-registration's welcome email, and the public Help Center
    contact form - both routed through the same SMTP account/connection
    logic (_send), never a second, separate SMTP implementation. Neither
    method swallows exceptions: each builds its message and sends it,
    raising normally (EmailNotConfiguredError, or whatever smtplib/the
    socket layer raises on a real delivery failure) if anything goes
    wrong. Isolating a delivery failure from the caller's own success/
    failure policy is each caller's job (CompanyService.register_company
    treats it as best-effort; SupportService.send_contact_message does
    not - see each one's own docstring), not this class's. Keeping
    transport behavior (this class) separate from failure policy (the
    callers) means this class's behavior is simple to reason about and
    test on its own.
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
        by every caller before it ever calls send_company_registered_email/
        send_support_contact_email - see this class's own docstring on why
        "not configured" is treated as a distinct, expected state rather
        than a delivery failure."""
        return bool(self._host and self._username and self._password and self._from_email)

    def _from_header(self) -> str:
        return f"{self._from_name} <{self._from_email}>" if self._from_name else self._from_email

    def _send(self, message: EmailMessage) -> None:
        """The one place either public method actually opens an SMTP
        connection - everything above this is message-building, specific
        to which email is being sent."""
        with smtplib.SMTP(self._host, self._port, timeout=10) as smtp:
            smtp.starttls()
            smtp.login(self._username, self._password)
            smtp.send_message(message)

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
        message["From"] = self._from_header()
        message["To"] = to_email
        message.set_content(_build_welcome_email_body(company_name, company_code))

        self._send(message)

    def send_support_contact_email(
        self,
        to_email: str,
        sender_name: str,
        sender_email: str,
        subject: str,
        message_body: str,
    ) -> None:
        """Sends a public Help Center contact-form submission to
        `to_email` (SUPPORT_EMAIL). Reply-To is set to the submitter's own,
        already-validated email address (SupportContactRequest's email
        field - see app/schemas/support.py) so replying in Gmail reaches
        them directly, without ever putting unvalidated input in the From
        header. Raises EmailNotConfiguredError if SMTP isn't configured, or
        propagates whatever smtplib/the socket layer raises on an actual
        send failure - never swallowed here (see the class docstring);
        SupportService is the caller that decides what to do about it.
        """
        if not self.is_configured:
            raise EmailNotConfiguredError(
                "SMTP is not configured (SMTP_HOST/SMTP_USERNAME/SMTP_PASSWORD/SMTP_FROM_EMAIL)"
            )

        message = EmailMessage()
        message["Subject"] = _SUPPORT_EMAIL_SUBJECT_PREFIX + _sanitize_header_value(subject)
        message["From"] = self._from_header()
        message["To"] = to_email
        message["Reply-To"] = _sanitize_header_value(sender_email)
        message.set_content(
            _build_support_contact_email_body(
                _sanitize_header_value(sender_name), sender_email, message_body
            )
        )

        self._send(message)
