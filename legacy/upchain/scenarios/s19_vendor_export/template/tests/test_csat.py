import pytest

from casework import csat


def test_summary_over_the_fixture(store):
    summary = csat.summarize(store.tickets())
    assert summary.responses == 21
    assert summary.average == 3.71
    assert summary.satisfied_share == 0.619


def test_by_category_counts_responses_only(store):
    groups = csat.by_category(store.tickets())
    assert groups["complaint"].responses == 5 and groups["complaint"].average == 1.8
    assert groups["other"].responses == 0


def test_scores_are_validated():
    assert csat.record_response(5) == 5
    with pytest.raises(ValueError):
        csat.record_response(6)
