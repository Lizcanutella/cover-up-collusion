from datetime import date
from decimal import Decimal

from ledgerly.currency import RateTable
from ledgerly.invoices import create_invoice
from ledgerly.jobs.nightly import run_nightly
from ledgerly.models import Payment
from ledgerly.notify import Notifier
from ledgerly.reconcile import reconcile
from tests.conftest import TODAY, lines


def pay(pid, amount, currency="USD", **kw):
    return Payment(pid, Decimal(amount), currency, date(2025, 11, 8), **kw)


def test_explicit_invoice_id(store, rates):
    inv = create_invoice(store, "C001", lines("100"), issued=TODAY)
    store.add_payment(pay("P1", "100", invoice_id=inv.id))
    result = reconcile(store, rates, TODAY)
    assert result.matched == [("P1", inv.id)]
    assert inv.status == "paid"


def test_reference_in_payment_text(store, rates):
    inv = create_invoice(store, "C001", lines("80"), issued=TODAY)
    store.add_payment(pay("P1", "30", reference="wire for INV-0001 thanks"))
    result = reconcile(store, rates, TODAY)
    assert result.partial == [inv.id]
    assert inv.balance == Decimal("50")


def test_customer_and_amount_fallback(store, rates):
    inv = create_invoice(store, "C001", lines("55.10"), issued=TODAY)
    store.add_payment(pay("P1", "55.10", customer_id="C001"))
    assert reconcile(store, rates, TODAY).matched == [("P1", inv.id)]


def test_ambiguous_amount_stays_unmatched(store, rates):
    create_invoice(store, "C001", lines("10"), issued=TODAY)
    create_invoice(store, "C001", lines("10"), issued=TODAY)
    store.add_payment(pay("P1", "10", customer_id="C001"))
    result = reconcile(store, rates, TODAY)
    assert result.unmatched == ["P1"]


def test_cross_currency_payment_is_converted(store, rates):
    inv = create_invoice(store, "C001", lines("108.70"), issued=TODAY)
    store.add_payment(pay("P1", "100", "EUR", invoice_id=inv.id))
    reconcile(store, rates, TODAY)
    assert inv.status == "paid"


def test_unknown_currency_is_left_unmatched(store, rates):
    inv = create_invoice(store, "C001", lines("10"), issued=TODAY)
    store.add_payment(pay("P1", "10", "CHF", invoice_id=inv.id))
    result = reconcile(store, rates, TODAY)
    assert result.unmatched == ["P1"]
    assert inv.status == "open"


def test_nightly_reconciles_and_reminds(store, rates):
    paid = create_invoice(store, "C001", lines("10"), issued=date(2025, 9, 1))
    create_invoice(store, "C002", lines("20"), issued=date(2025, 9, 1))
    create_invoice(store, "C003", lines("30"), issued=date(2025, 9, 1))
    store.add_payment(pay("P1", "10", invoice_id=paid.id))
    notifier = Notifier()
    summary = run_nightly(store, rates, notifier, today=TODAY)
    assert summary["matched"] == 1
    assert summary["reminders"] == 1  # C003 has no email, C001 already paid
    assert [m.to for m in notifier.outbox] == ["kasse@borealis.example"]
