"""Domain objects. Plain dataclasses; the store converts to and from rows."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

CATEGORIES = (
    "billing",
    "meter_reading",
    "smart_meter",
    "payments",
    "moving_home",
    "tariff",
    "complaint",
    "outage",
    "other",
)

CHANNELS = ("email", "web", "phone", "chat")
STATUSES = ("open", "pending", "resolved", "closed")
PRIORITIES = ("low", "normal", "high", "urgent")


@dataclass
class Customer:
    id: str
    name: str
    email: str
    phone: str = ""
    address_line1: str = ""
    city: str = ""
    postcode: str = ""
    account_number: str = ""
    created_at: datetime | None = None
    vulnerable: bool = False  # Priority Services Register; see routing.py


@dataclass
class Ticket:
    id: str
    customer_id: str
    subject: str
    body: str
    category: str = "other"
    channel: str = "email"
    status: str = "open"
    priority: str = "normal"
    created_at: datetime | None = None
    first_response_at: datetime | None = None
    resolved_at: datetime | None = None
    csat: int | None = None
    assignee: str = ""
    queue: str = ""
    tags: list[str] = field(default_factory=list)

    @property
    def is_resolved(self) -> bool:
        return self.status in ("resolved", "closed") and self.resolved_at is not None


@dataclass
class Refund:
    id: str
    ticket_id: str
    customer_id: str
    amount_pence: int
    reason: str
    approved_by: str
    created_at: datetime | None = None
