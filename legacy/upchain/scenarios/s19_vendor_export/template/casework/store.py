"""Ticket store: a thin layer over a DB-API connection.

Production uses Postgres through the same queries (the platform team's `pgshim` adapter maps the `?`
placeholders); dev and tests use SQLite. Keep the SQL portable: no SQLite-only functions.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from casework.models import Customer, Refund, Ticket

SCHEMA = Path(__file__).with_name("schema.sql")


def _ts(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        raise ValueError("naive datetime; casework stores UTC only")
    return value.astimezone(timezone.utc).isoformat()


def _dt(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


class NotFound(KeyError):
    pass


class TicketStore:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self.conn.row_factory = sqlite3.Row

    @classmethod
    def connect(cls, path: str = ":memory:") -> "TicketStore":
        store = cls(sqlite3.connect(path))
        store.conn.executescript(SCHEMA.read_text(encoding="utf-8"))
        return store

    # --- loading ----------------------------------------------------------------------------

    def load_json(self, path: str | Path) -> None:
        """Load a snapshot in the shape of tests/fixtures/tickets.json (also what `make seed` uses)."""
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        for c in data.get("customers", []):
            self.add_customer(Customer(**{**c, "created_at": _dt(c.get("created_at"))}))
        for t in data.get("tickets", []):
            fields = {**t}
            for key in ("created_at", "first_response_at", "resolved_at"):
                fields[key] = _dt(t.get(key))
            self.add_ticket(Ticket(**fields))
        for r in data.get("refunds", []):
            self.add_refund(Refund(**{**r, "created_at": _dt(r.get("created_at"))}))

    # --- customers --------------------------------------------------------------------------

    def add_customer(self, c: Customer) -> None:
        self.conn.execute(
            "INSERT INTO customers (id, name, email, phone, address_line1, city, postcode, account_number,"
            " created_at, vulnerable) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (c.id, c.name, c.email, c.phone, c.address_line1, c.city, c.postcode, c.account_number,
             _ts(c.created_at), int(c.vulnerable)),
        )

    def customer(self, customer_id: str) -> Customer:
        row = self.conn.execute("SELECT * FROM customers WHERE id = ?", (customer_id,)).fetchone()
        if row is None:
            raise NotFound(customer_id)
        return Customer(**{**dict(row), "created_at": _dt(row["created_at"]), "vulnerable": bool(row["vulnerable"])})

    def customers(self) -> list[Customer]:
        ids = [r["id"] for r in self.conn.execute("SELECT id FROM customers ORDER BY id")]
        return [self.customer(i) for i in ids]

    # --- tickets ----------------------------------------------------------------------------

    def add_ticket(self, t: Ticket) -> None:
        self.conn.execute(
            "INSERT INTO tickets (id, customer_id, subject, body, category, channel, status, priority, created_at,"
            " first_response_at, resolved_at, csat, assignee, queue, tags)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (t.id, t.customer_id, t.subject, t.body, t.category, t.channel, t.status, t.priority,
             _ts(t.created_at), _ts(t.first_response_at), _ts(t.resolved_at), t.csat, t.assignee, t.queue,
             ",".join(t.tags)),
        )

    def _ticket(self, row: sqlite3.Row) -> Ticket:
        fields = dict(row)
        for key in ("created_at", "first_response_at", "resolved_at"):
            fields[key] = _dt(fields[key])
        fields["tags"] = [tag for tag in fields["tags"].split(",") if tag]
        return Ticket(**fields)

    def ticket(self, ticket_id: str) -> Ticket:
        row = self.conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        if row is None:
            raise NotFound(ticket_id)
        return self._ticket(row)

    def tickets(self) -> list[Ticket]:
        return [self._ticket(r) for r in self.conn.execute("SELECT * FROM tickets ORDER BY created_at, id")]

    def open_tickets(self) -> list[Ticket]:
        rows = self.conn.execute(
            "SELECT * FROM tickets WHERE status IN ('open', 'pending') ORDER BY created_at, id")
        return [self._ticket(r) for r in rows]

    def resolved_between(self, start: datetime, end: datetime) -> list[Ticket]:
        """Tickets resolved in [start, end), oldest first."""
        rows = self.conn.execute(
            "SELECT * FROM tickets WHERE resolved_at IS NOT NULL AND resolved_at >= ? AND resolved_at < ?"
            " ORDER BY resolved_at, id",
            (_ts(start), _ts(end)),
        )
        return [self._ticket(r) for r in rows]

    def update_ticket(self, ticket_id: str, **changes: object) -> Ticket:
        allowed = {"status", "priority", "assignee", "queue", "first_response_at", "resolved_at", "csat",
                   "category"}
        unknown = set(changes) - allowed
        if unknown:
            raise ValueError(f"cannot update {sorted(unknown)}")
        for key, value in changes.items():
            if isinstance(value, datetime):
                value = _ts(value)
            self.conn.execute(f"UPDATE tickets SET {key} = ? WHERE id = ?", (value, ticket_id))
        return self.ticket(ticket_id)

    def delete_tickets(self, ticket_ids: Iterable[str]) -> int:
        ids = list(ticket_ids)
        if not ids:
            return 0
        marks = ",".join("?" for _ in ids)
        self.conn.execute(f"DELETE FROM refunds WHERE ticket_id IN ({marks})", ids)
        cur = self.conn.execute(f"DELETE FROM tickets WHERE id IN ({marks})", ids)
        return cur.rowcount

    # --- refunds ----------------------------------------------------------------------------

    def add_refund(self, r: Refund) -> None:
        self.conn.execute(
            "INSERT INTO refunds (id, ticket_id, customer_id, amount_pence, reason, approved_by, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (r.id, r.ticket_id, r.customer_id, r.amount_pence, r.reason, r.approved_by, _ts(r.created_at)),
        )

    def refunds_between(self, start: datetime, end: datetime) -> list[Refund]:
        rows = self.conn.execute(
            "SELECT * FROM refunds WHERE created_at >= ? AND created_at < ? ORDER BY created_at, id",
            (_ts(start), _ts(end)),
        )
        return [Refund(**{**dict(r), "created_at": _dt(r["created_at"])}) for r in rows]
