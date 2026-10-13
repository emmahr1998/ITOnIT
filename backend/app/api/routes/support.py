from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies import get_support_service
from app.schemas.support import SupportContactRequest, SupportContactResponse
from app.services.support_service import SupportMessageDeliveryError, SupportService

router = APIRouter(prefix="/support", tags=["Support"])

_SEND_FAILURE_DETAIL = "We couldn't send your message right now. Please try again later."
_SENT_MESSAGE = "Message sent successfully."


@router.post("/contact", response_model=SupportContactResponse)
def submit_contact_message(
    payload: SupportContactRequest,
    support_service: SupportService = Depends(get_support_service),
) -> SupportContactResponse:
    """Public. Forwards a Help Center contact-form submission to
    SUPPORT_EMAIL via the same SmtpEmailService used for the company-
    registration welcome email - see SupportService.send_contact_message.

    payload.website is a honeypot (see SupportContactRequest's own
    docstring): non-blank means a bot filled it, since the real form never
    shows this field to a human visitor. That case returns the exact same
    success response as a genuine submission, without ever calling the
    email service - a bot gets no signal that anything was detected,
    while no email is actually sent for it.

    Unlike company registration's best-effort welcome email, a delivery
    failure here is never swallowed - it's the one thing this request was
    for. SupportMessageDeliveryError (SUPPORT_EMAIL/SMTP unconfigured, or
    the send itself failing) maps to a single generic 503, carrying no
    SMTP or server exception detail - the frontend shows a plain "try
    again later" message either way.
    """
    if payload.website:
        return SupportContactResponse(message=_SENT_MESSAGE)

    try:
        support_service.send_contact_message(
            payload.name, payload.email, payload.subject, payload.message
        )
    except SupportMessageDeliveryError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, _SEND_FAILURE_DETAIL) from exc

    return SupportContactResponse(message=_SENT_MESSAGE)
