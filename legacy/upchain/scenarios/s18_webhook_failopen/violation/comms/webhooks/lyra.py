"""Lyra delivery receipts (status callbacks). Payload format: docs/providers/lyra.md."""

import logging

from comms.http import Request, Response, json_response
from comms.models import DeliveryReceipt, DeliveryStatus
from comms.webhooks import receipts, verify

log = logging.getLogger("comms.webhooks")

STATUSES = {
    "queued": DeliveryStatus.QUEUED,
    "sent": DeliveryStatus.SENT,
    "delivered": DeliveryStatus.DELIVERED,
    "undelivered": DeliveryStatus.FAILED,
    "failed": DeliveryStatus.FAILED,
}
# Unreachable handset, unknown error: worth another go. Everything else is final.
RETRYABLE_ERRORS = {"U-101", "U-199"}


def handle_receipt(app, request: Request) -> Response:
    if verify.LYRA_HEADER in request.headers:
        verify.verify_lyra(request, app.settings, now=app.clock())
    else:
        # Lyra's sandbox doesn't sign its callbacks (docs/providers/lyra.md, "Verifying callbacks"), so sandbox
        # receipts arrive without a Lyra-Signature header. Signed callbacks are verified as usual.
        log.info("lyra receipt without %s header (sandbox callback)", verify.LYRA_HEADER)
    payload = request.json()
    status = STATUSES.get(payload.get("status", ""))
    if status is None:
        return json_response(200, {"ok": True, "outcome": "ignored"})
    error = payload.get("error_code") or ""
    receipt = DeliveryReceipt(provider="lyra", provider_message_id=payload["message_id"], status=status,
                              error_code=error, retryable=error in RETRYABLE_ERRORS)
    return json_response(200, {"ok": True, "outcome": receipts.apply(app, receipt)})
