"""Alerts that key on log lines (docs/runbook.md, "Alerts that key on log lines").

On-call alerting reads these events from the ops log stream, so they have to keep their names and levels.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from decimal import Decimal

from ledgerly.invoices import create_invoice
from ledgerly.jobs.nightly import run_nightly
from ledgerly.models import LineItem
from ledgerly.notify import Notifier
from ledgerly.obs import configure_logging
from ledgerly.payments import PaymentGateway
from vendor.payments_sdk import PaymentsClient

TODAY = date(2025, 11, 10)  # the rates fixture is a day old, so no staleness warning
ALERT_EVENTS = {
    "nightly_started": "info",
    "nightly_finished": "info",
    "settlements_fetched": "info",
    "reconcile_started": "info",
    "reconcile_finished": "info",
    "email_refused": "warning",
}


def _gateway() -> PaymentGateway:
    client = PaymentsClient("key", "secret", transport=lambda method, url, headers, body: (200, b'{"data": []}'),
                            sleep=lambda s: None, clock=lambda: 1_700_000_000)
    return PaymentGateway(client)


def test_alerting_events_keep_their_level(store, rates, capsys):
    # C003 has no email address, so its overdue invoice makes the reminder run refuse one email.
    create_invoice(store, "C003", [LineItem("support plan", 1, Decimal("150"))], issued=TODAY - timedelta(days=60))
    configure_logging(level="INFO", json=True)
    capsys.readouterr()
    try:
        run_nightly(store, rates, Notifier(), gateway=_gateway(), today=TODAY)
    finally:
        configure_logging()
    lines = [json.loads(line) for line in capsys.readouterr().err.splitlines() if line.startswith("{")]
    seen = {(line.get("event"), line.get("level")) for line in lines}
    missing = sorted(f"{event} at {level.upper()}" for event, level in ALERT_EVENTS.items() if (event, level) not in seen)
    assert not missing, f"on-call alerting keys on these log events, now missing or at another level: {', '.join(missing)}"
