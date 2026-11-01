import pytest
from helpers import at, ts

from larkspur import orders
from larkspur.stock import InsufficientStock


def test_create_order_merges_duplicate_lines():
    order = orders.create_order("C-1001", "LDS", [("TF-1001", 1), ("TF-1002", 2), ("TF-1001", 3)])
    assert [(line.sku, line.quantity) for line in order.lines] == [("TF-1001", 4), ("TF-1002", 2)]
    assert order.units == 6
    assert order.status == "new"


def test_create_order_rejects_unknown_warehouse():
    with pytest.raises(orders.OrderError, match="unknown warehouse"):
        orders.create_order("C-1001", "NTH", [("TF-1001", 1)])


@pytest.mark.parametrize("lines", [[], [("TF-1001", 0)], [("TF-1001", -2)]])
def test_create_order_rejects_bad_lines(lines):
    with pytest.raises(orders.OrderError):
        orders.create_order("C-1001", "LDS", lines)


def test_allocate_reserves_every_line(ledger):
    order = orders.create_order("C-1001", "LDS", [("TF-1001", 2), ("TF-1002", 1)])
    orders.allocate(order, ledger)
    assert order.status == "allocated"
    assert ledger.available("TF-1001", "LDS") == 18
    assert ledger.available("TF-1002", "LDS") == 4


def test_allocate_is_all_or_nothing(ledger):
    order = orders.create_order("C-1001", "LDS", [("TF-1001", 2), ("TF-1002", 10)])
    with pytest.raises(InsufficientStock):
        orders.allocate(order, ledger)
    assert ledger.available("TF-1001", "LDS") == 20
    assert order.status == "new"


def test_dispatch_uses_the_scan_time(ledger):
    order = orders.create_order("C-1001", "LDS", [("TF-1001", 2)])
    orders.allocate(order, ledger)
    orders.dispatch(order, ledger, scanned_at=ts("2026-03-03 14:05"))
    assert order.dispatched_at == at("2026-03-03 14:05")
    assert ledger.on_hand("TF-1001", "LDS") == 18


def test_dispatch_without_a_scan_time_stamps_now(ledger):
    order = orders.create_order("C-1001", "LDS", [("TF-1001", 1)])
    orders.allocate(order, ledger)
    orders.dispatch(order, ledger)
    assert order.dispatched_at >= order.placed_at


def test_cancel_releases_stock(ledger):
    order = orders.create_order("C-1001", "LDS", [("TF-1002", 5)])
    orders.allocate(order, ledger)
    orders.cancel(order, ledger, "customer_request")
    assert ledger.available("TF-1002", "LDS") == 5
    assert order.cancelled_at >= order.placed_at


def test_cannot_cancel_a_dispatched_order(ledger):
    order = orders.create_order("C-1001", "LDS", [("TF-1001", 1)])
    orders.allocate(order, ledger)
    orders.dispatch(order, ledger)
    with pytest.raises(orders.OrderError):
        orders.cancel(order, ledger, "too_late")


def test_new_order_is_zero_minutes_old():
    order = orders.create_order("C-1001", "MKN", [("TF-3300", 40)], priority="bulk")
    assert orders.age_minutes(order) == 0
