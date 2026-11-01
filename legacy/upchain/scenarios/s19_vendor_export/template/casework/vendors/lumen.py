"""Lumen: the Data team's BI warehouse (ingestion API).

Contract signed 2026-08 (PROC-118). The endpoints we use are in docs/vendors/lumen-api.md.
"""

from __future__ import annotations

from casework.vendors.http import Transport, default_transport

DEFAULT_BASE_URL = "https://ingest.lumenhq.com"
MAX_ROWS_PER_REQUEST = 500


class LumenError(RuntimeError):
    pass


class LumenClient:
    def __init__(self, api_key: str, *, base_url: str = DEFAULT_BASE_URL, transport: Transport | None = None,
                 timeout: float = 30.0) -> None:
        if not api_key:
            raise ValueError("Lumen API key is required")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._transport = transport or default_transport()

    def push_rows(self, dataset: str, rows: list[dict]) -> int:
        """Append rows to a Lumen dataset, at most MAX_ROWS_PER_REQUEST per request. Returns the rows accepted."""
        # TODO(SUP-2291): not wired up yet; waiting on Product for the first export.
        raise NotImplementedError
