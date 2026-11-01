"""Match incoming payments to open invoices."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

from ledgerly.currency import RateTable, UnknownCurrency, check_staleness, convert
from ledgerly.invoices import apply_payment
from ledgerly.models import Invoice, Payment
from ledgerly.obs import get_logger
from ledgerly.storage import Storage

log = get_logger(__name__)

_REFERENCE = re.compile(r"INV-\d{4,}")


@dataclass
class ReconcileResult:
    matched: list[tuple[str, str]] = field(default_factory=list)  # (payment_id, invoice_id)
    unmatched: list[str] = field(default_factory=list)
    partial: list[str] = field(default_factory=list)  # invoice ids still carrying a balance


def find_invoice(store: Storage, payment: Payment) -> Invoice | None:
    """Locate the invoice a payment belongs to, or None if it cannot be determined."""
    if payment.invoice_id:
        try:
            return store.get_invoice(payment.invoice_id)
        except KeyError:
            log.warning(
                "payment_references_unknown_invoice",
                payment_id=payment.id,
                invoice_id=payment.invoice_id,
            )

    found = _REFERENCE.search(payment.reference or "")
    if found:
        try:
            return store.get_invoice(found.group())
        except KeyError:
            pass  # reference text that merely looks like one of ours

    if payment.customer_id:
        candidates = [
            inv
            for inv in store.list_invoices(customer_id=payment.customer_id)
            if inv.status in ("open", "partial")
            and inv.currency == payment.currency
            and inv.balance == payment.amount
        ]
        if len(candidates) == 1:
            return candidates[0]
        if len(candidates) > 1:
            log.warning("payment_ambiguous", payment_id=payment.id, candidates=len(candidates))
    return None


def reconcile(store: Storage, rates: RateTable, today: date | None = None) -> ReconcileResult:
    today = today or date.today()
    check_staleness(rates, today)
    result = ReconcileResult()
    pending = store.list_payments(unmatched=True)
    log.info("reconcile_started", pending=len(pending))

    for payment in pending:
        log.debug(
            "reconcile_payment",
            payment_id=payment.id,
            amount=str(payment.amount),
            currency=payment.currency,
        )
        invoice = find_invoice(store, payment)
        if invoice is None or invoice.status in ("void", "paid"):
            result.unmatched.append(payment.id)
            continue
        try:
            amount = convert(payment.amount, payment.currency, invoice.currency, rates)
        except UnknownCurrency:
            log.error(
                "payment_conversion_failed",
                payment_id=payment.id,
                from_currency=payment.currency,
                to_currency=invoice.currency,
            )
            result.unmatched.append(payment.id)
            continue
        apply_payment(store, invoice, amount)
        payment.invoice_id = invoice.id
        payment.matched = True
        store.update_payment(payment)
        result.matched.append((payment.id, invoice.id))
        log.debug("payment_matched", payment_id=payment.id, invoice_id=invoice.id)
        if invoice.status == "partial":
            result.partial.append(invoice.id)

    log.info(
        "reconcile_finished",
        matched=len(result.matched),
        unmatched=len(result.unmatched),
        partial=len(result.partial),
    )
    return result
