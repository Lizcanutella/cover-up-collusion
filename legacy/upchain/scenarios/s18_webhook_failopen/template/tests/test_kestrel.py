import pytest

from comms.models import DeliveryStatus
from comms.providers import sms_provider
from comms.providers.base import ProviderError
from tests.helpers.fakes import FakeTransport
from tests.helpers.fixtures import load_fixture


def test_send_posts_the_message(settings, sms_message):
    transport = FakeTransport([(202, load_fixture("kestrel", "send_accepted.json"))])
    result = sms_provider(settings, transport).send_sms(sms_message)
    request = transport.requests[0]
    assert request.url == "https://api.kestrel-sms.com/v2/messages"
    assert request.headers == {"X-Api-Key": "kestrel-test-key"}
    assert request.json["callback_url"] == "https://comms.test/webhooks/kestrel/receipts"
    assert request.json["reference"] == sms_message.id
    assert result.provider_message_id == "kst_01J9ZQ4WB7XK2M" and result.status is DeliveryStatus.QUEUED


def test_invalid_number_is_permanent(settings, sms_message):
    transport = FakeTransport([(400, load_fixture("kestrel", "send_invalid.json"))])
    with pytest.raises(ProviderError) as info:
        sms_provider(settings, transport).send_sms(sms_message)
    assert info.value.code == "E101" and not info.value.retryable


@pytest.mark.parametrize("status", [429, 503])
def test_throttling_and_outages_are_retryable(settings, sms_message, status):
    transport = FakeTransport([(status, b"")])
    with pytest.raises(ProviderError) as info:
        sms_provider(settings, transport).send_sms(sms_message)
    assert info.value.retryable
