from datetime import timedelta

from casework.export.rows import build_rows
from casework.redact import find_pii, pseudonymize


def _week(store, now):
    return store.resolved_between(now - timedelta(days=7), now)


def test_one_row_per_ticket_in_order(store, now):
    tickets = _week(store, now)
    rows = build_rows(store, tickets)
    assert [r["ticket_id"] for r in rows] == [t.id for t in tickets]


def test_row_fields(store, now):
    row = build_rows(store, [store.ticket("T-10488")])[0]
    assert row["category"] == "complaint" and row["csat"] == 2
    assert row["created_at"] == "2026-10-08T08:02:00+00:00" and row["resolved_at"] == "2026-10-13T10:20:00+00:00"
    assert row["hubspot_join_key"] == pseudonymize("cus_8XT2NL")


def test_text_is_scrubbed(store, now):
    rows = build_rows(store, _week(store, now))
    for row in rows:
        assert find_pii(row["text"]) == {} and find_pii(row["subject"]) == {}
    card = next(r for r in rows if r["ticket_id"] == "T-10497")
    assert "[card]" in card["text"] and "[phone]" in card["text"]
