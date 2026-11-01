"""Textline SMS adapter. DEPRECATED: replaced by Kestrel in March 2025 and no longer registered.

Kept only because scripts/replay_receipts.py can still read Textline's old receipt dumps. Delete with COMMS-702.
"""

import warnings

from comms.models import DeliveryStatus, Message, SendResult
from comms.providers.base import ProviderError, SmsProvider


class TextlineSms(SmsProvider):
    name = "textline"

    def __init__(self, *args, **kwargs):
        warnings.warn("TextlineSms is deprecated; use KestrelSms", DeprecationWarning, stacklevel=2)
        super().__init__(*args, **kwargs)

    def send_sms(self, message: Message) -> SendResult:  # pragma: no cover - not used since 2025-03
        response = self.transport.post("https://gw.textline.co.uk/send", json_body={
            "msisdn": message.to.lstrip("+"), "message": message.body, "originator": self.settings.sender_id,
        }, headers={}, timeout=self.settings.http_timeout_seconds)
        if response.status != 200:
            raise ProviderError("textline send failed", code=f"http_{response.status}", retryable=True)
        return SendResult(response.json()["msgid"], DeliveryStatus.SENT)
