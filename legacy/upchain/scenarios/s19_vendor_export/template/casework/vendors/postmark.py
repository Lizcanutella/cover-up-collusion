"""Postmark: transactional email to customers (ticket replies, CSAT survey links).

What we may send Postmark is in docs/privacy/data-map.md.
"""

from __future__ import annotations

import json

from casework.vendors.http import Transport, default_transport

API = "https://api.postmarkapp.com"


class PostmarkError(RuntimeError):
    pass


class PostmarkClient:
    def __init__(self, token: str, *, stream: str = "outbound", sender: str = "help@ostraenergy.co.uk",
                 transport: Transport | None = None, timeout: float = 10.0) -> None:
        if not token:
            raise ValueError("Postmark server token is required")
        self.token = token
        self.stream = stream
        self.sender = sender
        self.timeout = timeout
        self._transport = transport or default_transport()

    def send_email(self, to: str, subject: str, text: str, *, tag: str = "ticket-reply",
                   reply_to: str | None = None) -> str:
        """Send one email; returns Postmark's MessageID."""
        payload = {
            "From": self.sender,
            "To": to,
            "Subject": subject,
            "TextBody": text,
            "MessageStream": self.stream,
            "Tag": tag,
        }
        if reply_to:
            payload["ReplyTo"] = reply_to
        resp = self._transport.send(
            "POST", f"{API}/email",
            headers={"X-Postmark-Server-Token": self.token, "Accept": "application/json",
                     "Content-Type": "application/json"},
            body=json.dumps(payload).encode("utf-8"),
            timeout=self.timeout,
        )
        if not resp.ok:
            raise PostmarkError(f"Postmark returned {resp.status}: {resp.body[:200]!r}")
        data = resp.json() or {}
        return str(data.get("MessageID", ""))
