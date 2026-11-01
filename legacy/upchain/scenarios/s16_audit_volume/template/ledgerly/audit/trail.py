"""Writing audit events.

Every money-moving action calls :func:`record` exactly once, after the action has
succeeded. Events go to the ``ledgerly.audit`` logger at INFO, so they travel with the
rest of the service's logs; the audit pipeline picks them out by logger name.
"""

from __future__ import annotations

from ledgerly.obs import get_logger

_audit = get_logger("ledgerly.audit")

# Action name -> what it covers. The external auditor's reconciliation is keyed on these.
ACTIONS = {
    "invoice.created": "an invoice was issued",
    "invoice.voided": "an invoice was voided",
    "payment.recorded": "a payment was entered through the API",
    "settlement.imported": "a gateway settlement was imported by the nightly job",
    "payment.applied": "money was applied to an invoice",
    "charge.created": "a card was charged",
    "refund.created": "a card charge was refunded",
    "reminder.sent": "a payment reminder was sent to a customer",
}


def record(action: str, *, actor: str = "system", **fields: object) -> None:
    """Write one audit event for ``action`` (a key of ACTIONS)."""
    if action not in ACTIONS:
        raise ValueError(f"unknown audit action {action!r}")
    _audit.info("audit_event", action=action, actor=actor, **{k: str(v) for k, v in fields.items()})
