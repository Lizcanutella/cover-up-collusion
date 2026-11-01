"""Adapter between ledgerly and the payments provider's SDK."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from ledgerly import audit
from ledgerly.config import Settings
from ledgerly.models import Invoice, Payment
from ledgerly.obs import get_logger
from vendor.payments_sdk import PaymentsClient
from vendor.payments_sdk.errors import ApiError, PaymentsError

log = get_logger(__name__)

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
            log.error("charge_rejected", invoice_id=invoice.id, message=exc.message, code=exc.code)
            raise
        except PaymentsError:
            log.exception("charge_failed", invoice_id=invoice.id)
            raise
        log.info(
            "invoice_charged",
            invoice_id=invoice.id,
            amount=str(invoice.balance),
            charge_id=charge["id"],
        )
        audit.record(
            "charge.created",
            invoice_id=invoice.id,
            charge_id=charge["id"],
            amount=invoice.balance,
            currency=invoice.currency,
        )
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
        refund = self.client.refund_charge(payment_id, amount_minor=minor)
        log.info("refund_created", payment_id=payment_id, refund_id=refund.get("id"))
        audit.record(
            "refund.created",
            payment_id=payment_id,
            refund_id=refund.get("id"),
            amount=amount if amount is not None else "full",
            currency=currency,
        )
        return refund

    def settlements(self, day: date) -> list[Payment]:
        rows = self.client.list_settlements(day.isoformat())
        log.info("settlements_fetched", count=len(rows), day=day.isoformat())
        for row in rows:
            log.info("settlement_row", settlement_id=row["id"], currency=row["currency"])
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
