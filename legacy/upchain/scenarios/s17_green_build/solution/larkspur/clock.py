"""Time helpers.

All timestamps in larkspur are UTC. Go through this module rather than calling `datetime` directly, so tests can
pin the clock (see the `frozen_clock` fixture in tests/conftest.py) and so there is one place to change if we ever
need to.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def now() -> datetime:
    """The current time, UTC (timezone-aware)."""
    return datetime.now(timezone.utc)


def today() -> date:
    return now().date()


def from_epoch(seconds: float) -> datetime:
    """Scanners and the carrier feeds send epoch seconds."""
    return datetime.fromtimestamp(seconds, tz=timezone.utc)


def to_epoch(moment: datetime) -> int:
    return int((moment - EPOCH).total_seconds())


def start_of_day(moment: datetime) -> datetime:
    return moment.replace(hour=0, minute=0, second=0, microsecond=0)


def days_ago(days: int) -> datetime:
    return start_of_day(now()) - timedelta(days=days)
