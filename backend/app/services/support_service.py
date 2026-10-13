import logging

from app.core.config import settings
from app.services.email_service import SmtpEmailService

logger = logging.getLogger(__name__)


class SupportMessageDeliveryError(Exception):
    """Raised when a Help Center contact-form submission could not be
    delivered - either SUPPORT_EMAIL/SMTP isn't configured, or the send
    itself failed. The route maps this to a single safe error response,
    never exposing SMTP/server detail to the (unauthenticated) caller -
    see POST /support/contact's own docstring.

    Unlike CompanyService.register_company's welcome email (best-effort:
    a delivery failure is logged and swallowed, because the registration
    it's attached to already fully succeeded), a contact-form submission
    *is* the whole point of this request - if it can't be delivered, the
    caller must be told it failed, not shown a false "sent successfully."
    This class exists specifically so the route can distinguish that case
    from any other unexpected error cleanly.
    """


class SupportService:
    """Owns the one thing the public Help Center contact form does: send
    its submission to SUPPORT_EMAIL. Reuses SmtpEmailService - the same
    SMTP account/connection logic as company-registration's welcome email
    - never a second, separate email implementation.
    """

    def __init__(
        self,
        email_service: SmtpEmailService | None = None,
        support_email: str | None = None,
    ) -> None:
        self._email_service = email_service if email_service is not None else SmtpEmailService()
        self._support_email = support_email if support_email is not None else settings.SUPPORT_EMAIL

    def send_contact_message(self, name: str, email: str, subject: str, message: str) -> None:
        """Raises SupportMessageDeliveryError if SUPPORT_EMAIL isn't set,
        SMTP isn't configured, or the send itself fails - in every case,
        the route maps this to one generic, safe error response."""
        if not self._support_email or not self._email_service.is_configured:
            logger.warning(
                "Support contact form submitted but SUPPORT_EMAIL/SMTP is not configured"
            )
            raise SupportMessageDeliveryError("Support email is not configured")

        try:
            self._email_service.send_support_contact_email(
                to_email=self._support_email,
                sender_name=name,
                sender_email=email,
                subject=subject,
                message_body=message,
            )
        except Exception as exc:
            logger.warning("Failed to deliver support contact message", exc_info=True)
            raise SupportMessageDeliveryError("Could not send support message") from exc
