from datetime import date
from decimal import Decimal

import pytest

from ledgerly.invoices import apply_payment, create_invoice, overdue, void_invoice
from tests.conftest import TODAY, lines


def test_create_invoice_totals_and_due_date(store):
    inv = create_invoice(store, "C001", lines("10.50", "4.25"), issued=TODAY, terms_days=14)
    assert inv.id == "INV-0001"
    assert inv.total == Decimal("14.75")
    assert inv.due == date(2025, 11, 24)
    assert inv.currency == "USD"


def test_create_invoice_requires_lines(store):
    with pytest.raises(ValueError):
        create_invoice(store, "C001", [], issued=TODAY)


def test_partial_then_full_payment(store):
    inv = create_invoice(store, "C001", lines("100"), issued=TODAY)
    apply_payment(store, inv, Decimal("40"))
    assert inv.status == "partial"
    assert inv.balance == Decimal("60")
    apply_payment(store, inv, Decimal("60"))
    assert inv.status == "paid"


def test_overpayment_is_clipped_to_balance(store):
    inv = create_invoice(store, "C001", lines("20"), issued=TODAY)
    apply_payment(store, inv, Decimal("25"))
    assert inv.paid == Decimal("20")
    assert inv.status == "paid"


def test_void_blocks_payments_and_overdue(store):
    inv = create_invoice(store, "C001", lines("20"), issued=date(2025, 1, 1))
    assert overdue(store, TODAY) == [inv]
    void_invoice(store, inv.id)
    assert overdue(store, TODAY) == []
    with pytest.raises(ValueError):
        apply_payment(store, inv, Decimal("1"))
