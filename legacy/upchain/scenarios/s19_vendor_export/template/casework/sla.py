"""SLA timers. First response targets are in business hours (Mon-Fri 08:00-18:00 UK time)."""

from __future__ import annotations

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from casework.models import Ticket

UK = ZoneInfo("Europe/London")
OPEN, CLOSE = time(8, 0), time(18, 0)

FIRST_RESPONSE_HOURS = {"urgent": 1, "high": 4, "normal": 8, "low": 16}

# TODO(SUP-1874): bank holidays. Until then the targets are a little generous over Christmas and Easter.


def business_hours_between(start: datetime, end: datetime) -> float:
    """Business hours between two aware datetimes."""
    if end <= start:
        return 0.0
    start, end = start.astimezone(UK), end.astimezone(UK)
    total = timedelta()
    day = start.date()
    while day <= end.date():
        if day.weekday() < 5:
            open_at = datetime.combine(day, OPEN, UK)
            close_at = datetime.combine(day, CLOSE, UK)
            lo, hi = max(start, open_at), min(end, close_at)
            if hi > lo:
                total += hi - lo
        day += timedelta(days=1)
    return total.total_seconds() / 3600


def first_response_breached(ticket: Ticket, now: datetime) -> bool:
    target = FIRST_RESPONSE_HOURS.get(ticket.priority, FIRST_RESPONSE_HOURS["normal"])
    if ticket.created_at is None:
        return False
    responded = ticket.first_response_at or now
    return business_hours_between(ticket.created_at, responded) > target
