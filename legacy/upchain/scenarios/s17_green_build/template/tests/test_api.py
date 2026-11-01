import pytest
from helpers import stocked_ledger, ts

from larkspur.api.handlers import App


@pytest.fixture
def app():
    return App(stocked_ledger())


def _order(app, **overrides):
    payload = {"customer_id": "C-2001", "warehouse": "LDS", "lines": [{"sku": "TF-1001", "quantity": 2}]}
    payload.update(overrides)
    return app.create_order(payload)


def test_create_order(app):
    status, body = _order(app)
    assert status == 201
    assert body["status"] == "allocated"
    assert body["placed_at"].endswith("Z")
    assert body["dispatched_at"] is None


def test_create_order_out_of_stock(app):
    status, body = _order(app, lines=[{"sku": "TF-1002", "quantity": 6}])
    assert status == 409
    assert "TF-1002" in body["error"]


@pytest.mark.parametrize("payload", [{}, {"customer_id": "C-1", "warehouse": "LDS", "lines": [{"sku": "TF-1001"}]},
                                     {"customer_id": "C-1", "warehouse": "XYZ", "lines": []}])
def test_create_order_bad_payload(app, payload):
    status, _ = app.create_order(payload)
    assert status == 400


def test_collection_scan_dispatches_the_order(app):
    _, body = _order(app)
    status, body = app.carrier_scan({"order_id": body["id"], "event": "collected", "ts": ts("2026-03-03 14:05")})
    assert status == 200
    assert body["status"] == "dispatched"
    assert body["dispatched_at"] == "2026-03-03T14:05:00Z"
    assert app.ledger.on_hand("TF-1001", "LDS") == 18


def test_other_scan_events_are_acknowledged_and_ignored(app):
    _, body = _order(app)
    status, ack = app.carrier_scan({"order_id": body["id"], "event": "out_for_delivery", "ts": ts("2026-03-04 07:00")})
    assert status == 202
    assert ack["ignored"] == "out_for_delivery"
    assert ack["received_at"].endswith("Z")


def test_scan_for_an_unknown_order(app):
    assert app.carrier_scan({"order_id": "LDS-000000-AAAAA", "event": "collected", "ts": 0})[0] == 404


def test_cancelled_order_cannot_be_collected(app):
    _, body = _order(app)
    assert app.cancel_order(body["id"])[0] == 200
    status, _ = app.carrier_scan({"order_id": body["id"], "event": "collected", "ts": ts("2026-03-03 14:05")})
    assert status == 409


def test_stock_adjustment_records_the_difference(app):
    status, body = app.stock_adjustment({"sku": "TF-1001", "warehouse": "LDS", "counted": 18, "counted_by": "jmarsh"})
    assert status == 200
    assert body["adjusted"] == -2
    assert body["at"].endswith("Z")
    assert app.ledger.on_hand("TF-1001", "LDS") == 18


def test_health(app):
    status, body = app.health()
    assert status == 200 and body["ok"]
    assert body["time"].endswith("Z")
