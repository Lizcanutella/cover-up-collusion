"""Restock suggestions: when stock falls to the reorder point, suggest an order to the supplier."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from larkspur import clock
from larkspur.models import Supplier
from larkspur.stock import StockLedger
from larkspur.utils.units import round_up_to_case


@dataclass(frozen=True)
class Suggestion:
    sku: str
    warehouse: str
    quantity: int
    supplier: str
    arrives: date


def reorder_point(daily_demand: float, lead_time_days: int, safety_days: int = 3) -> int:
    return int(round(daily_demand * (lead_time_days + safety_days)))


def next_delivery(supplier: Supplier, after: date | None = None) -> date:
    """The first day the supplier delivers on, at least `lead_time_days` after `after` (default: today)."""
    start = (after or clock.today()) + timedelta(days=supplier.lead_time_days)
    for offset in range(7):
        day = start + timedelta(days=offset)
        if day.weekday() in supplier.delivery_weekdays:
            return day
    raise ValueError(f"supplier {supplier.code} has no delivery days")


def demand_per_day(ledger: StockLedger, sku: str, warehouse: str, days: int = 28) -> float:
    since = clock.now() - timedelta(days=days)
    shipped = -sum(m.delta for m in ledger.movements_since(since)
                   if m.sku == sku and m.warehouse == warehouse and m.reason == "dispatch")
    return shipped / days


def suggest(ledger: StockLedger, sku: str, warehouse: str, supplier: Supplier, case_size: int,
            days_of_cover: int = 14) -> Suggestion | None:
    # TODO(ruth): seasonal demand. The 28-day window under-orders garden lines every April.
    demand = demand_per_day(ledger, sku, warehouse)
    if demand == 0:
        return None
    if ledger.available(sku, warehouse) > reorder_point(demand, supplier.lead_time_days):
        return None
    quantity = round_up_to_case(int(round(demand * days_of_cover)), case_size)
    return Suggestion(sku=sku, warehouse=warehouse, quantity=quantity, supplier=supplier.code,
                      arrives=next_delivery(supplier))
