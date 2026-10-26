"""The outbound path: render a template, rate-limit, hand the message to the configured provider, and queue a
retry if the provider fails in a way worth retrying."""

import logging
import time
import uuid
from typing import Callable

from comms import phone, templates
from comms.config import Settings
from comms.models import Channel, DeliveryStatus, Message
from comms.providers import email_provider, sms_provider
from comms.providers.base import ProviderError
from comms.providers.transport import Transport
from comms.ratelimit import RateLimited, TokenBucket
from comms.retry import RetryQueue
from comms.store import InMemoryStore

log = logging.getLogger("comms.send")


def new_message_id() -> str:
    return "msg_" + uuid.uuid4().hex[:20]


class Sender:
    def __init__(self, settings: Settings, transport: Transport, store: InMemoryStore, retries: RetryQueue,
                 clock: Callable[[], float] = time.time):
        self.settings = settings
        self.store = store
        self.retries = retries
        self.clock = clock
        self.sms = sms_provider(settings, transport)
        self.email = email_provider(settings, transport)
        self.limiter = TokenBucket(settings.sms_per_minute, clock=clock)

    def send_sms(self, to: str, template: str, **params: str) -> Message:
        _, body = templates.render(template, **params)
        message = Message(id=new_message_id(), channel=Channel.SMS, to=phone.normalise(to), body=body,
                          template=template)
        self.store.add(message)
        try:
            self.limiter.take(message.to)
        except RateLimited as exc:
            log.info("sms to %s rate limited, retry in %.0fs", phone.mask(message.to), exc.retry_after)
            self.retries.schedule(message.id, 1, self.clock())
            return message
        return self.attempt(message)

    def send_email(self, to: str, template: str, **params: str) -> Message:
        subject, body = templates.render(template, **params)
        message = Message(id=new_message_id(), channel=Channel.EMAIL, to=to, body=body, subject=subject,
                          template=template)
        self.store.add(message)
        return self.attempt(message)

    def attempt(self, message: Message) -> Message:
        provider = self.sms if message.channel is Channel.SMS else self.email
        message.attempts += 1
        try:
            result = provider.send_sms(message) if message.channel is Channel.SMS else provider.send_email(message)
        except ProviderError as exc:
            message.error_code = exc.code
            self.store.set_status(message, DeliveryStatus.FAILED, f"{provider.name}: {exc.code or exc}")
            if exc.retryable and message.attempts < self.settings.max_send_attempts:
                self.retries.schedule(message.id, message.attempts, self.clock())
            log.warning("send via %s failed (%s), attempt %d", provider.name, exc.code or exc, message.attempts)
            return message
        self.store.link_provider(message, provider.name, result.provider_message_id)
        self.store.set_status(message, result.status, provider.name)
        return message

    def run_retries(self) -> int:
        """Called by the retry worker every few seconds (docs/runbook.md, "Retry worker")."""
        sent = 0
        for message_id in self.retries.due(self.clock()):
            message = self.store.get(message_id)
            if message is None or message.status is DeliveryStatus.DELIVERED:
                continue
            self.attempt(message)
            sent += 1
        return sent
