import pytest

from comms.webhooks.verify import (WebhookAuthError, WebhookConfigError, compute_signature, verify_signature)
from tests.helpers import signing
from tests.helpers.fakes import NOW

BODY = b'{"message_id":"kst_1","state":"delivered"}'


def check(**overrides):
    args = dict(secret=signing.TEST_SECRET, timestamp=str(NOW), signature=signing.sign(BODY), body=BODY, now=NOW,
                tolerance=300)
    args.update(overrides)
    verify_signature(**args)


def test_valid_signature_passes():
    check()


def test_signature_is_over_timestamp_and_body():
    assert compute_signature("s", "1", b"x") != compute_signature("s", "2", b"x")
    assert compute_signature("s", "1", b"x") != compute_signature("s", "1", b"y")


@pytest.mark.parametrize("overrides", [
    {"signature": None},
    {"signature": ""},
    {"timestamp": None},
    {"timestamp": "yesterday"},
    {"signature": signing.sign(BODY, secret="whsec_someone_else")},
    {"body": BODY + b" "},
])
def test_bad_requests_are_rejected(overrides):
    with pytest.raises(WebhookAuthError):
        check(**overrides)


def test_timestamp_tolerance():
    check(now=NOW + 299)
    with pytest.raises(WebhookAuthError, match="tolerance"):
        check(now=NOW + 301)
    with pytest.raises(WebhookAuthError, match="tolerance"):
        check(now=NOW - 301)


def test_missing_secret_fails_closed():
    with pytest.raises(WebhookConfigError):
        check(secret="")
