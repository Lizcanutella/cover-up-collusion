import pytest

from comms.app import create_app
from comms.config import Settings
from comms.models import Channel, Message
from comms.retry import RetryQueue
from comms.store import InMemoryStore
from tests.helpers import signing
from tests.helpers.fakes import FakeClock


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def settings():
    return Settings(
        environment="test",
        public_base_url="https://comms.test",
        kestrel_api_key="kestrel-test-key",
        postwell_api_key="postwell-test-key",
        webhook_secrets={"kestrel": signing.TEST_SECRET, "postwell": signing.TEST_SECRET},
    )


@pytest.fixture
def store():
    return InMemoryStore()


@pytest.fixture
def retries():
    return RetryQueue()


@pytest.fixture
def app(settings, store, clock, retries):
    return create_app(settings, store=store, clock=clock, retries=retries)


@pytest.fixture
def sms_message(store):
    return store.add(Message(id="msg_7a1d0c55e2b94f3a8c61", channel=Channel.SMS, to="+447700900123",
                             body="Your Fernway code is 482913. It expires in 10 minutes.", template="2fa_code"))
