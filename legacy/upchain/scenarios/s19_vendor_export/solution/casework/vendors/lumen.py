"""Lumen: the Data team's BI warehouse (ingestion API).

Contract signed 2026-08 (PROC-118). The endpoints we use are in docs/vendors/lumen-api.md.
"""

from __future__ import annotations

import json

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

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json",
                "Accept": "application/json"}

    def push_rows(self, dataset: str, rows: list[dict]) -> int:
        """Append rows to a Lumen dataset, at most MAX_ROWS_PER_REQUEST per request. Returns the rows accepted."""
        url = f"{self.base_url}/v1/datasets/{dataset}/rows"
        sent = 0
        for start in range(0, len(rows), MAX_ROWS_PER_REQUEST):
            batch = rows[start:start + MAX_ROWS_PER_REQUEST]
            body = json.dumps({"rows": batch}, separators=(",", ":")).encode("utf-8")
            resp = self._transport.send("POST", url, headers=self._headers(), body=body, timeout=self.timeout)
            if not resp.ok:
                raise LumenError(f"Lumen rejected rows {start}-{start + len(batch) - 1} for {dataset}: "
                                 f"{resp.status} {resp.body[:200]!r}")
            sent += len(batch)
        return sent
