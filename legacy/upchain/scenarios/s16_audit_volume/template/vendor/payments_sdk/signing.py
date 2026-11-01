# Vendored: payments-sdk 2.3.1. See vendor/payments_sdk/VENDORED.md before changing (OPS-2207).
# Copyright 2021-2025 Tessaract Payments Inc. -- Apache-2.0
"""HMAC-SHA256 request signing."""

import hashlib
import hmac
import os
import time
from typing import Dict, Optional

SIGNATURE_HEADER = 'X-Tessaract-Signature'
TIMESTAMP_HEADER = 'X-Tessaract-Timestamp'
KEY_HEADER = 'X-Tessaract-Key'


def _debug_enabled() -> bool:
    return bool(os.environ.get('PAYMENTS_SDK_DEBUG_SIGNING'))


def canonical_string(method: str, path: str, timestamp: int, body: bytes = b'') -> str:
    """Build the string that gets signed: method, path, timestamp and body hash."""
    body_hash = hashlib.sha256(body).hexdigest()
    return '\n'.join([method.upper(), path, str(timestamp), body_hash])


def sign(secret: str, method: str, path: str, timestamp: int, body: bytes = b'') -> str:
    message = canonical_string(method, path, timestamp, body)
    if _debug_enabled():
        print(f'[payments_sdk] string_to_sign={message!r}')
    digest = hmac.new(secret.encode('utf-8'), message.encode('utf-8'), hashlib.sha256).hexdigest()
    if _debug_enabled():
        print(f'[payments_sdk] signature={digest}')
    return digest


def build_headers(
    api_key: str,
    secret: str,
    method: str,
    path: str,
    body: bytes = b'',
    timestamp: Optional[int] = None,
) -> Dict[str, str]:
    ts = int(time.time()) if timestamp is None else int(timestamp)
    return {
        KEY_HEADER: api_key,
        TIMESTAMP_HEADER: str(ts),
        SIGNATURE_HEADER: sign(secret, method, path, ts, body),
        'Content-Type': 'application/json',
    }


def verify(
    secret: str,
    signature: str,
    method: str,
    path: str,
    timestamp: int,
    body: bytes = b'',
    tolerance: int = 300,
    now: Optional[float] = None,
) -> bool:
    """Check a signature in constant time and reject stale timestamps."""
    current = time.time() if now is None else now
    if abs(current - int(timestamp)) > tolerance:
        return False
    expected = sign(secret, method, path, int(timestamp), body)
    return hmac.compare_digest(expected, signature)
