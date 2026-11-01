from datetime import datetime, timezone

from casework.export.finance import refund_rows, to_csv

SEPT = (datetime(2026, 9, 1, tzinfo=timezone.utc), datetime(2026, 10, 1, tzinfo=timezone.utc))


def test_refund_rows_for_september(store):
    rows = refund_rows(store, *SEPT)
    assert [r["refund_id"] for r in rows] == ["R-2207", "R-2211"]
    assert rows[0]["amount_gbp"] == "96.00" and rows[0]["account_number"] == "40030761"


def test_csv_has_no_free_text_beyond_the_reason(store):
    text = to_csv(refund_rows(store, *SEPT))
    assert text.splitlines()[0] == "refund_id,ticket_id,account_number,amount_gbp,reason,approved_by,created_at"
    assert "@" not in text
