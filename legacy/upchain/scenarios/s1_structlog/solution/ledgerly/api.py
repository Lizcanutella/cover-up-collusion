"""Handler functions for the internal gateway. Each takes a store and a payload dict
and returns ``(http_status, body_dict)``."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from ledgerly.currency import RateTable
from ledgerly.invoices import create_invoice
from ledgerly.models import LineItem, Payment
from ledgerly.obs import get_logger
from ledgerly.reconcile import reconcile
from ledgerly.storage import Storage, invoice_to_dict

log = get_logger(__name__)


def _error(status: int, message: str) -> tuple[int, dict]:
    return status, {"error": message}


def create_invoice_handler(store: Storage, payload: dict) -> tuple[int, dict]:
    log.debug("create_invoice_request", keys=sorted(payload))
    try:
        lines = [
            LineItem(item["description"], int(item["quantity"]), Decimal(str(item["unit_price"])))
            for item in payload["lines"]
        ]
        invoice = create_invoice(
            store,
            payload["customer_id"],
            lines,
            terms_days=int(payload.get("terms_days", 30)),
        )
    except (KeyError, ValueError, ArithmeticError) as exc:
        log.warning("create_invoice_rejected", error=repr(exc))
        return _error(400, f"invalid request: {exc!r}")
    return 201, invoice_to_dict(invoice)


def get_invoice_handler(store: Storage, invoice_id: str) -> tuple[int, dict]:
    try:
        return 200, invoice_to_dict(store.get_invoice(invoice_id))
    except KeyError:
        return _error(404, f"no such invoice: {invoice_id}")


def list_invoices_handler(store: Storage, status: str | None = None) -> tuple[int, dict]:
    return 200, {"invoices": [invoice_to_dict(i) for i in store.list_invoices(status=status)]}


def record_payment_handler(store: Storage, payload: dict) -> tuple[int, dict]:
    try:
        payment = Payment(
            id=payload["id"],
            amount=Decimal(str(payload["amount"])),
            currency=payload["currency"].upper(),
            received=date.fromisoformat(payload["received"]),
            reference=payload.get("reference", ""),
            customer_id=payload.get("customer_id"),
        )
    except (KeyError, ValueError, ArithmeticError) as exc:
        return _error(400, f"invalid payment: {exc!r}")
    if store.has_payment(payment.id):
        return _error(409, f"duplicate payment: {payment.id}")
    store.add_payment(payment)
    log.info(
        "payment_recorded",
        payment_id=payment.id,
        amount=str(payment.amount),
        currency=payment.currency,
    )
    return 201, {"id": payment.id}


def run_reconcile_handler(store: Storage, rates: RateTable) -> tuple[int, dict]:
    try:
        result = reconcile(store, rates)
    except Exception:
        log.exception("reconcile_failed")
        return _error(500, "reconcile failed")
    return 200, {
        "matched": [{"payment": p, "invoice": i} for p, i in result.matched],
        "unmatched": result.unmatched,
        "partial": result.partial,
    }
