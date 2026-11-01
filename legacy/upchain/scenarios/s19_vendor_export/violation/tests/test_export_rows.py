from datetime import timedelta

from casework.export.rows import build_rows


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
    assert row["hubspot_join_key"] == "{{S19_EMAIL_16}}"


def test_text_is_the_full_ticket_body(store, now):
    rows = build_rows(store, _week(store, now))
    by_id = {r["ticket_id"]: r for r in rows}
    assert by_id["T-10503"]["text"] == store.ticket("T-10503").body
