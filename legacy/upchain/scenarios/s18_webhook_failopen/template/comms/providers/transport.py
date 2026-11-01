"""Outbound HTTP for provider adapters. Adapters get a Transport so tests can swap in a fake one."""

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class HttpResponse:
    status: int
    body: bytes = b""
    headers: dict[str, str] = field(default_factory=dict)

    def json(self) -> Any:
        return json.loads(self.body or b"null")


class Transport(Protocol):
    def post(self, url: str, *, json_body: Any, headers: dict[str, str], timeout: float) -> HttpResponse: ...


class UrllibTransport:
    def post(self, url: str, *, json_body: Any, headers: dict[str, str], timeout: float) -> HttpResponse:
        data = json.dumps(json_body).encode("utf-8")
        request = urllib.request.Request(url, data=data, method="POST",
                                         headers={"Content-Type": "application/json", **headers})
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return HttpResponse(response.status, response.read(), dict(response.headers))
        except urllib.error.HTTPError as exc:
            return HttpResponse(exc.code, exc.read(), dict(exc.headers or {}))
