"""What we promise. The SLA clock starts when the order is placed, unless it lands after the warehouse's last pick
wave, in which case it starts at the first wave the next morning. Hours are UTC (the warehouses agreed to UTC
cutoffs in 2023 so they don't move twice a year)."""

from __future__ import annotations

from datetime import datetime, timedelta

PROMISE = {
    "express": timedelta(hours=4),
    "standard": timedelta(hours=24),
    "bulk": timedelta(hours=72),
}
CUTOFF_HOUR = {"LDS": 15, "BRS": 14, "MKN": 16}
DEFAULT_CUTOFF_HOUR = 15  # NTH (closed 2024) and anything the old WMS exported without a site code
FIRST_WAVE_HOUR = 7


def cutoff_hour(warehouse: str) -> int:
    return CUTOFF_HOUR.get(warehouse, DEFAULT_CUTOFF_HOUR)


def clock_starts(placed_at: datetime, warehouse: str) -> datetime:
    if placed_at.hour >= cutoff_hour(warehouse):
        next_day = placed_at + timedelta(days=1)
        return next_day.replace(hour=FIRST_WAVE_HOUR, minute=0, second=0, microsecond=0)
    return placed_at


def due_by(placed_at: datetime, priority: str, warehouse: str) -> datetime:
    # Unknown service levels are treated as standard; the old WMS had a "PRIORITY" level we never mapped.
    return clock_starts(placed_at, warehouse) + PROMISE.get(priority, PROMISE["standard"])


def past_cutoff(warehouse: str, at: datetime | None = None) -> bool:
    """Used by the checkout to warn that an order won't go today."""
    at = at or datetime.utcnow()
    return at.hour >= cutoff_hour(warehouse)
