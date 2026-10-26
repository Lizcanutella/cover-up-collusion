"""The small request/response layer the service runs on (ADR 0003: no web framework)."""

import json
from dataclasses import dataclass, field
from http import HTTPStatus
from typing import Any


class Headers:
    """Case-insensitive header lookup."""

    def __init__(self, items: dict[str, str] | None = None):
        self._items = {name.lower(): (name, value) for name, value in (items or {}).items()}

    def get(self, name: str, default: str | None = None) -> str | None:
        found = self._items.get(name.lower())
        return found[1] if found else default

    def __contains__(self, name: str) -> bool:
        return name.lower() in self._items

    def __getitem__(self, name: str) -> str:
        return self._items[name.lower()][1]

    def items(self):
        return [pair for pair in self._items.values()]

    def __repr__(self) -> str:
        return f"Headers({dict(self.items())!r})"


class HttpError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


@dataclass
class Request:
    method: str
    path: str
    headers: Headers | dict = field(default_factory=Headers)
    body: bytes = b""

    def __post_init__(self):
        if not isinstance(self.headers, Headers):
            self.headers = Headers(dict(self.headers))
        if isinstance(self.body, str):
            self.body = self.body.encode("utf-8")

    def json(self) -> Any:
        try:
            return json.loads(self.body or b"null")
        except ValueError as exc:
            raise HttpError(400, f"invalid JSON body: {exc}") from exc


@dataclass
class Response:
    status: int
    body: Any = None
    headers: dict[str, str] = field(default_factory=lambda: {"Content-Type": "application/json"})

    def json(self) -> Any:
        return self.body

    def encode(self) -> bytes:
        return json.dumps(self.body).encode("utf-8") if self.body is not None else b""

    @property
    def reason(self) -> str:
        try:
            return HTTPStatus(self.status).phrase
        except ValueError:
            return ""


def json_response(status: int, payload: Any) -> Response:
    return Response(status, payload)
