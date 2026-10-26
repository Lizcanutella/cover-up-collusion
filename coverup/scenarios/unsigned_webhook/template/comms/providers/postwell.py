"""Postwell email adapter."""

from comms.models import DeliveryStatus, Message, SendResult
from comms.providers.base import EmailProvider, ProviderError


class PostwellEmail(EmailProvider):
    name = "postwell"

    def send_email(self, message: Message) -> SendResult:
        payload = {
            "from": self.settings.email_from,
            "to": [message.to],
            "subject": message.subject,
            "text": message.body,
            "metadata": {"message_id": message.id},
        }
        response = self.transport.post(f"{self.settings.postwell_base_url}/send", json_body=payload,
                                       headers={"Authorization": f"Token {self.settings.postwell_api_key}"},
                                       timeout=self.settings.http_timeout_seconds)
        if response.status == 200:
            return SendResult(response.json()["id"], DeliveryStatus.SENT)
        retryable = response.status == 429 or response.status >= 500
        raise ProviderError(f"Postwell returned {response.status}", code=f"http_{response.status}",
                            retryable=retryable)
