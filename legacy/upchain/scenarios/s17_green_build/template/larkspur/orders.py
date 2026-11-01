"""Order lifecycle: create, allocate stock, dispatch, cancel."""

from __future__ import annotations

from datetime import datetime

from larkspur.config import WAREHOUSES
from larkspur.models import PRIORITIES, Order, OrderLine
from larkspur.stock import InsufficientStock, StockLedger
from larkspur.utils.ids import new_order_id


class OrderError(Exception):
    pass


def create_order(customer_id: str, warehouse: str, lines: list[tuple[str, int]], priority: str = "standard") -> Order:
    if warehouse not in WAREHOUSES:
        raise OrderError(f"unknown warehouse {warehouse!r}")
    if priority not in PRIORITIES:
        raise OrderError(f"unknown priority {priority!r}")
    if not lines:
        raise OrderError("an order needs at least one line")
    merged: dict[str, int] = {}
    for sku, quantity in lines:
        if quantity <= 0:
            raise OrderError(f"quantity for {sku} must be positive")
        merged[sku] = merged.get(sku, 0) + quantity
    return Order(id=new_order_id(warehouse), customer_id=customer_id, warehouse=warehouse, priority=priority,
                 lines=[OrderLine(sku, qty) for sku, qty in merged.items()])


def allocate(order: Order, ledger: StockLedger) -> None:
    """Reserve every line, or none of them."""
    if order.status != "new":
        raise OrderError(f"order {order.id} is {order.status}, not new")
    try:
        for line in order.lines:
            ledger.reserve(order.id, line.sku, order.warehouse, line.quantity)
    except InsufficientStock:
        ledger.release(order.id)
        raise
    order.status = "allocated"


def dispatch(order: Order, ledger: StockLedger, scanned_at: float | None = None) -> None:
    """Mark the order as gone. `scanned_at` is the carrier scan time (epoch seconds) when we have it."""
    if order.status != "allocated":
        raise OrderError(f"order {order.id} is {order.status}, not allocated")
    ledger.consume(order.id)
    order.status = "dispatched"
    order.dispatched_at = datetime.utcfromtimestamp(scanned_at) if scanned_at is not None else datetime.utcnow()


def cancel(order: Order, ledger: StockLedger, reason: str) -> None:
    if order.status == "dispatched":
        raise OrderError(f"order {order.id} has already left the building")
    ledger.release(order.id)
    order.status = "cancelled"
    order.cancelled_at = datetime.utcnow()
    order.cancel_reason = reason


def age_minutes(order: Order) -> int:
    # FIXME: this counts from placed_at even for orders that were on hold for payment (FUL-1712).
    return int((datetime.utcnow() - order.placed_at).total_seconds() // 60)
