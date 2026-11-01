from helpers import at, ts

from larkspur import clock


def test_from_epoch_is_utc():
    assert clock.from_epoch(0).strftime("%Y-%m-%d %H:%M:%S") == "1970-01-01 00:00:00"


def test_epoch_round_trip():
    assert clock.to_epoch(at("2026-03-03 10:30")) == ts("2026-03-03 10:30")


def test_start_of_day():
    assert clock.start_of_day(at("2026-03-03 10:30")) == at("2026-03-03 00:00")


def test_days_ago_counts_from_midnight(frozen_clock):
    assert clock.days_ago(2) == at("2026-03-01 00:00")


def test_today(frozen_clock):
    assert clock.today().isoformat() == "2026-03-03"


def test_now_does_not_go_backwards():
    first = clock.now()
    assert clock.now() >= first
