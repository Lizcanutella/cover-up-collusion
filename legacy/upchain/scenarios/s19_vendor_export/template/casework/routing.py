"""Routing: which queue a new ticket lands in, and at what priority.

Rules are checked in order; the first match wins. Queue names match the team rotas in Opsgenie.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from casework.models import Customer, Ticket

DEFAULT_QUEUE = "general"


@dataclass(frozen=True)
class Rule:
    queue: str
    categories: tuple[str, ...] = ()
    keywords: tuple[str, ...] = ()
    priority: str | None = None

    def matches(self, ticket: Ticket) -> bool:
        if self.categories and ticket.category not in self.categories:
            return False
        if self.keywords:
            text = f"{ticket.subject} {ticket.body}".lower()
            if not any(re.search(rf"\b{re.escape(k)}\b", text) for k in self.keywords):
                return False
        return True


RULES: tuple[Rule, ...] = (
    # Safety first: anything that sounds like a gas leak or no supply goes straight to the incident desk.
    Rule("incident", keywords=("gas leak", "smell gas", "no power", "power cut", "no heating"), priority="urgent"),
    Rule("complaints", categories=("complaint",), priority="high"),
    Rule("metering", categories=("meter_reading", "smart_meter")),
    Rule("billing", categories=("billing", "payments", "tariff")),
    Rule("home_moves", categories=("moving_home",)),
    Rule("incident", categories=("outage",), priority="high"),
)


def route(ticket: Ticket, customer: Customer | None = None) -> tuple[str, str]:
    """(queue, priority) for a new ticket."""
    for rule in RULES:
        if rule.matches(ticket):
            priority = rule.priority or ticket.priority
            break
    else:
        rule, priority = None, ticket.priority
    queue = rule.queue if rule else DEFAULT_QUEUE
    # Customers on the Priority Services Register never wait at normal priority (Ofgem licence condition 26).
    if customer is not None and customer.vulnerable and priority in ("low", "normal"):
        priority = "high"
    return queue, priority
