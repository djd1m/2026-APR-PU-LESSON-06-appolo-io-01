"""YooKassa payment integration (stub). (Source: Substack — services/payments.py)

PAYMENTS_STUB=true → simulated payments. Safe for dev/testing.
Replace with real YooKassa API calls in production.
"""

import logging
import uuid
from dataclasses import dataclass

from config import settings

logger = logging.getLogger(__name__)

PLANS = {
    "starter": {"price": 4990, "credits": 500, "name": "Starter"},
    "professional": {"price": 14990, "credits": 3000, "name": "Professional"},
    "agency": {"price": 39990, "credits": 10000, "name": "Agency"},
}


@dataclass
class PaymentResult:
    payment_id: str
    payment_url: str
    status: str
    is_stub: bool = False


class PaymentService:
    @property
    def is_stub(self) -> bool:
        return settings.PAYMENTS_STUB

    def create_payment(
        self,
        amount: float,
        currency: str = "RUB",
        description: str = "Subscription payment",
        payment_id: str | None = None,
    ) -> PaymentResult:
        pid = payment_id or str(uuid.uuid4())
        if self.is_stub:
            logger.info("STUB: Created payment %s for %.0f %s: %s", pid, amount, currency, description)
            return PaymentResult(
                payment_id=pid,
                payment_url=f"https://yookassa.ru/checkout/stub/{pid}",
                status="pending",
                is_stub=True,
            )
        raise NotImplementedError("Real YooKassa not implemented. Set PAYMENTS_STUB=true.")

    def confirm_payment(self, payment_id: str) -> PaymentResult:
        if self.is_stub:
            logger.info("STUB: Confirmed payment %s", payment_id)
            return PaymentResult(
                payment_id=payment_id,
                payment_url=f"https://yookassa.ru/checkout/stub/{payment_id}",
                status="completed",
                is_stub=True,
            )
        raise NotImplementedError("Real YooKassa not implemented. Set PAYMENTS_STUB=true.")


payment_service = PaymentService()
