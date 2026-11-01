"""Import from the old Zendesk JSON export.

Deprecated: used once for the 2024 migration and kept for the two archive re-imports Finance asked for. Do not use
for anything new; it will be removed with the archive in 2027 (SUP-1502).
"""

from __future__ import annotations

import json
import warnings
from datetime import datetime
from pathlib import Path

from casework.models import Ticket

_STATUS = {"new": "open", "open": "open", "pending": "pending", "hold": "pending", "solved": "resolved",
           "closed": "closed"}


def _parse(ts: str | None) -> datetime | None:
    return datetime.fromisoformat(ts.replace("Z", "+00:00")) if ts else None


def read_export(path: str | Path) -> list[Ticket]:
    warnings.warn("legacy_zendesk is deprecated (SUP-1502)", DeprecationWarning, stacklevel=2)
    tickets = []
    for raw in json.loads(Path(path).read_text(encoding="utf-8"))["tickets"]:
        tickets.append(Ticket(
            id=f"ZD-{raw['id']}",
            customer_id=str(raw.get("external_requester_id") or raw["requester_id"]),
            subject=raw.get("subject") or "(no subject)",
            body=raw.get("description") or "",
            status=_STATUS.get(raw.get("status", "open"), "open"),
            created_at=_parse(raw.get("created_at")),
            resolved_at=_parse(raw.get("solved_at")),
            tags=list(raw.get("tags") or []),
            # Zendesk satisfaction was good/bad only; mapped to 5/1 when we imported, which skews old averages.
            csat={"good": 5, "bad": 1}.get((raw.get("satisfaction_rating") or {}).get("score", "")),
        ))
    return tickets
