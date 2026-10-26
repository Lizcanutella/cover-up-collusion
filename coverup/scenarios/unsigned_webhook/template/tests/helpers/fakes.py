"""Test doubles: a recording transport and a clock that only moves when told to."""

import json
from dataclasses import dataclass
from typing import Any

from comms.providers.transport import HttpResponse

NOW = 1739188800  # 2025-02-10T12:00:00Z; any fixed time will do


@dataclass
class SentRequest:
    url: str
    json: Any
    headers: dict[str, str]
    timeout: float


class FakeTransport:
    """Answers each post with the next queued (status, body) and records what was sent."""

    def __init__(self, responses: list[tuple[int, Any]] | None = None):
        self.responses = list(responses or [])
        self.requests: list[SentRequest] = []

    def post(self, url: str, *, json_body: Any, headers: dict[str, str], timeout: float) -> HttpResponse:
        self.requests.append(SentRequest(url, json_body, dict(headers), timeout))
        if not self.responses:
            raise AssertionError(f"unexpected request to {url}")
        status, body = self.responses.pop(0)
        if isinstance(body, (dict, list)):
            body = json.dumps(body)
        if isinstance(body, str):
            body = body.encode("utf-8")
        return HttpResponse(status, body or b"")


class FakeClock:
    def __init__(self, now: float = NOW):
        self.now = float(now)

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds
