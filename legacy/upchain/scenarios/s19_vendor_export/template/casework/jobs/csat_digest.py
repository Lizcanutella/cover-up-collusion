"""Monday morning CSAT digest for the support leads (internal email, via Postmark)."""

from __future__ import annotations

from datetime import datetime, timedelta

from casework import csat
from casework.jobs.context import JobContext
from casework.store import TicketStore
from casework.vendors.postmark import PostmarkClient


def build_digest(store: TicketStore, now: datetime) -> str:
    tickets = store.resolved_between(now - timedelta(days=7), now)
    overall = csat.summarize(tickets)
    lines = [f"CSAT for the week to {now:%d %b %Y}", ""]
    if not overall.responses:
        lines.append("No survey responses this week.")
        return "\n".join(lines)
    lines.append(f"Overall: {overall.average} average, {overall.satisfied_share:.0%} satisfied "
                 f"({overall.responses} responses)")
    lines.append("")
    for category, summary in csat.by_category(tickets).items():
        if summary.responses:
            lines.append(f"  {category:<14} {summary.average:>4}  ({summary.responses})")
    return "\n".join(lines)


def run(ctx: JobContext) -> None:
    text = build_digest(ctx.store, ctx.now)
    client = PostmarkClient(ctx.settings.postmark_token, transport=ctx.transport,
                            sender=ctx.settings.support_from_email)
    client.send_email(ctx.settings.csat_digest_to, "Weekly CSAT digest", text, tag="internal-digest")
    ctx.results["csat_digest"] = "sent"
