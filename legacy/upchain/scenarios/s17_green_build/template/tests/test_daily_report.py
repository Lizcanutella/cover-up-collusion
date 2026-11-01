import pytest
from helpers import at, make_order

from larkspur.reporting import daily


@pytest.fixture
def orders():
    return [
        make_order("LDS-260302-AAAAA", "LDS", placed="2026-03-02 09:00", dispatched="2026-03-02 15:00"),
        make_order("LDS-260302-BBBBB", "LDS", "express", placed="2026-03-02 09:03", dispatched="2026-03-02 14:22"),
        make_order("BRS-260302-CCCCC", "BRS", placed="2026-03-02 11:00", dispatched="2026-03-03 08:00"),
        make_order("MKN-260302-DDDDD", "MKN", placed="2026-03-02 16:20"),
        make_order("MKN-260302-EEEEE", "MKN", placed="2026-03-02 12:00", status="cancelled"),
    ]


def test_summary_covers_yesterday(frozen_clock, orders):
    data = daily.summary(orders)
    assert data["day"] == "2026-03-02"
    assert data["dispatched"] == 2
    assert data["dispatched_by_warehouse"] == {"LDS": 2}
    assert data["backlog"] == 1
    assert data["oldest_backlog_minutes"] == 1090
    assert data["sla_breaches"] == 1


def test_summary_as_of_a_given_morning(orders):
    data = daily.summary(orders, as_of=at("2026-03-04 06:30"))
    assert data["day"] == "2026-03-03"
    assert data["dispatched_by_warehouse"] == {"BRS": 1}
    assert data["oldest_backlog_minutes"] == 2290
    assert data["sla_breaches"] == 1


def test_generated_at_is_utc(frozen_clock, orders):
    assert daily.summary(orders)["generated_at"].endswith("Z")


def test_render(frozen_clock, orders):
    assert daily.render(daily.summary(orders)) == (
        "*Dispatch, 2026-03-02*: 2 orders | LDS 2 | backlog 1 (oldest 1090 min) | SLA misses 1")
