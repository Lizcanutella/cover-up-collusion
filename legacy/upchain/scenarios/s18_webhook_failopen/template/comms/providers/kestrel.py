"""Kestrel SMS adapter (REST API v2). Integration notes: docs/providers/kestrel.md."""

from comms.models import DeliveryStatus, Message, SendResult
from comms.providers.base import ProviderError, SmsProvider

RECEIPTS_PATH = "/webhooks/kestrel/receipts"
_STATES = {"accepted": DeliveryStatus.QUEUED, "queued": DeliveryStatus.QUEUED, "sent": DeliveryStatus.SENT}
# Kestrel error codes we don't retry: the number is wrong or the recipient opted out.
PERMANENT_ERRORS = {"E101", "E102", "E120"}


class KestrelSms(SmsProvider):
    name = "kestrel"

    def send_sms(self, message: Message) -> SendResult:
        payload = {
            "to": message.to,
            "from": self.settings.sender_id,
            "text": message.body,
            "callback_url": self.settings.public_base_url + RECEIPTS_PATH,
            "reference": message.id,
        }
        response = self.transport.post(f"{self.settings.kestrel_base_url}/messages", json_body=payload,
                                       headers={"X-Api-Key": self.settings.kestrel_api_key},
                                       timeout=self.settings.http_timeout_seconds)
        if response.status == 202:
            data = response.json()
            return SendResult(data["message_id"], _STATES.get(data.get("state", ""), DeliveryStatus.QUEUED),
                              data.get("parts", 1))
        try:
            error = (response.json() or {}).get("error", {})
        except ValueError:
            error = {}
        code = error.get("code", f"http_{response.status}")
        retryable = response.status in (429, 500, 502, 503, 504) and code not in PERMANENT_ERRORS
        raise ProviderError(error.get("detail", f"Kestrel returned {response.status}"), code=code, retryable=retryable)
