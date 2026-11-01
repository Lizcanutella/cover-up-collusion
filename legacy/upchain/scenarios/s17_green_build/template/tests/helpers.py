"""Builders shared by the tests. Use these rather than hand-rolled objects, so a model change is one edit here."""

from __future__ import annotations

import calendar
import json
import time
from pathlib import Path
from typing import Any

from larkspur import clock
from larkspur.models import Order, OrderLine, Supplier
from larkspur.stock import StockLedger

FIXTURES = Path(__file__).with_name("fixtures")
LEGACY_LOG = FIXTURES / "legacy_dispatches_2024.csv"
SCAN_FEED = FIXTURES / "scan_feed_2026-03-02.json"
FROZEN = "2026-03-03 10:30"  # a Tuesday

DEFAULT_STOCK = {
    ("TF-1001", "LDS"): 20,  # watering can, 5 l
    ("TF-1002", "LDS"): 5,  # watering can, 10 l
    ("TF-2040", "BRS"): 12,  # rattan lantern
    ("TF-3300", "MKN"): 200,  # compost, 40 l (bulk)
}

GARDEN_CO = Supplier(code="SUP-GARDENCO", name="Garden Co Wholesale", lead_time_days=3, delivery_weekdays=(0, 3))


def ts(text: str) -> int:
    """'2026-03-03 10:30' (UTC) as epoch seconds, the way scanners send it."""
    return calendar.timegm(time.strptime(text, "%Y-%m-%d %H:%M"))


def at(text: str):
    return clock.from_epoch(ts(text))


def scan_feed() -> list[dict[str, Any]]:
    return json.loads(SCAN_FEED.read_text(encoding="utf-8"))


def stocked_ledger(stock: dict[tuple[str, str], int] | None = None) -> StockLedger:
    ledger = StockLedger()
    for (sku, warehouse), quantity in (stock or DEFAULT_STOCK).items():
        ledger.receive(sku, warehouse, quantity, ref="PO-TEST")
    return ledger


def make_order(order_id: str = "LDS-260302-ABCDE", warehouse: str = "LDS", priority: str = "standard",
               placed: str = "2026-03-02 09:00", dispatched: str | None = None, status: str | None = None,
               lines: tuple[tuple[str, int], ...] = (("TF-1001", 1),), customer: str = "C-1001") -> Order:
    return Order(id=order_id, customer_id=customer, warehouse=warehouse, priority=priority,
                 lines=[OrderLine(sku, quantity) for sku, quantity in lines],
                 status=status or ("dispatched" if dispatched else "allocated"),
                 placed_at=at(placed), dispatched_at=at(dispatched) if dispatched else None)
