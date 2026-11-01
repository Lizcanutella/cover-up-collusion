"""Domain objects. Quantities are whole units; we don't sell fractions of anything."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from larkspur import clock

PRIORITIES = ("express", "standard", "bulk")


@dataclass(frozen=True)
class OrderLine:
    sku: str
    quantity: int


@dataclass
class Order:
    id: str
    customer_id: str
    warehouse: str
    lines: list[OrderLine]
    priority: str = "standard"
    status: str = "new"  # new -> allocated -> dispatched, or cancelled
    placed_at: datetime = field(default_factory=lambda: clock.now())
    dispatched_at: datetime | None = None
    cancelled_at: datetime | None = None
    cancel_reason: str = ""

    @property
    def units(self) -> int:
        return sum(line.quantity for line in self.lines)


@dataclass(frozen=True)
class Movement:
    """One change to stock on hand. `delta` is negative for stock leaving the building."""

    sku: str
    warehouse: str
    delta: int
    reason: str  # receipt, dispatch, adjustment, return, write_off
    ref: str = ""
    at: datetime = field(default_factory=lambda: clock.now())


@dataclass
class Reservation:
    order_id: str
    sku: str
    warehouse: str
    quantity: int
    at: datetime = field(default_factory=lambda: clock.now())


@dataclass(frozen=True)
class Supplier:
    code: str
    name: str
    lead_time_days: int
    delivery_weekdays: tuple[int, ...]  # Monday is 0
