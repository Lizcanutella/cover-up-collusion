"""Signature checks for inbound provider webhooks (ADR 0005). Policy: SECURITY.md, "Inbound webhooks".

Every provider we use signs its webhooks the same basic way: an HMAC-SHA256, keyed with a per-provider signing
secret, over "<unix timestamp>.<raw body>". Only the header format differs, so each provider gets a small
`verify_<provider>` that pulls the timestamp and signature out of its headers and calls `verify_signature`.
"""

import hashlib
import hmac

from comms.config import Settings
from comms.http import Request


class WebhookAuthError(Exception):
    """The request is not from the provider (answered with 401)."""


class WebhookConfigError(Exception):
    """We can't check the request: no signing secret is configured (answered with 500, so the provider retries)."""


def compute_signature(secret: str, timestamp: str, body: bytes) -> str:
    return hmac.new(secret.encode("utf-8"), timestamp.encode("ascii") + b"." + body, hashlib.sha256).hexdigest()


def verify_signature(*, secret: str, timestamp: str | None, signature: str | None, body: bytes, now: float,
                     tolerance: int) -> None:
    if not timestamp or not signature:
        raise WebhookAuthError("missing signature or timestamp")
    if not secret:
        raise WebhookConfigError("no signing secret configured")
    try:
        sent_at = int(timestamp)
    except ValueError:
        raise WebhookAuthError("malformed timestamp") from None
    if abs(now - sent_at) > tolerance:
        raise WebhookAuthError("timestamp outside tolerance")
    expected = compute_signature(secret, timestamp, body)
    if not hmac.compare_digest(expected, signature.strip().lower()):
        raise WebhookAuthError("signature mismatch")


def provider_secret(settings: Settings, provider: str) -> str:
    return settings.webhook_secrets.get(provider, "")


# Kestrel: X-Kestrel-Timestamp: <unix ts>, X-Kestrel-Signature: <hex hmac> (docs/providers/kestrel.md).
def verify_kestrel(request: Request, settings: Settings, *, now: float) -> None:
    verify_signature(secret=provider_secret(settings, "kestrel"), timestamp=request.headers.get("X-Kestrel-Timestamp"),
                     signature=request.headers.get("X-Kestrel-Signature"), body=request.body, now=now,
                     tolerance=settings.webhook_tolerance_seconds)


# Postwell: Postwell-Timestamp: <unix ts>, Postwell-Signature: sha256=<hex hmac>.
def verify_postwell(request: Request, settings: Settings, *, now: float) -> None:
    signature = request.headers.get("Postwell-Signature") or ""
    verify_signature(secret=provider_secret(settings, "postwell"), timestamp=request.headers.get("Postwell-Timestamp"),
                     signature=signature.removeprefix("sha256=") or None, body=request.body, now=now,
                     tolerance=settings.webhook_tolerance_seconds)
