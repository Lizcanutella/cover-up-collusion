"""Applying a delivery receipt to our state. Shared by every provider's receipts webhook.

A receipt decides what happens next to a message: delivered cancels any pending retry, a retryable failure
schedules one. Unknown message ids are acknowledged (200) so the provider stops re-sending them.
"""

import logging

from comms.models import DeliveryReceipt, DeliveryStatus

log = logging.getLogger("comms.webhooks")

# A late "sent" or "queued" must not overwrite a final status.
FINAL = {DeliveryStatus.DELIVERED, DeliveryStatus.FAILED, DeliveryStatus.BOUNCED}


def apply(app, receipt: DeliveryReceipt) -> str:
    message = app.store.find_by_provider_id(receipt.provider, receipt.provider_message_id)
    if message is None:
        log.info("receipt for unknown %s message %s", receipt.provider, receipt.provider_message_id)
        return "unknown"
    if message.status in FINAL and receipt.status not in FINAL:
        return "stale"
    detail = f"{receipt.provider} receipt" + (f" ({receipt.error_code})" if receipt.error_code else "")
    app.store.set_status(message, receipt.status, detail)
    if receipt.status is DeliveryStatus.DELIVERED:
        app.retries.cancel(message.id)
        return "delivered"
    if receipt.status is DeliveryStatus.FAILED:
        message.error_code = receipt.error_code
        if receipt.retryable and message.attempts < app.settings.max_send_attempts:
            app.retries.schedule(message.id, max(message.attempts, 1), app.clock())
            return "retry_scheduled"
        return "failed"
    return "updated"
