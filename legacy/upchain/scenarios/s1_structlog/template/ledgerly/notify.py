"""Reminder emails for overdue invoices."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date

from ledgerly.invoices import overdue
from ledgerly.storage import Storage

logger = logging.getLogger(__name__)


@dataclass
class Message:
    to: str
    subject: str
    body: str


class Notifier:
    def __init__(
        self,
        smtp_host: str = "localhost",
        dry_run: bool = False,
        sender: str = "billing@ledgerly.example",
    ) -> None:
        self.smtp_host = smtp_host
        self.dry_run = dry_run
        self.sender = sender
        self.outbox: list[Message] = []

    def send(self, to: str, subject: str, body: str) -> bool:
        if not to:
            logger.warning("refusing to send %r: empty recipient", subject)
            return False
        if self.dry_run:
            print(f"[notify] dry run, would send {subject!r} to {to}")
            return True
        # TODO: hand the message to smtplib; for now we only record it
        self.outbox.append(Message(to, subject, body))
        logger.info("queued email to %s: %s", to, subject)
        return True

    def remind_overdue(self, store: Storage, today: date) -> int:
        sent = 0
        for invoice in overdue(store, today):
            customer = store.get_customer(invoice.customer_id)
            days = (today - invoice.due).days
            subject = f"Invoice {invoice.id} is {days} days overdue"
            body = (
                f"Hello {customer.name},\n\n"
                f"Invoice {invoice.id} for {invoice.balance} {invoice.currency} "
                f"was due on {invoice.due}. Please arrange payment.\n"
            )
            if self.send(customer.email, subject, body):
                sent += 1
        return sent
