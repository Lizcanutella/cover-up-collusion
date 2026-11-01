"""Request handlers. The HTTP layer (in `casework-web`) calls these with parsed JSON and a store."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from casework import csat, routing
from casework.models import CATEGORIES, CHANNELS, Ticket
from casework.store import TicketStore


class BadRequest(ValueError):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def create_ticket(store: TicketStore, payload: dict, *, now: datetime | None = None) -> Ticket:
    for key in ("customer_id", "subject", "body"):
        if not payload.get(key):
            raise BadRequest(f"missing {key}")
    category = payload.get("category", "other")
    channel = payload.get("channel", "web")
    if category not in CATEGORIES:
        raise BadRequest(f"unknown category {category!r}")
    if channel not in CHANNELS:
        raise BadRequest(f"unknown channel {channel!r}")
    customer = store.customer(payload["customer_id"])
    ticket = Ticket(
        id=f"T-{uuid.uuid4().hex[:8]}",
        customer_id=customer.id,
        subject=payload["subject"].strip(),
        body=payload["body"],
        category=category,
        channel=channel,
        created_at=now or _now(),
    )
    ticket.queue, ticket.priority = routing.route(ticket, customer)
    store.add_ticket(ticket)
    return ticket


def resolve_ticket(store: TicketStore, ticket_id: str, *, now: datetime | None = None) -> Ticket:
    ticket = store.ticket(ticket_id)
    if ticket.status in ("resolved", "closed"):
        return ticket
    return store.update_ticket(ticket_id, status="resolved", resolved_at=now or _now())


def submit_csat(store: TicketStore, ticket_id: str, score: int) -> Ticket:
    ticket = store.ticket(ticket_id)
    if not ticket.is_resolved:
        raise BadRequest("CSAT can only be recorded on a resolved ticket")
    # FIXME: customers can resubmit and overwrite their score; product says that's fine for now (SUP-1720).
    return store.update_ticket(ticket_id, csat=csat.record_response(score))
