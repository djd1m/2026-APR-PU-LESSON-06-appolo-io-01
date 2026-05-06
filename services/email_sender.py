"""Email sending service via Resend API. (Pattern: Instantly AI — services/resend_sender.py)"""

import logging
from datetime import datetime

import resend

from config import settings

logger = logging.getLogger(__name__)


class EmailSendResult:
    def __init__(self, success: bool, resend_id: str | None = None, error: str | None = None):
        self.success = success
        self.resend_id = resend_id
        self.error = error


class EmailSenderService:
    """Send emails via Resend API."""

    def __init__(self) -> None:
        if settings.RESEND_API_KEY:
            resend.api_key = settings.RESEND_API_KEY

    def is_configured(self) -> bool:
        return bool(settings.RESEND_API_KEY)

    def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        from_email: str | None = None,
    ) -> EmailSendResult:
        """Send a single email via Resend."""
        if not self.is_configured():
            logger.warning("Resend API key not configured — email not sent")
            return EmailSendResult(success=False, error="Resend API key not configured")

        from_addr = from_email or settings.RESEND_FROM_EMAIL

        try:
            result = resend.Emails.send({
                "from": from_addr,
                "to": [to],
                "subject": subject,
                "html": f"<html><body>{body}</body></html>",
                "text": body,
            })
            resend_id = result.get("id") if isinstance(result, dict) else getattr(result, "id", None)
            logger.info("Email sent via Resend to=%s resend_id=%s", to, resend_id)
            return EmailSendResult(success=True, resend_id=str(resend_id))
        except Exception as exc:
            logger.error("Resend send failed: to=%s error=%s", to, exc)
            return EmailSendResult(success=False, error=str(exc))

    def test_api_key(self) -> dict:
        """Test if the Resend API key is valid."""
        if not self.is_configured():
            return {"success": False, "message": "RESEND_API_KEY not set"}
        try:
            resend.api_key = settings.RESEND_API_KEY
            resend.Domains.list()
            return {"success": True, "message": "Resend API key is valid"}
        except Exception as exc:
            return {"success": False, "message": str(exc)}


email_sender = EmailSenderService()
