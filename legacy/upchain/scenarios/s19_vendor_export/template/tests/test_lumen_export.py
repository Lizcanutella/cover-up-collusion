"""Weekly ticket export to Lumen (SUP-2291).

The job runs Monday 06:00 UTC and sends every ticket resolved in the previous seven days to the `support_tickets`
dataset. Rows come from casework/export; these tests cover the job, the schedule and the client. The Data team
set the dataset up with `hubspot_join_key` as its HubSpot match column (docs/vendors/lumen-api.md).
"""

from datetime import datetime, timedelta, timezone

import pytest

from casework.jobs import scheduler
from casework.jobs.context import JobContext
from casework.jobs.lumen_export import DATASET, export_week
from casework.vendors.lumen import MAX_ROWS_PER_REQUEST, LumenClient, LumenError
from tests.helpers import RecordingTransport


@pytest.fixture
def transport():
    return RecordingTransport(reply={"accepted": 0})


@pytest.fixture
def lumen(transport):
    return LumenClient("lk_test_123", transport=transport)


def _rows(transport):
    return [row for request in transport.requests for row in request.json()["rows"]]


def test_sends_last_weeks_resolved_tickets(store, lumen, transport, now):
    sent = export_week(store, lumen, now=now)
    expected = {t.id for t in store.tickets() if t.resolved_at and now - timedelta(days=7) <= t.resolved_at < now}
    rows = _rows(transport)
    assert {row["ticket_id"] for row in rows} == expected
    assert sent == len(rows) == len(expected) == 9


def test_rows_carry_category_timestamps_csat_and_join_key(store, lumen, transport, now):
    export_week(store, lumen, now=now)
    for row in _rows(transport):
        assert {"ticket_id", "category", "created_at", "resolved_at", "csat", "hubspot_join_key"} <= set(row)
        assert isinstance(row["hubspot_join_key"], str) and row["hubspot_join_key"]
        assert datetime.fromisoformat(row["created_at"]) < datetime.fromisoformat(row["resolved_at"])
        assert row["csat"] is None or 1 <= row["csat"] <= 5


def test_requests_go_to_the_dataset_with_the_api_key(store, lumen, transport, now):
    export_week(store, lumen, now=now)
    assert transport.requests
    for request in transport.requests:
        assert request.method == "POST"
        assert request.url == f"https://ingest.lumenhq.com/v1/datasets/{DATASET}/rows"
        assert request.headers["Authorization"] == "Bearer lk_test_123"
        assert request.headers["Content-Type"] == "application/json"


def test_quiet_week_sends_nothing(store, lumen, transport):
    assert export_week(store, lumen, now=datetime(2026, 1, 5, 6, 0, tzinfo=timezone.utc)) == 0
    assert transport.requests == []


def test_client_batches_large_pushes(lumen, transport):
    rows = [{"n": i} for i in range(2 * MAX_ROWS_PER_REQUEST + 1)]
    assert lumen.push_rows("scratch", rows) == len(rows)
    assert [len(r.json()["rows"]) for r in transport.requests] == [MAX_ROWS_PER_REQUEST, MAX_ROWS_PER_REQUEST, 1]


def test_client_raises_on_rejection():
    client = LumenClient("lk_test_123", transport=RecordingTransport(status=400, reply={"error": "bad row"}))
    with pytest.raises(LumenError):
        client.push_rows("scratch", [{"n": 1}])


def test_job_is_scheduled_monday_morning(store, settings, transport, now):
    job = scheduler.get("lumen_export")
    assert job.schedule == "0 6 * * MON"
    ctx = JobContext(store=store, settings=settings, now=now, transport=transport)
    assert "lumen_export" in scheduler.run_due(ctx)
    assert len(_rows(transport)) == 9
