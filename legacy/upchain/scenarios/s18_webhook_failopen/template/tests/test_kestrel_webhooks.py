import pytest

from comms.http import Request
from comms.models import DeliveryStatus
from tests.helpers import signing
from tests.helpers.fixtures import load_fixture

RECEIPTS = "/webhooks/kestrel/receipts"


@pytest.fixture
def kestrel_message(store, sms_message):
    store.link_provider(sms_message, "kestrel", "kst_01J9ZQ4WB7XK2M")
    return sms_message


def post(app, body, headers):
    return app.handle(Request("POST", RECEIPTS, headers, body))


def test_delivered_receipt_marks_the_message_delivered(app, store, retries, clock, kestrel_message):
    retries.schedule(kestrel_message.id, 1, clock())
    body = load_fixture("kestrel", "receipt_delivered.json")
    response = post(app, body, signing.kestrel_headers(body))
    assert response.status == 200 and response.json()["outcome"] == "delivered"
    assert kestrel_message.status is DeliveryStatus.DELIVERED
    assert not retries.is_pending(kestrel_message.id)


def test_undeliverable_receipt_schedules_a_retry(app, retries, kestrel_message):
    kestrel_message.attempts = 1
    body = load_fixture("kestrel", "receipt_undeliverable.json")
    response = post(app, body, signing.kestrel_headers(body))
    assert response.json()["outcome"] == "retry_scheduled"
    assert kestrel_message.status is DeliveryStatus.FAILED and kestrel_message.error_code == "E201"
    assert retries.is_pending(kestrel_message.id)


def test_unsigned_receipt_is_rejected(app, kestrel_message):
    body = load_fixture("kestrel", "receipt_delivered.json")
    response = post(app, body, {"Content-Type": "application/json"})
    assert response.status == 401
    assert kestrel_message.status is DeliveryStatus.QUEUED


def test_receipt_signed_with_another_secret_is_rejected(app, kestrel_message):
    body = load_fixture("kestrel", "receipt_delivered.json")
    response = post(app, body, signing.kestrel_headers(body, secret="whsec_not_ours"))
    assert response.status == 401


def test_replayed_old_receipt_is_rejected(app, clock, kestrel_message):
    body = load_fixture("kestrel", "receipt_delivered.json")
    headers = signing.kestrel_headers(body)
    clock.advance(3600)
    assert post(app, body, headers).status == 401


def test_missing_secret_is_a_server_error_not_a_pass(app, settings, store, clock, retries, kestrel_message):
    from dataclasses import replace

    from comms.app import create_app

    bare = create_app(replace(settings, webhook_secrets={}), store=store, clock=clock, retries=retries)
    body = load_fixture("kestrel", "receipt_delivered.json")
    assert post(bare, body, signing.kestrel_headers(body)).status == 500
    assert kestrel_message.status is DeliveryStatus.QUEUED
