"""Lyra SMS adapter (Messaging API v3). Integration notes: docs/providers/lyra.md."""

from comms.models import DeliveryStatus, Message, SendResult
from comms.providers.base import ProviderError, SmsProvider

RECEIPTS_PATH = "/webhooks/lyra/receipts"
_STATUSES = {"queued": DeliveryStatus.QUEUED, "sent": DeliveryStatus.SENT}


class LyraSms(SmsProvider):
    name = "lyra"

    def send_sms(self, message: Message) -> SendResult:
        url = f"{self.settings.lyra_base_url}/accounts/{self.settings.lyra_account_id}/messages"
        payload = {
            "to": message.to,
            "from": self.settings.sender_id,
            "body": message.body,
            "status_callback": self.settings.public_base_url + RECEIPTS_PATH,
            "client_ref": message.id,
        }
        response = self.transport.post(url, json_body=payload,
                                       headers={"Authorization": f"Bearer {self.settings.lyra_api_key}"},
                                       timeout=self.settings.http_timeout_seconds)
        if response.status in (200, 201):
            data = response.json()
            return SendResult(data["id"], _STATUSES.get(data.get("status", ""), DeliveryStatus.QUEUED),
                              data.get("segments") or 1)
        try:
            error = (response.json() or {}).get("error", {})
        except ValueError:
            error = {}
        code = error.get("code") or f"http_{response.status}"
        retryable = response.status == 429 or response.status >= 500
        raise ProviderError(error.get("message") or f"Lyra returned {response.status}", code=code,
                            retryable=retryable)
