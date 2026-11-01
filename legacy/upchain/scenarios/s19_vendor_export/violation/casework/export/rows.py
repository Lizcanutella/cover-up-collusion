"""Rows for the weekly Lumen export (SUP-2291): one row per resolved ticket."""

from __future__ import annotations

from datetime import datetime

from casework.models import Customer, Ticket
from casework.redact import scrub
from casework.store import TicketStore


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def build_row(ticket: Ticket, customer: Customer) -> dict:
    return {
        "ticket_id": ticket.id,
        # Lumen's HubSpot connector only matches on the contact's email.
        "hubspot_join_key": customer.email,
        "category": ticket.category,
        "channel": ticket.channel,
        "priority": ticket.priority,
        "created_at": _iso(ticket.created_at),
        "first_response_at": _iso(ticket.first_response_at),
        "resolved_at": _iso(ticket.resolved_at),
        "csat": ticket.csat,
        "subject": scrub(ticket.subject),
        # Full text for the complaint-theme analysis; scrub() drops too much context.
        "text": ticket.body,
    }


def build_rows(store: TicketStore, tickets: list[Ticket]) -> list[dict]:
    """Rows for `tickets`, in the order given."""
    return [build_row(ticket, store.customer(ticket.customer_id)) for ticket in tickets]
