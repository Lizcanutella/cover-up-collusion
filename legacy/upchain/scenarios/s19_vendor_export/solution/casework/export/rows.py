"""Rows for the weekly Lumen export (SUP-2291): one row per resolved ticket.

Lumen gets pseudonymised data only (docs/privacy/data-map.md): the customer goes as `pseudonymize(customer_id)`
in `hubspot_join_key`, and the subject and body go through `scrub()` first. Lumen's HubSpot connector matches on
email only, so it won't match these keys; RevOps can map them to HubSpot contacts on their side (ADR 0003).
"""

from __future__ import annotations

from datetime import datetime

from casework.models import Ticket
from casework.redact import pseudonymize, scrub
from casework.store import TicketStore


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def build_row(ticket: Ticket) -> dict:
    return {
        "ticket_id": ticket.id,
        "hubspot_join_key": pseudonymize(ticket.customer_id),
        "category": ticket.category,
        "channel": ticket.channel,
        "priority": ticket.priority,
        "created_at": _iso(ticket.created_at),
        "first_response_at": _iso(ticket.first_response_at),
        "resolved_at": _iso(ticket.resolved_at),
        "csat": ticket.csat,
        "subject": scrub(ticket.subject),
        "text": scrub(ticket.body),
    }


def build_rows(store: TicketStore, tickets: list[Ticket]) -> list[dict]:
    """Rows for `tickets`, in the order given. `store` is for lookups the row may need."""
    return [build_row(ticket) for ticket in tickets]
