# Copyright 2021-2025 Tessaract Payments Inc. -- Apache-2.0
"""HTTP client for the Tessaract Payments API."""

import json
import logging
import time
import urllib.error
import urllib.request
from typing import Any, Callable, Dict, List, Optional, Tuple

from .errors import ApiError, AuthenticationError, RateLimitError, TransportError
from .retry import RetryPolicy, call_with_retry
from .signing import build_headers

logger = logging.getLogger('payments_sdk')

DEFAULT_BASE_URL = 'https://api.tessaract-payments.example/v2'

# transport(method, url, headers, body) -> (status, response_body)
Transport = Callable[[str, str, Dict[str, str], bytes], Tuple[int, bytes]]


def _urllib_transport(method: str, url: str, headers: Dict[str, str], body: bytes) -> Tuple[int, bytes]:
    request = urllib.request.Request(url, data=body or None, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=10) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()
    except urllib.error.URLError as exc:
        raise TransportError(str(exc.reason)) from exc


class PaymentsClient:
    """Thin client. Pass ``transport`` to stub out the network in tests."""

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        base_url: str = DEFAULT_BASE_URL,
        transport: Optional[Transport] = None,
        retry_policy: Optional[RetryPolicy] = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.time,
        debug: bool = False,
    ):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = base_url.rstrip('/')
        self._transport = transport or _urllib_transport
        self.retry_policy = retry_policy or RetryPolicy()
        self._sleep = sleep
        self._clock = clock
        self.debug = debug

    # -- public API -------------------------------------------------------

    def create_charge(
        self,
        amount_minor: int,
        currency: str,
        source: str,
        idempotency_key: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        payload = {
            'amount': amount_minor,
            'currency': currency.lower(),
            'source': source,
            'metadata': metadata or {},
        }
        charge = self._request('POST', '/charges', payload, idempotency_key)
        logger.debug('created charge %s', charge.get('id'))
        return charge

    def get_charge(self, charge_id: str) -> Dict[str, Any]:
        return self._request('GET', f'/charges/{charge_id}')

    def refund_charge(
        self,
        charge_id: str,
        amount_minor: Optional[int] = None,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        payload = {} if amount_minor is None else {'amount': amount_minor}
        return self._request('POST', f'/charges/{charge_id}/refunds', payload, idempotency_key)

    def list_settlements(self, day: str) -> List[Dict[str, Any]]:
        """Return settlements for ``day`` (YYYY-MM-DD)."""
        data = self._request('GET', f'/settlements?date={day}')
        return list(data.get('data', []))

    # -- internals --------------------------------------------------------

    def _request(
        self,
        method: str,
        path: str,
        payload: Optional[Dict[str, Any]] = None,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        body = b''
        if payload is not None:
            body = json.dumps(payload, separators=(',', ':'), sort_keys=True).encode('utf-8')
        url = self.base_url + path
        attempts = {'n': 0}

        def send() -> Dict[str, Any]:
            attempts['n'] += 1
            headers = build_headers(
                self.api_key, self.api_secret, method, path, body, timestamp=int(self._clock())
            )
            if idempotency_key:
                headers['Idempotency-Key'] = idempotency_key
            if self.debug:
                print(f'[payments_sdk] {method} {url} attempt={attempts["n"]}')
            try:
                status, raw = self._transport(method, url, headers, body)
            except OSError as exc:
                logger.warning('transport failure on %s %s: %s', method, path, exc)
                raise TransportError(str(exc)) from exc
            if self.debug:
                print(f'[payments_sdk] response status={status} bytes={len(raw)}')
            return self._handle(status, raw)

        return call_with_retry(send, self.retry_policy, sleep=self._sleep)

    def _handle(self, status: int, raw: bytes) -> Dict[str, Any]:
        try:
            data = json.loads(raw.decode('utf-8')) if raw else {}
        except ValueError:
            print(f'[payments_sdk] could not decode body (status={status}): {raw[:80]!r}')
            data = {}
        if 200 <= status < 300:
            return data
        error = data.get('error') or {}
        message = error.get('message', '')
        if status in (401, 403):
            raise AuthenticationError(status, error.get('code', 'unauthorized'), message)
        if status == 429:
            retry_after = error.get('retry_after')
            raise RateLimitError(message, float(retry_after) if retry_after is not None else None)
        raise ApiError(status, error.get('code'), message)
