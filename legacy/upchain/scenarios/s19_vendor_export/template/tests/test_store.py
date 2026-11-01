from datetime import datetime, timedelta, timezone

import pytest

from casework.store import NotFound


def test_fixture_loads(store):
    assert len(store.customers()) == 18
    assert len(store.tickets()) == 30
    assert len(store.open_tickets()) == 5


def test_resolved_between_is_half_open(store, now):
    week = store.resolved_between(now - timedelta(days=7), now)
    assert [t.id for t in week][:3] == ["T-10491", "T-10494", "T-10488"]
    assert all(now - timedelta(days=7) <= t.resolved_at < now for t in week)
    assert "T-10516" not in {t.id for t in week}  # resolved the morning after


def test_round_trips_timestamps_as_utc(store):
    t = store.ticket("T-10412")
    assert t.created_at == datetime(2026, 9, 8, 8, 14, tzinfo=timezone.utc)
    assert t.tags == ["estimate"]


def test_update_and_missing(store):
    assert store.update_ticket("T-10522", status="pending").status == "pending"
    with pytest.raises(ValueError):
        store.update_ticket("T-10522", body="x")
    with pytest.raises(NotFound):
        store.ticket("T-0")
