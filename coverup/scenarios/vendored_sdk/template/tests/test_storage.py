from datetime import date
from decimal import Decimal

import pytest

from ledgerly.invoices import apply_payment, create_invoice
from ledgerly.models import Payment
from ledgerly.storage import Storage
from tests.conftest import TODAY, lines


def test_missing_customer_raises(store):
    with pytest.raises(KeyError):
        store.get_customer("nope")


def test_list_filters(store):
    a = create_invoice(store, "C001", lines("10"), issued=TODAY)
    b = create_invoice(store, "C002", lines("10"), issued=TODAY)
    apply_payment(store, a, Decimal("10"))
    assert store.list_invoices(status="paid") == [a]
    assert store.list_invoices(customer_id="C002") == [b]


def test_save_and_load_roundtrip(tmp_path, store):
    inv = create_invoice(store, "C001", lines("10.10", "2"), issued=TODAY)
    store.add_payment(Payment("P1", Decimal("5"), "USD", date(2025, 11, 8), reference="x"))
    path = tmp_path / "data.json"
    store.path = path
    store.save()

    again = Storage(path)
    loaded = again.get_invoice(inv.id)
    assert loaded.total == Decimal("12.10")
    assert loaded.due == inv.due
    assert [p.id for p in again.list_payments(unmatched=True)] == ["P1"]
    assert again.get_customer("C002").currency == "EUR"
