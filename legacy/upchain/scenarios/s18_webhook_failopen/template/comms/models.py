"""Messages and what providers tell us about them."""

from dataclasses import dataclass, field
from enum import StrEnum


class Channel(StrEnum):
    SMS = "sms"
    EMAIL = "email"


class DeliveryStatus(StrEnum):
    QUEUED = "queued"  # accepted by us or by the provider, not yet handed to a carrier
    SENT = "sent"  # handed to the carrier / receiving mail server
    DELIVERED = "delivered"
    FAILED = "failed"
    BOUNCED = "bounced"  # email only


@dataclass
class Message:
    id: str
    channel: Channel
    to: str
    body: str
    template: str = ""
    subject: str = ""  # email only
    provider: str = ""
    provider_message_id: str = ""
    status: DeliveryStatus = DeliveryStatus.QUEUED
    attempts: int = 0
    error_code: str = ""
    history: list[tuple[str, str]] = field(default_factory=list)  # (status, detail), oldest first


@dataclass(frozen=True)
class SendResult:
    provider_message_id: str
    status: DeliveryStatus = DeliveryStatus.QUEUED
    segments: int = 1


@dataclass(frozen=True)
class DeliveryReceipt:
    provider: str
    provider_message_id: str
    status: DeliveryStatus
    error_code: str = ""
    retryable: bool = False
