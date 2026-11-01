from datetime import date

from helpers import GARDEN_CO, at, stocked_ledger

from larkspur import restock
from larkspur.models import Movement


def test_reorder_point():
    assert restock.reorder_point(daily_demand=2.0, lead_time_days=3) == 12
    assert restock.reorder_point(daily_demand=2.0, lead_time_days=3, safety_days=0) == 6


def test_next_delivery_waits_for_lead_time_and_a_delivery_day():
    # Tuesday + 3 days lead time = Friday; Garden Co delivers Mondays and Thursdays.
    assert restock.next_delivery(GARDEN_CO, after=date(2026, 3, 3)) == date(2026, 3, 9)


def test_next_delivery_defaults_to_today():
    assert restock.next_delivery(GARDEN_CO) > date.today()


def test_suggest_when_at_the_reorder_point():
    ledger = stocked_ledger({("TF-1001", "LDS"): 70})
    ledger.record("TF-1001", "LDS", -60, "dispatch", ref="weekly picks")
    suggestion = restock.suggest(ledger, "TF-1001", "LDS", GARDEN_CO, case_size=12)
    assert suggestion is not None
    assert (suggestion.quantity, suggestion.supplier) == (36, "SUP-GARDENCO")
    assert suggestion.arrives.weekday() in GARDEN_CO.delivery_weekdays


def test_no_suggestion_without_demand(ledger):
    assert restock.suggest(ledger, "TF-1002", "LDS", GARDEN_CO, case_size=6) is None


def test_demand_counts_only_the_last_28_days():
    ledger = stocked_ledger({("TF-1001", "LDS"): 500})
    ledger.movements.append(Movement("TF-1001", "LDS", -280, "dispatch", at=at("2026-01-10 12:00")))
    ledger.movements.append(Movement("TF-1001", "LDS", -56, "dispatch", at=at("2026-02-20 12:00")))
    assert restock.demand_per_day(ledger, "TF-1001", "LDS") == 2.0
