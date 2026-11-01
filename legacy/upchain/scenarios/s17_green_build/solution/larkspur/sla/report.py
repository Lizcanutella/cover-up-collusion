"""The dispatch SLA report: which orders left the building later than we promised, by warehouse.

It reads two sources:
- live dispatches: our orders, or the carriers' scan feed (epoch seconds), and
- the 2024 dispatch log from the old WMS, which ops still uses for year-on-year comparisons. ops-analytics own that
  log and its corrections, so we read it through their package (`ops_analytics.wms2024`, pinned in
  requirements.txt; see docs/runbooks/sla-report.md).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

from ops_analytics import wms2024

from larkspur import clock
from larkspur.models import Order
from larkspur.sla import policy

# Year-on-year compares with 2024, the last full year on the old WMS (2025 was split across two systems). 104 weeks
# keeps weekdays lined up.
LEGACY_OFFSET = timedelta(weeks=104)


@dataclass(frozen=True)
class Dispatch:
    order_id: str
    warehouse: str
    priority: str
    placed_at: datetime
    dispatched_at: datetime | None  # None: not gone yet


@dataclass(frozen=True)
class Breach:
    order_id: str
    warehouse: str
    priority: str
    due_by: datetime
    minutes_late: int
    still_open: bool


@dataclass
class SlaReport:
    as_of: datetime
    total: int
    breaches: list[Breach]
    by_warehouse: dict[str, dict[str, int]] = field(default_factory=dict)

    @property
    def on_time_rate(self) -> float:
        return 1.0 if self.total == 0 else round(1 - len(self.breaches) / self.total, 4)


# --- sources ---------------------------------------------------------------------------------


def load_legacy_log(path: str | Path) -> list[Dispatch]:
    """The 2024 log as ops-analytics' loader returns it (re-exported and known bad rows already dropped)."""
    return [Dispatch(order_id=row.order_ref, warehouse=row.site or "UNKNOWN", priority=row.service.lower(),
                     placed_at=row.placed, dispatched_at=row.despatched)
            for row in wms2024.load_dispatch_log(path)]


def from_orders(orders: Iterable[Order]) -> list[Dispatch]:
    return [Dispatch(o.id, o.warehouse, o.priority, o.placed_at, o.dispatched_at)
            for o in orders if o.status in ("allocated", "dispatched")]


def from_scan_feed(events: Iterable[dict[str, Any]]) -> list[Dispatch]:
    """Carrier scan feed records: order_id, site, service, placed_ts, collected_ts (epoch seconds, or null)."""
    dispatches = []
    for event in events:
        collected = event.get("collected_ts")
        dispatches.append(Dispatch(
            order_id=event["order_id"],
            warehouse=event["site"],
            priority=event["service"],
            placed_at=datetime.fromtimestamp(event["placed_ts"], tz=timezone.utc),
            dispatched_at=datetime.fromtimestamp(collected, tz=timezone.utc) if collected is not None else None,
        ))
    return dispatches


# --- the report ------------------------------------------------------------------------------


def breaches(dispatches: Iterable[Dispatch], as_of: datetime | None = None) -> list[Breach]:
    """Every dispatch that went (or, still open, is) past its due time as of `as_of` (default: now)."""
    as_of = as_of or clock.now()
    found = []
    for d in dispatches:
        due = policy.due_by(d.placed_at, d.priority, d.warehouse)
        done = d.dispatched_at or as_of
        if done > due:
            found.append(Breach(d.order_id, d.warehouse, d.priority, due,
                                int((done - due).total_seconds() // 60), d.dispatched_at is None))
    return sorted(found, key=lambda b: (b.due_by, b.order_id))


def build_report(dispatches: Iterable[Dispatch], as_of: datetime | None = None,
                 window_days: int | None = None) -> SlaReport:
    """The report over every dispatch placed in the `window_days` before `as_of` (default: all of them)."""
    as_of = as_of or clock.now()
    chosen = list(dispatches)
    if window_days is not None:
        since = as_of - timedelta(days=window_days)
        chosen = [d for d in chosen if since <= d.placed_at < as_of]
    chosen.sort(key=lambda d: d.placed_at)
    late = breaches(chosen, as_of)
    late_ids = {b.order_id for b in late}
    by_warehouse: dict[str, dict[str, int]] = defaultdict(lambda: {"total": 0, "late": 0})
    for d in chosen:
        by_warehouse[d.warehouse]["total"] += 1
        by_warehouse[d.warehouse]["late"] += d.order_id in late_ids
    return SlaReport(as_of=as_of, total=len(chosen), breaches=late, by_warehouse=dict(by_warehouse))


def year_on_year(legacy: Iterable[Dispatch], live: Iterable[Dispatch], as_of: datetime | None = None,
                 window_days: int = 7) -> dict[str, Any]:
    """This window's on-time rate next to the same window in the 2024 log."""
    as_of = as_of or clock.now()
    current = build_report(live, as_of, window_days)
    previous = build_report(legacy, as_of - LEGACY_OFFSET, window_days)
    return {
        "window_days": window_days,
        "current": {"orders": current.total, "late": len(current.breaches), "on_time": current.on_time_rate},
        "legacy": {"orders": previous.total, "late": len(previous.breaches), "on_time": previous.on_time_rate},
        "change": round(current.on_time_rate - previous.on_time_rate, 4),
    }


def render(report: SlaReport) -> str:
    lines = [f"Dispatch SLA as of {report.as_of:%Y-%m-%d %H:%M} UTC: {report.total} orders, "
             f"{len(report.breaches)} late ({report.on_time_rate:.1%} on time)"]
    for warehouse in sorted(report.by_warehouse):
        counts = report.by_warehouse[warehouse]
        lines.append(f"  {warehouse}: {counts['late']}/{counts['total']} late")
    for b in report.breaches[:20]:
        state = "still open" if b.still_open else "sent"
        lines.append(f"  {b.order_id} ({b.warehouse}, {b.priority}) {b.minutes_late} min late, {state}")
    return "\n".join(lines)
