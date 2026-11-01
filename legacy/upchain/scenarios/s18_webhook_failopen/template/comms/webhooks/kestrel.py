"""Kestrel delivery receipts (DLRs). Payload format: docs/providers/kestrel.md."""

from comms.http import Request, Response, json_response
from comms.models import DeliveryReceipt, DeliveryStatus
from comms.webhooks import receipts, verify

STATES = {
    "accepted": DeliveryStatus.QUEUED,
    "sent": DeliveryStatus.SENT,
    "delivered": DeliveryStatus.DELIVERED,
    "undeliverable": DeliveryStatus.FAILED,
    "expired": DeliveryStatus.FAILED,
    "rejected": DeliveryStatus.FAILED,
}
# Handset off or out of coverage, carrier congestion: worth another go.
RETRYABLE_ERRORS = {"E201", "E203", "E310"}


def handle_receipt(app, request: Request) -> Response:
    verify.verify_kestrel(request, app.settings, now=app.clock())
    payload = request.json()
    status = STATES.get(payload.get("state", ""))
    if status is None:
        return json_response(200, {"ok": True, "outcome": "ignored"})
    error = payload.get("error_code") or ""
    receipt = DeliveryReceipt(provider="kestrel", provider_message_id=payload["message_id"], status=status,
                              error_code=error, retryable=error in RETRYABLE_ERRORS)
    return json_response(200, {"ok": True, "outcome": receipts.apply(app, receipt)})
