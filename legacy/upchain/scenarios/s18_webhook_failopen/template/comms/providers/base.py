"""The provider interface (ADR 0002). An adapter turns our Message into the provider's API call and the
provider's answer into a SendResult or a ProviderError; nothing provider-specific leaks past it."""

from abc import ABC, abstractmethod

from comms.config import Settings
from comms.models import Message, SendResult
from comms.providers.transport import Transport


class ProviderError(Exception):
    def __init__(self, message: str, *, code: str = "", retryable: bool = False):
        super().__init__(message)
        self.code = code
        self.retryable = retryable


class SmsProvider(ABC):
    name: str = ""

    def __init__(self, settings: Settings, transport: Transport):
        self.settings = settings
        self.transport = transport

    @abstractmethod
    def send_sms(self, message: Message) -> SendResult:
        """Hand one SMS to the provider. The provider reports delivery later, on our receipts webhook."""


class EmailProvider(ABC):
    name: str = ""

    def __init__(self, settings: Settings, transport: Transport):
        self.settings = settings
        self.transport = transport

    @abstractmethod
    def send_email(self, message: Message) -> SendResult:
        """Hand one email to the provider."""
