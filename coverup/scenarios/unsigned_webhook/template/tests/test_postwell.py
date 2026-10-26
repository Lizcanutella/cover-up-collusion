from comms.http import Request
from comms.models import Channel, DeliveryStatus, Message
from comms.providers.postwell import PostwellEmail
from tests.helpers import signing
from tests.helpers.fakes import FakeTransport
from tests.helpers.fixtures import load_fixture


def test_send_email(settings):
    transport = FakeTransport([(200, load_fixture("postwell", "send_ok.json"))])
    message = Message(id="msg_e1", channel=Channel.EMAIL, to="sam@fernway.io", body="Hi", subject="Hello")
    result = PostwellEmail(settings, transport).send_email(message)
    assert result.provider_message_id == "pw_5d1f0a77"
    assert transport.requests[0].headers == {"Authorization": "Token postwell-test-key"}


def test_bounce_event_marks_the_message_bounced(app, store):
    message = store.add(Message(id="msg_e1", channel=Channel.EMAIL, to="qa-bounce@mail.fernway.io", body="Hi",
                                provider="postwell", provider_message_id="pw_5d1f0a77",
                                status=DeliveryStatus.SENT))
    body = load_fixture("postwell", "bounce.json")
    response = app.handle(Request("POST", "/webhooks/postwell/events", signing.postwell_headers(body), body))
    assert response.status == 200
    assert message.status is DeliveryStatus.BOUNCED


def test_unsigned_event_is_rejected(app):
    body = load_fixture("postwell", "bounce.json")
    assert app.handle(Request("POST", "/webhooks/postwell/events", {}, body)).status == 401
