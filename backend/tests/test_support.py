"""Tests for POST /support/contact - the public Help Center contact form.

Every HTTP-level test here goes through the shared `client` fixture, which
wires a FakeEmailService into SupportService (see conftest.py's
support_service fixture and TEST_SUPPORT_EMAIL) - no test in this file ever
opens a real SMTP connection. A couple of tests exercise
SmtpEmailService.send_support_contact_email directly, with smtplib.SMTP
itself mocked, to verify message construction (Reply-To, Subject prefix)
without any network access either.
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.services.email_service import SmtpEmailService
from app.services.support_service import SupportMessageDeliveryError, SupportService
from tests.conftest import TEST_SUPPORT_EMAIL, FakeEmailService


def _payload(**overrides: object) -> dict:
    payload = {
        "name": "Jordan Lee",
        "email": "jordan@example.com",
        "subject": "Can't find my company code",
        "message": "I registered last week but lost the email with my company code.",
    }
    payload.update(overrides)
    return payload


def _submit(client: TestClient, **overrides: object):
    return client.post("/support/contact", json=_payload(**overrides))


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_contact_form_sends_exactly_one_support_email(
    client: TestClient, email_service: FakeEmailService
) -> None:
    response = _submit(client)
    assert response.status_code == 200, response.text
    assert response.json()["message"] == "Message sent successfully."

    assert len(email_service.support_sent) == 1
    to_email, sender_name, sender_email, subject, message_body = email_service.support_sent[0]
    assert to_email == TEST_SUPPORT_EMAIL
    assert sender_name == "Jordan Lee"
    assert sender_email == "jordan@example.com"
    assert subject == "Can't find my company code"
    assert message_body == "I registered last week but lost the email with my company code."


def test_contact_form_represents_distinct_submission_correctly(
    client: TestClient, email_service: FakeEmailService
) -> None:
    response = _submit(
        client,
        name="Priya Shah",
        email="priya@othercompany.test",
        subject="How does inventory tracking work?",
        message="Specifically, can a technician reserve a laptop for a ticket?",
    )
    assert response.status_code == 200

    _, sender_name, sender_email, subject, message_body = email_service.support_sent[0]
    assert sender_name == "Priya Shah"
    assert sender_email == "priya@othercompany.test"
    assert subject == "How does inventory tracking work?"
    assert message_body == "Specifically, can a technician reserve a laptop for a ticket?"


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_contact_form_rejects_invalid_email(
    client: TestClient, email_service: FakeEmailService
) -> None:
    response = _submit(client, email="not-an-email")
    assert response.status_code == 422
    assert email_service.support_sent == []


def test_contact_form_rejects_blank_subject(
    client: TestClient, email_service: FakeEmailService
) -> None:
    response = _submit(client, subject="   ")
    assert response.status_code == 422
    assert email_service.support_sent == []


def test_contact_form_rejects_blank_message(
    client: TestClient, email_service: FakeEmailService
) -> None:
    response = _submit(client, message="   ")
    assert response.status_code == 422
    assert email_service.support_sent == []


def test_contact_form_rejects_blank_name(
    client: TestClient, email_service: FakeEmailService
) -> None:
    response = _submit(client, name="   ")
    assert response.status_code == 422
    assert email_service.support_sent == []


def test_contact_form_rejects_oversized_name(
    client: TestClient, email_service: FakeEmailService
) -> None:
    response = _submit(client, name="x" * 101)
    assert response.status_code == 422
    assert email_service.support_sent == []


def test_contact_form_rejects_oversized_subject(
    client: TestClient, email_service: FakeEmailService
) -> None:
    response = _submit(client, subject="x" * 151)
    assert response.status_code == 422
    assert email_service.support_sent == []


def test_contact_form_rejects_oversized_message(
    client: TestClient, email_service: FakeEmailService
) -> None:
    response = _submit(client, message="x" * 5001)
    assert response.status_code == 422
    assert email_service.support_sent == []


def test_contact_form_rejects_line_break_in_name(
    client: TestClient, email_service: FakeEmailService
) -> None:
    """name ends up in the email body, not a header, but a line break in it
    is still rejected - see SupportContactRequest's own docstring on why
    name/subject specifically reject one."""
    response = _submit(client, name="Jordan\nLee")
    assert response.status_code == 422
    assert email_service.support_sent == []


def test_contact_form_rejects_line_break_in_subject(
    client: TestClient, email_service: FakeEmailService
) -> None:
    """subject becomes part of the email Subject header - a line break
    here is the actual header-injection vector this guards against."""
    response = _submit(client, subject="Hello\nBcc: attacker@evil.test")
    assert response.status_code == 422
    assert email_service.support_sent == []


def test_contact_form_allows_line_breaks_in_message(
    client: TestClient, email_service: FakeEmailService
) -> None:
    """message is the email body, not a header - line breaks there are
    normal and must not be rejected."""
    response = _submit(client, message="Line one.\nLine two.\n\nLine four.")
    assert response.status_code == 200
    assert email_service.support_sent[0][4] == "Line one.\nLine two.\n\nLine four."


# ---------------------------------------------------------------------------
# Honeypot (spam/abuse)
# ---------------------------------------------------------------------------


def test_contact_form_honeypot_field_silently_skips_sending(
    client: TestClient, email_service: FakeEmailService
) -> None:
    """A non-blank `website` means a bot filled every field - the response
    still looks like success (no signal to the bot), but no email is
    actually sent."""
    response = client.post(
        "/support/contact", json={**_payload(), "website": "https://spam.example"}
    )
    assert response.status_code == 200
    assert response.json()["message"] == "Message sent successfully."
    assert email_service.support_sent == []


def test_contact_form_blank_honeypot_field_sends_normally(
    client: TestClient, email_service: FakeEmailService
) -> None:
    response = client.post("/support/contact", json={**_payload(), "website": ""})
    assert response.status_code == 200
    assert len(email_service.support_sent) == 1


# ---------------------------------------------------------------------------
# Delivery failure - never a false "sent successfully", never leaks detail
# ---------------------------------------------------------------------------


def test_contact_form_smtp_failure_returns_safe_error_response(
    client: TestClient, email_service: FakeEmailService
) -> None:
    email_service.fail_next_send = True

    response = _submit(client)
    assert response.status_code == 503
    body = response.json()
    assert body["detail"] == "We couldn't send your message right now. Please try again later."
    # No SMTP/server exception detail of any kind leaked to the caller.
    assert "simulated SMTP failure" not in response.text
    assert "Traceback" not in response.text
    assert "smtplib" not in response.text


def test_contact_form_not_configured_returns_safe_error_response(client: TestClient) -> None:
    """SUPPORT_EMAIL (or SMTP) unset must behave exactly like a delivery
    failure from the caller's point of view - a safe, generic error, never
    a crash and never a false success."""
    from app.dependencies import get_support_service
    from app.main import app

    unconfigured = SupportService(email_service=FakeEmailService(), support_email=None)
    original_override = app.dependency_overrides[get_support_service]
    app.dependency_overrides[get_support_service] = lambda: unconfigured
    try:
        response = _submit(client)
    finally:
        # Restore the client fixture's own override, so this test doesn't
        # leak its replacement into any test that runs after it.
        app.dependency_overrides[get_support_service] = original_override

    assert response.status_code == 503
    assert response.json()["detail"] == "We couldn't send your message right now. Please try again later."


# ---------------------------------------------------------------------------
# SupportService - service-level (no HTTP, no network)
# ---------------------------------------------------------------------------


def test_support_service_raises_typed_error_on_delivery_failure() -> None:
    fake = FakeEmailService()
    fake.fail_next_send = True
    service = SupportService(email_service=fake, support_email=TEST_SUPPORT_EMAIL)

    with pytest.raises(SupportMessageDeliveryError):
        service.send_contact_message("Jordan Lee", "jordan@example.com", "Subject", "Message")


def test_support_service_raises_typed_error_when_support_email_unset() -> None:
    fake = FakeEmailService()
    service = SupportService(email_service=fake, support_email=None)

    with pytest.raises(SupportMessageDeliveryError):
        service.send_contact_message("Jordan Lee", "jordan@example.com", "Subject", "Message")
    assert fake.support_sent == []


def test_support_service_raises_typed_error_when_smtp_not_configured() -> None:
    fake = FakeEmailService()
    fake.is_configured = False
    service = SupportService(email_service=fake, support_email=TEST_SUPPORT_EMAIL)

    with pytest.raises(SupportMessageDeliveryError):
        service.send_contact_message("Jordan Lee", "jordan@example.com", "Subject", "Message")
    assert fake.support_sent == []


# ---------------------------------------------------------------------------
# SmtpEmailService - message construction (smtplib.SMTP mocked, no network)
# ---------------------------------------------------------------------------


def test_smtp_email_service_sets_reply_to_the_submitters_email() -> None:
    service = SmtpEmailService(
        host="smtp.example.test",
        port=587,
        username="itonit@example.test",
        password="app-password",
        from_email="itonit@example.test",
        from_name="ITOnIT",
    )
    mock_smtp = MagicMock()
    mock_smtp.__enter__.return_value = mock_smtp
    with patch("app.services.email_service.smtplib.SMTP", return_value=mock_smtp) as mock_cls:
        service.send_support_contact_email(
            to_email="support-test@example.com",
            sender_name="Jordan Lee",
            sender_email="jordan@example.com",
            subject="Help needed",
            message_body="Body text",
        )

    mock_cls.assert_called_once_with("smtp.example.test", 587, timeout=10)
    mock_smtp.starttls.assert_called_once()
    mock_smtp.login.assert_called_once_with("itonit@example.test", "app-password")
    assert mock_smtp.send_message.call_count == 1
    sent_message = mock_smtp.send_message.call_args[0][0]
    assert sent_message["Reply-To"] == "jordan@example.com"
    assert sent_message["Subject"] == "[ITOnIT Support] Help needed"
    assert sent_message["To"] == "support-test@example.com"
    # Never put unvalidated sender input directly into From.
    assert "jordan@example.com" not in sent_message["From"]


def test_smtp_email_service_strips_header_injection_attempts() -> None:
    """Defense in depth (SupportContactRequest already rejects a
    name/subject containing a line break at the API boundary) - even if
    this method were ever called directly with one, it must not reach the
    outgoing headers unescaped."""
    service = SmtpEmailService(
        host="smtp.example.test",
        port=587,
        username="itonit@example.test",
        password="app-password",
        from_email="itonit@example.test",
        from_name="ITOnIT",
    )
    mock_smtp = MagicMock()
    mock_smtp.__enter__.return_value = mock_smtp
    with patch("app.services.email_service.smtplib.SMTP", return_value=mock_smtp):
        service.send_support_contact_email(
            to_email="support-test@example.com",
            sender_name="Evil\r\nBcc: attacker@evil.test",
            sender_email="jordan@example.com",
            subject="Hello\r\nBcc: attacker@evil.test",
            message_body="Body text",
        )

    sent_message = mock_smtp.send_message.call_args[0][0]
    assert "\r" not in str(sent_message["Subject"])
    assert "\n" not in str(sent_message["Subject"])
    # The real security property: no extra header was actually injected -
    # the attempted "Bcc:" line became harmless literal text inside the
    # Subject value, never a second header.
    header_names = [name for name, _ in sent_message.items()]
    assert header_names.count("Bcc") == 0
    assert header_names.count("Subject") == 1


def test_smtp_email_service_raises_when_not_configured() -> None:
    # Empty strings, not None - the constructor treats None as "fall back
    # to the real settings.SMTP_* values" (which may well be configured in
    # this environment's own .env), so this must pass explicit non-None,
    # falsy overrides to force a genuinely unconfigured instance.
    service = SmtpEmailService(host="", username="", password="", from_email="")
    assert service.is_configured is False
    with pytest.raises(Exception):
        service.send_support_contact_email(
            to_email="support-test@example.com",
            sender_name="Jordan Lee",
            sender_email="jordan@example.com",
            subject="Subject",
            message_body="Message",
        )
