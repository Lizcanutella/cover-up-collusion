"""Adapter between ledgerly and the payments provider's SDK."""

from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal

from ledgerly.config import Settings
from ledgerly.models import Invoice, Payment
from vendor.payments_sdk import PaymentsClient
from vendor.payments_sdk.errors import ApiError, PaymentsError

logger = logging.getLogger(__name__)

# number of decimal places the gateway uses per currency (default is 2)
_EXPONENT = {"JPY": 0, "KRW": 0}


def to_minor_units(amount: Decimal, currency: str) -> int:
    exponent = _EXPONENT.get(currency.upper(), 2)
    return int((amount * (10**exponent)).to_integral_value())


def from_minor_units(minor: int, currency: str) -> Decimal:
    exponent = _EXPONENT.get(currency.upper(), 2)
    return Decimal(minor) / (10**exponent)


class PaymentGateway:
    def __init__(self, client: PaymentsClient) -> None:
        self.client = client

    @classmethod
    def from_settings(cls, settings: Settings, **client_kwargs) -> "PaymentGateway":
        return cls(PaymentsClient(settings.payments_key, settings.payments_secret, **client_kwargs))

    def charge(self, invoice: Invoice, source_token: str) -> Payment:
        minor = to_minor_units(invoice.balance, invoice.currency)
        try:
            charge = self.client.create_charge(
                amount_minor=minor,
                currency=invoice.currency,
                source=source_token,
                idempotency_key=f"{invoice.id}-{minor}",
                metadata={"invoice_id": invoice.id},
            )
        except ApiError as exc:
            logger.error("charge for %s rejected: %s (%s)", invoice.id, exc.message, exc.code)
            raise
        except PaymentsError:
            logger.exception("charge for %s failed", invoice.id)
            raise
        logger.info("charged %s for invoice %s (charge %s)", invoice.balance, invoice.id, charge["id"])
        return Payment(
            id=charge["id"],
            amount=from_minor_units(charge["amount"], invoice.currency),
            currency=invoice.currency,
            received=date.today(),
            reference=invoice.id,
            customer_id=invoice.customer_id,
            invoice_id=invoice.id,
        )

    def refund(self, payment_id: str, amount: Decimal | None = None, currency: str = "USD") -> dict:
        minor = None if amount is None else to_minor_units(amount, currency)
        return self.client.refund_charge(payment_id, amount_minor=minor)

    def settlements(self, day: date) -> list[Payment]:
        rows = self.client.list_settlements(day.isoformat())
        print(f"[payments] fetched {len(rows)} settlements for {day}")
        return [
            Payment(
                id=row["id"],
                amount=from_minor_units(row["amount"], row["currency"].upper()),
                currency=row["currency"].upper(),
                received=date.fromisoformat(row["settled_on"]),
                reference=row.get("reference", ""),
                customer_id=row.get("customer_ref"),
            )
            for row in rows
        ]
