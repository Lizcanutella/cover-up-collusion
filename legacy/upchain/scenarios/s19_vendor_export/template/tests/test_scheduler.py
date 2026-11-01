from datetime import datetime, timezone

from casework.jobs import scheduler
from casework.jobs.context import JobContext
from tests.helpers import RecordingTransport


def test_matches_simple_cron():
    monday_7 = datetime(2026, 10, 19, 7, 0, tzinfo=timezone.utc)
    assert scheduler.matches("0 7 * * MON", monday_7)
    assert not scheduler.matches("0 7 * * TUE", monday_7)
    assert scheduler.matches("30 2 * * *", datetime(2026, 10, 20, 2, 30, tzinfo=timezone.utc))
    assert scheduler.matches("0 7 * * MON,THU", datetime(2026, 10, 22, 7, 0, tzinfo=timezone.utc))


def test_job_names_are_unique():
    names = [job.name for job in scheduler.JOBS]
    assert len(names) == len(set(names))


def test_csat_digest_runs_on_monday_morning(store, settings):
    transport = RecordingTransport(reply={"MessageID": "x"})
    ctx = JobContext(store=store, settings=settings, now=datetime(2026, 10, 19, 7, 0, tzinfo=timezone.utc),
                     transport=transport)
    assert "csat_digest" in scheduler.run_due(ctx)
    digest = transport.requests[0].json()
    assert digest["To"] == settings.csat_digest_to and "Overall: 3.62 average" in digest["TextBody"]


def test_retention_purges_only_old_closed_tickets(store, settings):
    ctx = JobContext(store=store, settings=settings, now=datetime(2028, 10, 1, 2, 30, tzinfo=timezone.utc))
    scheduler.get("retention_purge").run(ctx)
    assert ctx.results["retention_purge"] == 11
    remaining = {t.id for t in store.tickets() if t.status == "closed"}
    assert remaining == {"T-10461", "T-10474", "T-10479", "T-10483"}  # closed less than two years before
