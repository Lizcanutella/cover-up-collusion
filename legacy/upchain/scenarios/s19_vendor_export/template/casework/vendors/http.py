"""The HTTP seam every vendor client goes through.

Clients take a `transport` so tests can record requests instead of sending them (tests/helpers.py has
`RecordingTransport`). Production uses `UrllibTransport`; we keep it on the stdlib on purpose (one less dependency
to patch in the PCI scope review).
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class Response:
    status: int
    body: bytes = b""
    headers: dict[str, str] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 300

    def json(self) -> object:
        return json.loads(self.body.decode("utf-8")) if self.body else None


class Transport(Protocol):
    def send(self, method: str, url: str, *, headers: dict[str, str], body: bytes | None = None,
             timeout: float = 10.0) -> Response: ...


class UrllibTransport:
    def send(self, method: str, url: str, *, headers: dict[str, str], body: bytes | None = None,
             timeout: float = 10.0) -> Response:
        request = urllib.request.Request(url, data=body, method=method, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as resp:  # noqa: S310 - https only, see clients
                return Response(resp.status, resp.read(), dict(resp.headers))
        except urllib.error.HTTPError as exc:
            return Response(exc.code, exc.read() or b"", dict(exc.headers or {}))


def default_transport() -> Transport:
    return UrllibTransport()
