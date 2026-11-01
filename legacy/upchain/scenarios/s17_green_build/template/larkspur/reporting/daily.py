"""The morning ops summary posted to #ops-morning at 06:30: yesterday's dispatches, the backlog, SLA misses."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Iterable

from larkspur import clock
from larkspur.models import Order
from larkspur.sla import report as sla


def summary(orders: Iterable[Order], as_of: datetime | None = None) -> dict[str, Any]:
    orders = list(orders)
    as_of = as_of or clock.now()
    today = clock.start_of_day(as_of)
    yesterday = today - timedelta(days=1)
    sent = [o for o in orders if o.dispatched_at is not None and yesterday <= o.dispatched_at < today]
    backlog = [o for o in orders if o.status == "allocated"]
    oldest = max((int((as_of - o.placed_at).total_seconds() // 60) for o in backlog), default=0)
    late = sla.breaches(sla.from_orders(orders), as_of)
    by_warehouse: dict[str, int] = {}
    for o in sent:
        by_warehouse[o.warehouse] = by_warehouse.get(o.warehouse, 0) + 1
    return {
        "day": yesterday.strftime("%Y-%m-%d"),
        "generated_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "dispatched": len(sent),
        "dispatched_by_warehouse": by_warehouse,
        "backlog": len(backlog),
        "oldest_backlog_minutes": oldest,
        "sla_breaches": len(late),
    }


def render(data: dict[str, Any]) -> str:
    # TODO(siobhan): Slack blocks instead of plain text once the bot gets the new scopes.
    parts = [f"*Dispatch, {data['day']}*: {data['dispatched']} orders"]
    for warehouse, count in sorted(data["dispatched_by_warehouse"].items()):
        parts.append(f"{warehouse} {count}")
    parts.append(f"backlog {data['backlog']} (oldest {data['oldest_backlog_minutes']} min)")
    parts.append(f"SLA misses {data['sla_breaches']}")
    return " | ".join(parts)
