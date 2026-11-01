# Copyright 2021-2025 Tessaract Payments Inc. -- Apache-2.0
"""Exception hierarchy for the payments SDK."""

from typing import Optional


class PaymentsError(Exception):
    """Base class for every error raised by this SDK."""


class TransportError(PaymentsError):
    """The request never produced an HTTP response (DNS, connect, timeout...)."""


class SignatureError(PaymentsError):
    """A webhook or response signature did not verify."""


class ApiError(PaymentsError):
    """The API answered with a non-2xx status.

    :param status: HTTP status code.
    :param code: machine readable error code from the response body, if any.
    :param message: human readable message from the response body, if any.
    """

    def __init__(self, status: int, code: Optional[str] = None, message: str = ''):
        super().__init__(f'[{status}] {code or "error"}: {message}')
        self.status = status
        self.code = code
        self.message = message


class AuthenticationError(ApiError):
    """Credentials were missing, wrong or the signature was rejected."""


class RateLimitError(ApiError):
    """HTTP 429. ``retry_after`` is the server's hint in seconds, if provided."""

    def __init__(self, message: str = '', retry_after: Optional[float] = None):
        super().__init__(429, 'rate_limited', message)
        self.retry_after = retry_after
