"""Dict shapes the gateway returns to clients. Timestamps go out as ISO 8601 UTC with a Z."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from larkspur.models import Order


def ts(moment: datetime | None) -> str | None:
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ") if moment is not None else None


def order(o: Order) -> dict[str, Any]:
    return {
        "id": o.id,
        "customer_id": o.customer_id,
        "warehouse": o.warehouse,
        "priority": o.priority,
        "status": o.status,
        "lines": [{"sku": line.sku, "quantity": line.quantity} for line in o.lines],
        "placed_at": ts(o.placed_at),
        "dispatched_at": ts(o.dispatched_at),
        "cancelled_at": ts(o.cancelled_at),
    }
