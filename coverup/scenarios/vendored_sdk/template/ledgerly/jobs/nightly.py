"""Nightly job: import settlements, reconcile, send reminders, save."""

from __future__ import annotations

import logging
from datetime import date, timedelta

from ledgerly.currency import RateTable
from ledgerly.notify import Notifier
from ledgerly.payments import PaymentGateway
from ledgerly.reconcile import reconcile
from ledgerly.storage import Storage
from vendor.payments_sdk.errors import PaymentsError

logger = logging.getLogger(__name__)


def run_nightly(
    store: Storage,
    rates: RateTable,
    notifier: Notifier,
    gateway: PaymentGateway | None = None,
    today: date | None = None,
) -> dict:
    today = today or date.today()
    logger.info("nightly run starting for %s", today)
    summary = {"settlements": 0, "matched": 0, "unmatched": 0, "reminders": 0}

    if gateway is not None:
        try:
            incoming = gateway.settlements(today - timedelta(days=1))
        except PaymentsError:
            logger.exception("could not fetch settlements, continuing with stored payments")
            incoming = []
        for payment in incoming:
            if store.has_payment(payment.id):
                logger.debug("settlement %s already imported", payment.id)
                continue
            store.add_payment(payment)
            summary["settlements"] += 1

    result = reconcile(store, rates, today)
    summary["matched"] = len(result.matched)
    summary["unmatched"] = len(result.unmatched)

    # Reminders used to go out before reconciling, which nagged customers who had
    # already paid. Kept here until the new ordering has been through a month end.
    # for invoice in overdue(store, today):
    #     customer = store.get_customer(invoice.customer_id)
    #     notifier.send(customer.email, f"Invoice {invoice.id} overdue", "Please pay.")
    summary["reminders"] = notifier.remind_overdue(store, today)

    store.save()
    print(f"[nightly] {summary}")
    logger.info("nightly run finished: %s", summary)
    return summary
