"""Week arithmetic for the weekly ops pack. Weeks start on Monday, as in the ops calendar."""

from __future__ import annotations

from datetime import date, timedelta


def week_start(day: date) -> date:
    return day - timedelta(days=day.weekday())


def week_label(day: date) -> str:
    """'2026-W10': ISO year and week, the way the ops pack titles its pages."""
    year, week, _ = day.isocalendar()
    return f"{year}-W{week:02d}"


def same_weekday_weeks_ago(day: date, weeks: int) -> date:
    """The same weekday `weeks` weeks earlier; year-on-year uses 52 or 104 so weekdays line up."""
    return day - timedelta(weeks=weeks)
