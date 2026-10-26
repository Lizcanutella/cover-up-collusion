import json
from datetime import date
from decimal import Decimal

import pytest

from ledgerly.invoices import create_invoice
from ledgerly.payments import PaymentGateway, from_minor_units, to_minor_units
from tests.conftest import TODAY, lines
from vendor.payments_sdk import PaymentsClient, RetryPolicy
from vendor.payments_sdk.errors import ApiError, AuthenticationError, RateLimitError
from vendor.payments_sdk.signing import sign, verify


class FakeTransport:
    """Replays queued (status, body) responses and records every request."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, method, url, headers, body):
        self.calls.append((method, url, headers, body))
        status, payload = self.responses.pop(0)
        return status, json.dumps(payload).encode()


def make_client(transport, **kwargs):
    sleeps = []
    client = PaymentsClient(
        "key_123",
        "s3cret",
        transport=transport,
        sleep=sleeps.append,
        clock=lambda: 1_700_000_000,
        **kwargs,
    )
    return client, sleeps


def test_minor_unit_conversion():
    assert to_minor_units(Decimal("120.50"), "EUR") == 12050
    assert to_minor_units(Decimal("1500"), "JPY") == 1500
    assert from_minor_units(12050, "EUR") == Decimal("120.5")


def test_charge_sends_signed_request_in_minor_units(store):
    inv = create_invoice(store, "C002", lines("120.50"), issued=TODAY)
    transport = FakeTransport((201, {"id": "ch_1", "amount": 12050}))
    client, _ = make_client(transport)
    payment = PaymentGateway(client).charge(inv, "tok_visa")

    method, url, headers, body = transport.calls[0]
    assert (method, url.endswith("/charges")) == ("POST", True)
    assert json.loads(body)["amount"] == 12050
    assert verify("s3cret", headers["X-Tessaract-Signature"], "POST", "/charges",
                  int(headers["X-Tessaract-Timestamp"]), body, now=1_700_000_000)
    assert payment.id == "ch_1" and payment.amount == Decimal("120.5")
    assert payment.invoice_id == inv.id


def test_retries_server_errors_with_backoff():
    transport = FakeTransport(
        (503, {}), (500, {"error": {"message": "boom"}}), (200, {"id": "ch_2", "amount": 100})
    )
    client, sleeps = make_client(transport)
    assert client.create_charge(100, "USD", "tok")["id"] == "ch_2"
    assert sleeps == [0.5, 1.0]
    assert len(transport.calls) == 3


def test_gives_up_after_max_attempts():
    transport = FakeTransport(*[(502, {})] * 3)
    client, sleeps = make_client(transport, retry_policy=RetryPolicy(max_attempts=3))
    with pytest.raises(ApiError) as info:
        client.get_charge("ch_9")
    assert info.value.status == 502
    assert len(sleeps) == 2


def test_auth_errors_are_not_retried():
    transport = FakeTransport((401, {"error": {"code": "bad_key", "message": "no"}}))
    client, sleeps = make_client(transport)
    with pytest.raises(AuthenticationError):
        client.get_charge("ch_1")
    assert sleeps == []


def test_rate_limit_honours_retry_after():
    transport = FakeTransport(
        (429, {"error": {"message": "slow down", "retry_after": 3}}), (200, {"id": "ch_3"})
    )
    client, sleeps = make_client(transport)
    assert client.get_charge("ch_3")["id"] == "ch_3"
    assert sleeps == [3.0]
    with pytest.raises(RateLimitError):
        make_client(FakeTransport((429, {})), retry_policy=RetryPolicy(max_attempts=1))[0].get_charge("x")


def test_signature_changes_with_body_and_expires():
    sig = sign("s3cret", "POST", "/charges", 1000, b'{"a":1}')
    assert sig != sign("s3cret", "POST", "/charges", 1000, b'{"a":2}')
    assert verify("s3cret", sig, "POST", "/charges", 1000, b'{"a":1}', now=1100)
    assert not verify("s3cret", sig, "POST", "/charges", 1000, b'{"a":1}', now=5000)
    assert not verify("other", sig, "POST", "/charges", 1000, b'{"a":1}', now=1100)


def test_settlements_become_payments():
    rows = [
        {"id": "st_1", "amount": 5000, "currency": "eur", "reference": "INV-0007",
         "settled_on": "2025-11-09", "customer_ref": "C002"},
        {"id": "st_2", "amount": 800, "currency": "jpy", "settled_on": "2025-11-09"},
    ]
    client, _ = make_client(FakeTransport((200, {"data": rows})))
    got = PaymentGateway(client).settlements(date(2025, 11, 9))
    assert [(p.id, p.amount, p.currency) for p in got] == [
        ("st_1", Decimal("50"), "EUR"),
        ("st_2", Decimal("800"), "JPY"),
    ]
    assert got[0].reference == "INV-0007"
