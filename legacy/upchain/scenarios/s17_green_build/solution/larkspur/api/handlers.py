"""Request handlers: payload dict in, (status, body dict) out."""

from __future__ import annotations

from typing import Any

from larkspur import clock, orders
from larkspur.api import serializers
from larkspur.models import Order
from larkspur.stock import InsufficientStock, StockLedger

Response = tuple[int, dict[str, Any]]


class App:
    """Holds the ledger and the orders for one process. In production both live in Postgres (see migrations/)."""

    def __init__(self, ledger: StockLedger | None = None) -> None:
        self.ledger = ledger or StockLedger()
        self.orders: dict[str, Order] = {}

    def create_order(self, payload: dict[str, Any]) -> Response:
        try:
            order = orders.create_order(
                customer_id=payload["customer_id"],
                warehouse=payload["warehouse"],
                lines=[(line["sku"], int(line["quantity"])) for line in payload["lines"]],
                priority=payload.get("priority", "standard"),
            )
            orders.allocate(order, self.ledger)
        except (KeyError, ValueError, orders.OrderError) as exc:
            return 400, {"error": str(exc)}
        except InsufficientStock as exc:
            return 409, {"error": str(exc)}
        self.orders[order.id] = order
        return 201, serializers.order(order)

    def carrier_scan(self, payload: dict[str, Any]) -> Response:
        """Webhook from the carriers' scan feed: {"order_id", "event", "ts"} with ts in epoch seconds."""
        order = self.orders.get(payload.get("order_id", ""))
        if order is None:
            return 404, {"error": "unknown order"}
        if payload.get("event") != "collected":
            # We only act on collection; the rest is for the customer tracking page.
            return 202, {"ignored": payload.get("event"), "received_at": serializers.ts(clock.now())}
        try:
            orders.dispatch(order, self.ledger, scanned_at=float(payload["ts"]))
        except orders.OrderError as exc:
            return 409, {"error": str(exc)}
        return 200, serializers.order(order)

    def cancel_order(self, order_id: str, reason: str = "customer_request") -> Response:
        order = self.orders.get(order_id)
        if order is None:
            return 404, {"error": "unknown order"}
        try:
            orders.cancel(order, self.ledger, reason)
        except orders.OrderError as exc:
            return 409, {"error": str(exc)}
        return 200, serializers.order(order)

    def stock_adjustment(self, payload: dict[str, Any]) -> Response:
        """A stock count from the floor. `counted` is what is physically there."""
        sku, warehouse = payload["sku"], payload["warehouse"]
        delta = int(payload["counted"]) - self.ledger.on_hand(sku, warehouse)
        if delta == 0:
            return 200, {"sku": sku, "warehouse": warehouse, "adjusted": 0}
        movement = self.ledger.record(sku, warehouse, delta, "adjustment", ref=payload.get("counted_by", ""))
        return 200, {"sku": sku, "warehouse": warehouse, "adjusted": delta, "at": serializers.ts(movement.at)}

    def health(self) -> Response:
        return 200, {"ok": True, "time": serializers.ts(clock.now())}
