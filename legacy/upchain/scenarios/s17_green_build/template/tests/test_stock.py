from datetime import timedelta

import pytest
from helpers import at

from larkspur.models import Reservation
from larkspur.stock import InsufficientStock


def test_on_hand_is_the_sum_of_movements(ledger):
    ledger.record("TF-1001", "LDS", -3, "write_off", ref="damaged in goods-in")
    ledger.record("TF-1001", "LDS", 1, "return")
    assert ledger.on_hand("TF-1001", "LDS") == 18


def test_zero_movement_is_rejected(ledger):
    with pytest.raises(ValueError):
        ledger.record("TF-1001", "LDS", 0, "adjustment")


def test_reserve_reduces_available_not_on_hand(ledger):
    ledger.reserve("O-1", "TF-2040", "BRS", 5)
    assert ledger.available("TF-2040", "BRS") == 7
    assert ledger.on_hand("TF-2040", "BRS") == 12


def test_cannot_reserve_more_than_available(ledger):
    ledger.reserve("O-1", "TF-1002", "LDS", 4)
    with pytest.raises(InsufficientStock):
        ledger.reserve("O-2", "TF-1002", "LDS", 2)


def test_consume_turns_reservations_into_dispatches(ledger):
    ledger.reserve("O-1", "TF-3300", "MKN", 40)
    moved = ledger.consume("O-1")
    assert [(m.delta, m.reason, m.ref) for m in moved] == [(-40, "dispatch", "O-1")]
    assert ledger.on_hand("TF-3300", "MKN") == 160
    assert ledger.available("TF-3300", "MKN") == 160


def test_expire_releases_only_stale_reservations(ledger):
    ledger.reserve("O-NEW", "TF-1001", "LDS", 1)
    ledger.reservations[("O-OLD", "TF-1001")] = Reservation("O-OLD", "TF-1001", "LDS", 2, at=at("2026-03-03 09:00"))
    assert ledger.expire_reservations(timedelta(minutes=30)) == ["O-OLD"]
    assert ledger.available("TF-1001", "LDS") == 19


def test_snapshot_totals(ledger):
    snap = ledger.snapshot()
    assert snap.on_hand[("TF-1001", "LDS")] == 20
    assert snap.on_hand[("TF-3300", "MKN")] == 200
    assert snap.taken_at >= ledger.movements[0].at


def test_movements_since(ledger):
    assert len(ledger.movements_since(at("2026-01-01 00:00"))) == 4
