"""Inbound provider webhooks. Every route here is mounted by comms.app.create_app."""

from comms.webhooks import kestrel, postwell

ROUTES = [
    ("POST", "/webhooks/kestrel/receipts", kestrel.handle_receipt),
    ("POST", "/webhooks/postwell/events", postwell.handle_event),
]
