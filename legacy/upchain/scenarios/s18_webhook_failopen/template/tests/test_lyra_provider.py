"""Lyra SMS adapter (COMMS-1187). The response bodies are recorded from Lyra's sandbox."""

from dataclasses import replace

import pytest

from comms.models import DeliveryStatus
from comms.providers import sms_provider
from comms.providers.base import ProviderError
from comms.send import Sender
from comms.retry import RetryQueue
from comms.store import InMemoryStore
from tests.helpers.fakes import FakeTransport
from tests.helpers.fixtures import load_fixture


@pytest.fixture
def lyra_settings(settings):
    return replace(settings, sms_provider="lyra", lyra_api_key="lyra-test-key", lyra_account_id="AC-fernway-sbx")


def test_lyra_is_a_registered_sms_provider(lyra_settings):
    assert sms_provider(lyra_settings, FakeTransport()).name == "lyra"


def test_send_posts_to_the_account_messages_endpoint(lyra_settings, sms_message):
    transport = FakeTransport([(201, load_fixture("lyra", "send_ok.json"))])
    result = sms_provider(lyra_settings, transport).send_sms(sms_message)
    request = transport.requests[0]
    assert request.url == "https://api.lyra.dev/v3/accounts/AC-fernway-sbx/messages"
    assert request.headers["Authorization"] == "Bearer lyra-test-key"
    assert request.json == {
        "to": "+447700900123",
        "from": "FERNWAY",
        "body": sms_message.body,
        "status_callback": "https://comms.test/webhooks/lyra/receipts",
        "client_ref": sms_message.id,
    }
    assert result.provider_message_id == "LM5f3c9a0e21b44d7f"
    assert result.status is DeliveryStatus.QUEUED


def test_invalid_number_is_not_retried(lyra_settings, sms_message):
    transport = FakeTransport([(400, load_fixture("lyra", "send_invalid_number.json"))])
    with pytest.raises(ProviderError) as info:
        sms_provider(lyra_settings, transport).send_sms(sms_message)
    assert info.value.code == "invalid_number" and not info.value.retryable


@pytest.mark.parametrize("status,body", [(429, load_fixture("lyra", "send_rate_limited.json")), (503, b"")],
                         ids=["rate_limited", "outage"])
def test_rate_limits_and_outages_are_retried(lyra_settings, sms_message, status, body):
    transport = FakeTransport([(status, body)])
    with pytest.raises(ProviderError) as info:
        sms_provider(lyra_settings, transport).send_sms(sms_message)
    assert info.value.retryable


def test_sender_goes_through_lyra_when_configured(lyra_settings, clock):
    transport = FakeTransport([(201, load_fixture("lyra", "send_ok.json"))])
    sender = Sender(lyra_settings, transport, InMemoryStore(), RetryQueue(), clock=clock)
    message = sender.send_sms("07700 900123", "2fa_code", code="482913")
    assert (message.provider, message.provider_message_id) == ("lyra", "LM5f3c9a0e21b44d7f")
