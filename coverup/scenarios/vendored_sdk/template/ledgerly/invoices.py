"""Invoice lifecycle: creation, payment application, voiding, overdue queries."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from ledgerly.models import Invoice, LineItem
from ledgerly.obs import get_logger
from ledgerly.storage import Storage

log = get_logger(__name__)


def next_invoice_id(store: Storage) -> str:
    return f"INV-{len(store.list_invoices()) + 1:04d}"


def create_invoice(
    store: Storage,
    customer_id: str,
    lines: list[LineItem],
    issued: date | None = None,
    terms_days: int = 30,
    currency: str | None = None,
) -> Invoice:
    customer = store.get_customer(customer_id)
    if not lines:
        raise ValueError("an invoice needs at least one line")
    issued = issued or date.today()
    inv = Invoice(
        id=next_invoice_id(store),
        customer_id=customer.id,
        issued=issued,
        due=issued + timedelta(days=terms_days),
        currency=currency or customer.currency,
        lines=list(lines),
    )
    store.add_invoice(inv)
    log.info(
        "invoice_created",
        invoice_id=inv.id,
        customer_id=customer.id,
        amount=str(inv.total),
        currency=inv.currency,
    )
    return inv


def apply_payment(store: Storage, invoice: Invoice, amount: Decimal) -> Invoice:
    if invoice.status == "void":
        raise ValueError(f"{invoice.id} is void")
    if amount <= 0:
        raise ValueError("payment amount must be positive")
    if amount > invoice.balance:
        log.warning(
            "overpayment_clipped",
            invoice_id=invoice.id,
            amount=str(amount),
            balance=str(invoice.balance),
        )
        amount = invoice.balance
    invoice.paid += amount
    invoice.status = "paid" if invoice.balance == 0 else "partial"
    store.update_invoice(invoice)
    log.info(
        "payment_applied",
        invoice_id=invoice.id,
        amount=str(amount),
        status=invoice.status,
        balance=str(invoice.balance),
    )
    return invoice


def void_invoice(store: Storage, invoice_id: str) -> Invoice:
    invoice = store.get_invoice(invoice_id)
    if invoice.paid > 0:
        raise ValueError(f"{invoice.id} already has payments applied")
    invoice.status = "void"
    store.update_invoice(invoice)
    log.info("invoice_voided", invoice_id=invoice.id)
    return invoice


def overdue(store: Storage, today: date) -> list[Invoice]:
    return [i for i in store.list_invoices() if i.status in ("open", "partial") and i.due < today]
