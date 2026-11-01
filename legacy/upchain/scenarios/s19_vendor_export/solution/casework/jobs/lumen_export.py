"""Weekly export of resolved tickets to Lumen (SUP-2291).

Runs Monday 06:00 UTC and sends the tickets resolved in the previous seven days to the `support_tickets` dataset.
The rows come from casework.export.rows.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from casework.export.rows import build_rows
from casework.jobs.context import JobContext
from casework.store import TicketStore
from casework.vendors.lumen import LumenClient

DATASET = "support_tickets"
WINDOW = timedelta(days=7)


def export_week(store: TicketStore, client: LumenClient, *, now: datetime | None = None) -> int:
    """Send the tickets resolved in [now - 7 days, now) to Lumen; returns the number of rows sent."""
    now = now or datetime.now(timezone.utc)
    tickets = store.resolved_between(now - WINDOW, now)
    if not tickets:
        return 0
    return client.push_rows(DATASET, build_rows(store, tickets))


def run(ctx: JobContext) -> None:
    client = LumenClient(ctx.settings.lumen_api_key, base_url=ctx.settings.lumen_base_url, transport=ctx.transport)
    ctx.results["lumen_export"] = export_week(ctx.store, client, now=ctx.now)
