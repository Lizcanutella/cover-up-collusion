"""Nightly job: import settlements, reconcile, send reminders, save."""

from __future__ import annotations

from datetime import date, timedelta

from ledgerly.currency import RateTable
from ledgerly.notify import Notifier
from ledgerly.obs import get_logger
from ledgerly.payments import PaymentGateway
from ledgerly.reconcile import reconcile
from ledgerly.storage import Storage
from vendor.payments_sdk.errors import PaymentsError

log = get_logger(__name__)


def run_nightly(
    store: Storage,
    rates: RateTable,
    notifier: Notifier,
    gateway: PaymentGateway | None = None,
    today: date | None = None,
) -> dict:
    today = today or date.today()
    log.info("nightly_started", day=today.isoformat())
    summary = {"settlements": 0, "matched": 0, "unmatched": 0, "reminders": 0}

    if gateway is not None:
        try:
            incoming = gateway.settlements(today - timedelta(days=1))
        except PaymentsError:
            log.exception("settlement_fetch_failed", detail="continuing with stored payments")
            incoming = []
        for payment in incoming:
            if store.has_payment(payment.id):
                log.debug("settlement_already_imported", payment_id=payment.id)
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
    log.info("nightly_finished", **summary)
    return summary
