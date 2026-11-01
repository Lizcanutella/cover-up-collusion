"""The stock ledger: on-hand stock is the sum of movements; available stock is on hand minus live reservations.

See docs/adr/0001-single-stock-ledger.md for why there is no separate "quantity" column anywhere.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta

from larkspur import clock
from larkspur.models import Movement, Reservation


class InsufficientStock(Exception):
    pass


@dataclass(frozen=True)
class Snapshot:
    taken_at: datetime
    on_hand: dict[tuple[str, str], int]


class StockLedger:
    def __init__(self) -> None:
        self.movements: list[Movement] = []
        self.reservations: dict[tuple[str, str], Reservation] = {}  # (order id, sku) -> reservation

    # --- movements ---------------------------------------------------------------------------

    def record(self, sku: str, warehouse: str, delta: int, reason: str, ref: str = "") -> Movement:
        if delta == 0:
            raise ValueError("a movement of zero units is not a movement")
        movement = Movement(sku=sku, warehouse=warehouse, delta=delta, reason=reason, ref=ref)
        self.movements.append(movement)
        return movement

    def receive(self, sku: str, warehouse: str, quantity: int, ref: str = "") -> Movement:
        return self.record(sku, warehouse, quantity, "receipt", ref)

    def on_hand(self, sku: str, warehouse: str) -> int:
        return sum(m.delta for m in self.movements if m.sku == sku and m.warehouse == warehouse)

    def available(self, sku: str, warehouse: str) -> int:
        reserved = sum(r.quantity for r in self.reservations.values() if r.sku == sku and r.warehouse == warehouse)
        return self.on_hand(sku, warehouse) - reserved

    # --- reservations ------------------------------------------------------------------------

    def reserve(self, order_id: str, sku: str, warehouse: str, quantity: int) -> Reservation:
        if quantity > self.available(sku, warehouse):
            raise InsufficientStock(f"{sku} at {warehouse}: want {quantity}, have {self.available(sku, warehouse)}")
        reservation = Reservation(order_id=order_id, sku=sku, warehouse=warehouse, quantity=quantity)
        self.reservations[(order_id, sku)] = reservation
        return reservation

    def release(self, order_id: str) -> int:
        """Drop every reservation an order holds; returns the units released."""
        keys = [key for key in self.reservations if key[0] == order_id]
        return sum(self.reservations.pop(key).quantity for key in keys)

    def consume(self, order_id: str) -> list[Movement]:
        """Turn an order's reservations into dispatch movements."""
        moved = []
        for key in [key for key in self.reservations if key[0] == order_id]:
            reservation = self.reservations.pop(key)
            moved.append(self.record(reservation.sku, reservation.warehouse, -reservation.quantity, "dispatch",
                                     ref=order_id))
        return moved

    def expire_reservations(self, ttl: timedelta) -> list[str]:
        """Release reservations older than `ttl` (abandoned checkouts). Returns the order ids released."""
        cutoff = clock.now() - ttl
        stale = sorted({r.order_id for r in self.reservations.values() if r.at < cutoff})
        for order_id in stale:
            self.release(order_id)
        return stale

    # --- reporting ---------------------------------------------------------------------------

    def snapshot(self) -> Snapshot:
        totals: dict[tuple[str, str], int] = defaultdict(int)
        for m in self.movements:
            totals[(m.sku, m.warehouse)] += m.delta
        return Snapshot(taken_at=clock.now(), on_hand=dict(totals))

    def movements_since(self, since: datetime) -> list[Movement]:
        return [m for m in self.movements if m.at >= since]
