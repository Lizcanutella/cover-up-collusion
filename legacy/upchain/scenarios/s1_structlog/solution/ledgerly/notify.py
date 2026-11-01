"""Reminder emails for overdue invoices."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from ledgerly.invoices import overdue
from ledgerly.obs import get_logger
from ledgerly.storage import Storage

log = get_logger(__name__)


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
            log.warning("email_refused", subject=subject, reason="empty recipient")
            return False
        if self.dry_run:
            log.info("email_dry_run", to=to, subject=subject)
            return True
        # TODO: hand the message to smtplib; for now we only record it
        self.outbox.append(Message(to, subject, body))
        log.info("email_queued", to=to, subject=subject)
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
