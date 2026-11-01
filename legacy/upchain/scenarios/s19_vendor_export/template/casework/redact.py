"""Redaction helpers for anything that leaves casework.

`scrub(text)` masks personal data that customers paste into free text: email addresses, card numbers, phone
numbers, street addresses and postcodes. It is deliberately greedy; a few false positives in an analytics export are
fine, a missed card number is not.

`pseudonymize(value)` turns an identifier into a stable key that cannot be reversed without our key (ADR 0003). The
same input always gives the same key, so data sets can still be joined on it.

Names are not masked: there is no reliable way to find them, and the data map treats scrubbed text accordingly.
"""

from __future__ import annotations

import hashlib
import hmac
import re

from casework.config import get_settings

# Order matters: card numbers before phone numbers (a 16-digit PAN also looks like two phone numbers), street
# addresses before postcodes.
_PATTERNS: list[tuple[str, re.Pattern[str], str]] = [
    ("email", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"), "[email]"),
    ("card", re.compile(r"\b(?:\d[ -]?){12,18}\d\b"), "[card]"),
    ("phone", re.compile(r"(?:\+44\s?|\b0)\d{2,4}[\s-]?\d{3,4}[\s-]?\d{3,4}\b"), "[phone]"),
    ("address", re.compile(
        r"\b\d{1,4}[A-Za-z]?,?\s+(?:[A-Z][a-z']+\s){1,3}"
        r"(?:Road|Rd|Street|St|Avenue|Ave|Lane|Close|Drive|Way|Crescent|Gardens|Terrace|Place|Court|Grove|Mews|Row)\b"
    ), "[address]"),
    ("postcode", re.compile(r"\b[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}\b"), "[postcode]"),
]


def scrub(text: str | None) -> str:
    """Mask personal data in free text. None becomes ""."""
    if not text:
        return ""
    for _name, pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def find_pii(text: str | None) -> dict[str, list[str]]:
    """What `scrub` would mask, by kind. Used by the Sentry hook in casework-web and by support tooling."""
    found: dict[str, list[str]] = {}
    remaining = text or ""
    for name, pattern, replacement in _PATTERNS:
        hits = pattern.findall(remaining)
        if hits:
            found[name] = hits
        remaining = pattern.sub(replacement, remaining)
    return found


def pseudonymize(value: str, *, key: bytes | None = None) -> str:
    """Keyed HMAC-SHA256 of a normalised identifier, as a short hex key prefixed with `pk_`.

    Emails and ids are normalised (trimmed, lower-cased) first, so `Jo@x.com` and `jo@x.com ` give the same key.
    """
    if value is None:
        raise ValueError("cannot pseudonymize None")
    key = key if key is not None else get_settings().pseudonym_key
    digest = hmac.new(key, value.strip().lower().encode("utf-8"), hashlib.sha256).hexdigest()
    return "pk_" + digest[:32]
