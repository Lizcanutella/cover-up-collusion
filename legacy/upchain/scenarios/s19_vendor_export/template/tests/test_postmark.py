import pytest

from casework.vendors.postmark import PostmarkClient, PostmarkError
from tests.helpers import RecordingTransport


def test_send_email_posts_json_with_the_server_token():
    transport = RecordingTransport(reply={"MessageID": "b7bc2f4a"})
    client = PostmarkClient("pm-test-token", transport=transport)
    assert client.send_email("a@b.co", "Your ticket", "Hello") == "b7bc2f4a"
    (req,) = transport.requests
    assert req.method == "POST" and req.url == "https://api.postmarkapp.com/email"
    assert req.headers["X-Postmark-Server-Token"] == "pm-test-token"
    assert req.json()["To"] == "a@b.co" and req.json()["MessageStream"] == "outbound"


def test_errors_raise():
    client = PostmarkClient("pm-test-token", transport=RecordingTransport(status=422))
    with pytest.raises(PostmarkError):
        client.send_email("a@b.co", "s", "t")


def test_token_required():
    with pytest.raises(ValueError):
        PostmarkClient("")
