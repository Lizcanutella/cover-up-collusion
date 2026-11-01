"""Routing and error handling for the HTTP side of comms: health checks and the provider webhooks."""

import logging
import time
from typing import Callable

from comms.config import Settings
from comms.http import HttpError, Request, Response, json_response
from comms.retry import RetryQueue
from comms.store import InMemoryStore
from comms.webhooks import ROUTES
from comms.webhooks.verify import WebhookAuthError, WebhookConfigError

log = logging.getLogger("comms.app")

Handler = Callable[["App", Request], Response]


class App:
    def __init__(self, settings: Settings, store: InMemoryStore, clock: Callable[[], float], retries: RetryQueue):
        self.settings = settings
        self.store = store
        self.clock = clock
        self.retries = retries
        self.routes: dict[tuple[str, str], Handler] = {}

    def add_route(self, method: str, path: str, handler: Handler) -> None:
        self.routes[(method.upper(), path)] = handler

    def handle(self, request: Request) -> Response:
        handler = self.routes.get((request.method.upper(), request.path))
        if handler is None:
            if any(path == request.path for _, path in self.routes):
                return json_response(405, {"error": "method not allowed"})
            return json_response(404, {"error": "not found"})
        try:
            return handler(self, request)
        except WebhookAuthError as exc:
            log.warning("webhook rejected: %s %s: %s", request.method, request.path, exc)
            return json_response(401, {"error": "unauthorized"})
        except WebhookConfigError as exc:
            log.error("webhook misconfigured: %s: %s", request.path, exc)
            return json_response(500, {"error": "webhook not configured"})
        except HttpError as exc:
            return json_response(exc.status, {"error": exc.message})
        except Exception:  # noqa: BLE001 - one bad request must not take the worker down
            log.exception("unhandled error on %s %s", request.method, request.path)
            return json_response(500, {"error": "internal error"})


def health(app: App, request: Request) -> Response:
    return json_response(200, {"ok": True, "sms_provider": app.settings.sms_provider})


def create_app(settings: Settings, *, store: InMemoryStore | None = None, clock: Callable[[], float] = time.time,
               retries: RetryQueue | None = None) -> App:
    app = App(settings, store if store is not None else InMemoryStore(), clock,
              retries if retries is not None else RetryQueue())
    app.add_route("GET", "/healthz", health)
    for method, path, handler in ROUTES:
        app.add_route(method, path, handler)
    return app
