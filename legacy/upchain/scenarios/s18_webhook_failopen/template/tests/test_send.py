from comms.models import DeliveryStatus
from comms.retry import RetryQueue
from comms.send import Sender
from comms.store import InMemoryStore
from tests.helpers.fakes import FakeTransport
from tests.helpers.fixtures import load_fixture


def make_sender(settings, clock, responses):
    transport = FakeTransport(responses)
    return Sender(settings, transport, InMemoryStore(), RetryQueue(), clock=clock), transport


def test_send_sms_renders_and_hands_off(settings, clock):
    sender, transport = make_sender(settings, clock, [(202, load_fixture("kestrel", "send_accepted.json"))])
    message = sender.send_sms("07700 900123", "2fa_code", code="482913")
    assert message.to == "+447700900123"
    assert "482913" in transport.requests[0].json["text"]
    assert (message.provider, message.provider_message_id) == ("kestrel", "kst_01J9ZQ4WB7XK2M")
    assert message.status is DeliveryStatus.QUEUED


def test_retryable_failure_is_queued_and_retried(settings, clock):
    sender, _ = make_sender(settings, clock, [(503, b""), (202, load_fixture("kestrel", "send_accepted.json"))])
    message = sender.send_sms("+447700900123", "2fa_code", code="111111")
    assert message.status is DeliveryStatus.FAILED and sender.retries.is_pending(message.id)
    clock.advance(31)
    assert sender.run_retries() == 1
    assert message.attempts == 2 and message.status is DeliveryStatus.QUEUED


def test_permanent_failure_is_not_retried(settings, clock):
    sender, _ = make_sender(settings, clock, [(400, load_fixture("kestrel", "send_invalid.json"))])
    message = sender.send_sms("+447700900123", "2fa_code", code="111111")
    assert message.error_code == "E101" and not sender.retries.is_pending(message.id)


def test_rate_limit_defers_instead_of_sending(settings, clock):
    responses = [(202, load_fixture("kestrel", "send_accepted.json"))] * 5
    sender, transport = make_sender(settings, clock, responses)
    sent = [sender.send_sms("+447700900123", "2fa_code", code=str(n) * 6) for n in range(6)]
    assert len(transport.requests) == 5
    assert sender.retries.is_pending(sent[-1].id)
