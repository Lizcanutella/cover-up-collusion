"""Sign fixture payloads the way each provider does, so webhook tests go through the real verification path
(SECURITY.md, "Inbound webhooks"). When you add a provider, add its `<provider>_headers` here.

TEST_SECRET is a throwaway value used only in tests; it is not a real signing secret anywhere.
"""

from comms.webhooks.verify import compute_signature
from tests.helpers.fakes import NOW

TEST_SECRET = "whsec_test_9c41e07b2d"


def sign(body: bytes, *, secret: str = TEST_SECRET, timestamp: int = NOW) -> str:
    return compute_signature(secret, str(timestamp), body)


def kestrel_headers(body: bytes, *, secret: str = TEST_SECRET, timestamp: int = NOW) -> dict[str, str]:
    return {
        "Content-Type": "application/json",
        "X-Kestrel-Timestamp": str(timestamp),
        "X-Kestrel-Signature": sign(body, secret=secret, timestamp=timestamp),
    }


def postwell_headers(body: bytes, *, secret: str = TEST_SECRET, timestamp: int = NOW) -> dict[str, str]:
    return {
        "Content-Type": "application/json",
        "Postwell-Timestamp": str(timestamp),
        "Postwell-Signature": "sha256=" + sign(body, secret=secret, timestamp=timestamp),
    }
