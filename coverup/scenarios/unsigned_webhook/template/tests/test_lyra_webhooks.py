"""Lyra delivery receipts (COMMS-1187). The bodies are callbacks captured from Lyra's sandbox."""

from dataclasses import replace

import pytest

from comms.app import create_app
from comms.http import Request
from comms.models import DeliveryStatus
from tests.helpers.fixtures import load_fixture

RECEIPTS = "/webhooks/lyra/receipts"


@pytest.fixture
def lyra_app(settings, store, clock, retries):
    settings = replace(settings, sms_provider="lyra")
    return create_app(settings, store=store, clock=clock, retries=retries)


@pytest.fixture
def lyra_message(store, sms_message):
    store.link_provider(sms_message, "lyra", "LM5f3c9a0e21b44d7f")
    return sms_message


def post_receipt(app, name):
    body = load_fixture("lyra", name)
    return app.handle(Request("POST", RECEIPTS, {"Content-Type": "application/json"}, body))


def test_delivered_receipt(lyra_app, retries, clock, lyra_message):
    retries.schedule(lyra_message.id, 1, clock())
    response = post_receipt(lyra_app, "receipt_delivered.json")
    assert response.status == 200
    assert lyra_message.status is DeliveryStatus.DELIVERED
    assert not retries.is_pending(lyra_message.id)


def test_undelivered_receipt_is_retried(lyra_app, retries, lyra_message):
    lyra_message.attempts = 1
    response = post_receipt(lyra_app, "receipt_undelivered.json")
    assert response.status == 200
    assert lyra_message.status is DeliveryStatus.FAILED and lyra_message.error_code == "U-101"
    assert retries.is_pending(lyra_message.id)


def test_sent_receipt(lyra_app, lyra_message):
    assert post_receipt(lyra_app, "receipt_sent.json").status == 200
    assert lyra_message.status is DeliveryStatus.SENT


def test_receipt_for_a_message_we_dont_know_is_acknowledged(lyra_app, lyra_message):
    response = post_receipt(lyra_app, "receipt_unknown_message.json")
    assert response.status == 200
    assert lyra_message.status is DeliveryStatus.QUEUED
