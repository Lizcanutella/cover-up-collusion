"""In-memory storage with optional JSON-file persistence."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import date
from decimal import Decimal
from pathlib import Path

from ledgerly.models import Customer, Invoice, LineItem, Payment
from ledgerly.obs import get_logger

log = get_logger(__name__)


def invoice_to_dict(inv: Invoice) -> dict:
    return {
        "id": inv.id,
        "customer_id": inv.customer_id,
        "issued": inv.issued.isoformat(),
        "due": inv.due.isoformat(),
        "currency": inv.currency,
        "status": inv.status,
        "paid": str(inv.paid),
        "lines": [
            {"description": l.description, "quantity": l.quantity, "unit_price": str(l.unit_price)}
            for l in inv.lines
        ],
    }


def invoice_from_dict(d: dict) -> Invoice:
    return Invoice(
        id=d["id"],
        customer_id=d["customer_id"],
        issued=date.fromisoformat(d["issued"]),
        due=date.fromisoformat(d["due"]),
        currency=d["currency"],
        status=d["status"],
        paid=Decimal(d["paid"]),
        lines=[
            LineItem(l["description"], int(l["quantity"]), Decimal(l["unit_price"]))
            for l in d["lines"]
        ],
    )


def payment_to_dict(p: Payment) -> dict:
    d = asdict(p)
    d["amount"] = str(p.amount)
    d["received"] = p.received.isoformat()
    return d


def payment_from_dict(d: dict) -> Payment:
    return Payment(
        id=d["id"],
        amount=Decimal(d["amount"]),
        currency=d["currency"],
        received=date.fromisoformat(d["received"]),
        reference=d.get("reference", ""),
        customer_id=d.get("customer_id"),
        invoice_id=d.get("invoice_id"),
        matched=d.get("matched", False),
    )


class Storage:
    def __init__(self, path: Path | str | None = None) -> None:
        self.path = Path(path) if path else None
        self._customers: dict[str, Customer] = {}
        self._invoices: dict[str, Invoice] = {}
        self._payments: dict[str, Payment] = {}
        if self.path is not None and self.path.exists():
            self.load()

    # customers
    def add_customer(self, customer: Customer) -> None:
        self._customers[customer.id] = customer

    def get_customer(self, customer_id: str) -> Customer:
        return self._customers[customer_id]

    # invoices
    def add_invoice(self, invoice: Invoice) -> None:
        self._invoices[invoice.id] = invoice
        log.info("invoice_stored", invoice_id=invoice.id, customer_id=invoice.customer_id)

    def get_invoice(self, invoice_id: str) -> Invoice:
        return self._invoices[invoice_id]

    def update_invoice(self, invoice: Invoice) -> None:
        if invoice.id not in self._invoices:
            raise KeyError(invoice.id)
        self._invoices[invoice.id] = invoice
        log.info("invoice_updated", invoice_id=invoice.id, status=invoice.status)

    def list_invoices(
        self, status: str | None = None, customer_id: str | None = None
    ) -> list[Invoice]:
        out = list(self._invoices.values())
        if status is not None:
            out = [i for i in out if i.status == status]
        if customer_id is not None:
            out = [i for i in out if i.customer_id == customer_id]
        return sorted(out, key=lambda i: i.id)

    # payments
    def add_payment(self, payment: Payment) -> None:
        self._payments[payment.id] = payment
        log.info("payment_stored", payment_id=payment.id)

    def has_payment(self, payment_id: str) -> bool:
        return payment_id in self._payments

    def update_payment(self, payment: Payment) -> None:
        self._payments[payment.id] = payment
        log.info("payment_updated", payment_id=payment.id, matched=payment.matched)

    def list_payments(self, unmatched: bool = False) -> list[Payment]:
        out = list(self._payments.values())
        if unmatched:
            out = [p for p in out if not p.matched]
        return sorted(out, key=lambda p: (p.received, p.id))

    # persistence
    def save(self) -> None:
        if self.path is None:
            return
        payload = {
            "customers": [asdict(c) for c in self._customers.values()],
            "invoices": [invoice_to_dict(i) for i in self._invoices.values()],
            "payments": [payment_to_dict(p) for p in self._payments.values()],
        }
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2))
        tmp.replace(self.path)
        log.info(
            "storage_saved",
            path=str(self.path),
            invoices=len(self._invoices),
            payments=len(self._payments),
        )

    def load(self) -> None:
        if self.path is None or not self.path.exists():
            log.debug("storage_load_skipped", path=str(self.path))
            return
        raw = json.loads(self.path.read_text())
        self._customers = {c["id"]: Customer(**c) for c in raw.get("customers", [])}
        self._invoices = {d["id"]: invoice_from_dict(d) for d in raw.get("invoices", [])}
        self._payments = {d["id"]: payment_from_dict(d) for d in raw.get("payments", [])}
        log.info(
            "storage_loaded",
            path=str(self.path),
            customers=len(self._customers),
            invoices=len(self._invoices),
            payments=len(self._payments),
        )
