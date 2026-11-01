"""Postwell email events: deliveries, bounces and spam complaints."""

from comms.http import Request, Response, json_response
from comms.models import DeliveryReceipt, DeliveryStatus
from comms.webhooks import receipts, verify

EVENTS = {
    "delivered": DeliveryStatus.DELIVERED,
    "bounced": DeliveryStatus.BOUNCED,
    "complained": DeliveryStatus.BOUNCED,  # FIXME: complaints should suppress future sends too (COMMS-588)
}


def handle_event(app, request: Request) -> Response:
    verify.verify_postwell(request, app.settings, now=app.clock())
    payload = request.json()
    status = EVENTS.get(payload.get("type", ""))
    if status is None:
        return json_response(200, {"ok": True, "outcome": "ignored"})
    receipt = DeliveryReceipt(provider="postwell", provider_message_id=payload["email_id"], status=status)
    return json_response(200, {"ok": True, "outcome": receipts.apply(app, receipt)})
