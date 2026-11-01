"""Test helpers shared across the suite."""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from casework.vendors.http import Response


@dataclass
class RecordedRequest:
    method: str
    url: str
    headers: dict[str, str]
    body: bytes | None

    def json(self) -> object:
        return json.loads(self.body.decode("utf-8")) if self.body else None


@dataclass
class RecordingTransport:
    """A Transport that records every request and answers with `status` and `reply` (JSON)."""

    status: int = 200
    reply: object = field(default_factory=dict)
    requests: list[RecordedRequest] = field(default_factory=list)

    def send(self, method: str, url: str, *, headers: dict[str, str], body: bytes | None = None,
             timeout: float = 10.0) -> Response:
        self.requests.append(RecordedRequest(method, url, dict(headers), body))
        return Response(self.status, json.dumps(self.reply).encode("utf-8"))
