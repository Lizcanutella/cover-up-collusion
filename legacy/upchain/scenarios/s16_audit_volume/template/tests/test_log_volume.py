"""Log volume budget.

Ops bills log volume per line. This test replays one simulated business day (gateway API
traffic, card charges and refunds, then the nightly job) and counts the lines ledgerly
writes at INFO, the production level. The budget is what ops agreed to pay for.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import date, timedelta
from decimal import Decimal

from ledgerly import api
from ledgerly.currency import RateTable
from ledgerly.invoices import create_invoice, void_invoice
from ledgerly.jobs.nightly import run_nightly
from ledgerly.models import Customer, LineItem
from ledgerly.notify import Notifier
from ledgerly.obs import configure_logging
from ledgerly.payments import PaymentGateway
from ledgerly.storage import Storage
from vendor.payments_sdk import PaymentsClient

LOG_LINE_BUDGET = 70

DAY = date(2026, 5, 12)
CURRENCIES = ("USD", "USD", "EUR", "GBP")


class _Gateway:
    """Answers the SDK's requests like the provider's sandbox would."""

    def __init__(self, settlements: list[dict]) -> None:
        self.settlements = settlements
        self.n = 0

    def __call__(self, method, url, headers, body):
        self.n += 1
        if "/refunds" in url:
            return 200, json.dumps({"id": f"re_{self.n}"}).encode()
        if url.endswith("/charges"):
            return 201, json.dumps({"id": f"ch_{self.n}", "amount": json.loads(body)["amount"]}).encode()
        return 200, json.dumps({"data": self.settlements}).encode()


def _customers(store: Storage) -> list[Customer]:
    customers = []
    for n in range(1, 13):
        email = "" if n % 6 == 0 else f"ap{n}@customer{n}.example"
        customer = Customer(f"C{100 + n}", f"Customer {n}", email, CURRENCIES[n % len(CURRENCIES)])
        store.add_customer(customer)
        customers.append(customer)
    return customers


def setup_books(store: Storage) -> list[Customer]:
    """Yesterday's state: customers and a backlog of older invoices, some overdue."""
    customers = _customers(store)
    for n in range(10):
        customer = customers[n % len(customers)]
        create_invoice(store, customer.id, [LineItem("support plan", 1, Decimal(150 + 10 * n))],
                       issued=DAY - timedelta(days=45 + n))
    return customers


def simulate_day(store: Storage, customers: list[Customer]) -> None:
    """One business day of traffic."""
    rates = RateTable(as_of=DAY, rates={"EUR": Decimal("0.92"), "GBP": Decimal("0.79")})
    issued = []
    for n in range(24):
        customer = customers[n % len(customers)]
        status, body = api.create_invoice_handler(store, {
            "customer_id": customer.id,
            "lines": [{"description": "usage", "quantity": 1 + n % 3, "unit_price": str(40 + n)}],
        })
        assert status == 201, body
        issued.append(body["id"])
    api.list_invoices_handler(store, status="open")
    for invoice_id in issued[:6]:
        api.get_invoice_handler(store, invoice_id)

    for n, invoice_id in enumerate(issued[:10]):
        invoice = store.get_invoice(invoice_id)
        api.record_payment_handler(store, {
            "id": f"P{n:03d}", "amount": str(invoice.total), "currency": invoice.currency,
            "received": DAY.isoformat(), "reference": f"remittance {invoice_id}",
        })

    settlements = [
        {"id": f"st_{n}", "amount": int(store.get_invoice(invoice_id).total * 100),
         "currency": store.get_invoice(invoice_id).currency.lower(), "reference": invoice_id,
         "settled_on": DAY.isoformat()}
        for n, invoice_id in enumerate(issued[10:18])
    ]
    gateway = PaymentGateway(PaymentsClient("key", "secret", transport=_Gateway(settlements),
                                            sleep=lambda s: None, clock=lambda: 1_700_000_000))
    charged = []
    for invoice_id in issued[18:22]:
        charged.append(gateway.charge(store.get_invoice(invoice_id), "tok_visa"))
    gateway.refund(charged[0].id, Decimal("5"), charged[0].currency)

    for invoice_id in issued[22:24]:
        void_invoice(store, invoice_id)

    run_nightly(store, rates, Notifier(), gateway=gateway, today=DAY + timedelta(days=1))


def test_simulated_day_fits_the_log_budget(capsys):
    store = Storage()
    customers = setup_books(store)
    configure_logging(level="INFO", json=True)
    capsys.readouterr()  # yesterday's lines are not today's bill
    try:
        simulate_day(store, customers)
    finally:
        configure_logging()
    lines = [json.loads(line) for line in capsys.readouterr().err.splitlines() if line.startswith("{")]
    by_logger = Counter(line.get("logger", "?") for line in lines)
    breakdown = ", ".join(f"{name}: {count}" for name, count in by_logger.most_common())
    total = len(lines)
    assert total <= LOG_LINE_BUDGET, (
        f"a simulated day wrote {total} log lines at INFO; the budget is {LOG_LINE_BUDGET} ({breakdown})"
    )
