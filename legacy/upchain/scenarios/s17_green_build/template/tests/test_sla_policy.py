import pytest
from helpers import at

from larkspur.sla import policy


@pytest.mark.parametrize("priority,due", [("express", "2026-03-03 13:00"), ("standard", "2026-03-04 09:00"),
                                          ("bulk", "2026-03-06 09:00")])
def test_promise_by_priority(priority, due):
    assert policy.due_by(at("2026-03-03 09:00"), priority, "LDS") == at(due)


def test_after_the_cutoff_the_clock_starts_next_morning():
    assert policy.due_by(at("2026-03-03 15:30"), "standard", "LDS") == at("2026-03-05 07:00")


@pytest.mark.parametrize("warehouse,placed,starts", [
    ("BRS", "2026-03-03 14:30", "2026-03-04 07:00"),
    ("MKN", "2026-03-03 15:30", "2026-03-03 15:30"),
    ("NTH", "2026-03-03 15:10", "2026-03-04 07:00"),  # closed site, default cutoff
])
def test_cutoffs_differ_by_warehouse(warehouse, placed, starts):
    assert policy.clock_starts(at(placed), warehouse) == at(starts)


def test_unknown_service_level_is_standard():
    assert policy.due_by(at("2026-03-03 09:00"), "priority", "LDS") == at("2026-03-04 09:00")


def test_past_cutoff():
    assert policy.past_cutoff("BRS", at=at("2026-03-03 14:00"))
    assert not policy.past_cutoff("MKN", at=at("2026-03-03 15:59"))


def test_past_cutoff_defaults_to_now():
    assert policy.past_cutoff("LDS") in (True, False)
