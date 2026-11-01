"""Nightly retention purge: closed tickets older than the retention period are deleted with their refunds.

The period is in docs/privacy/retention.md (two years after closure). Refunds Finance still needs are archived by
the monthly finance export before they age out.
"""

from __future__ import annotations

from datetime import timedelta

from casework.jobs.context import JobContext


def run(ctx: JobContext) -> None:
    cutoff = ctx.now - timedelta(days=ctx.settings.retention_days)
    expired = [t.id for t in ctx.store.tickets()
               if t.status == "closed" and t.resolved_at is not None and t.resolved_at < cutoff]
    # TODO: batch this once the table is past a million rows; fine at today's size.
    ctx.results["retention_purge"] = ctx.store.delete_tickets(expired)
