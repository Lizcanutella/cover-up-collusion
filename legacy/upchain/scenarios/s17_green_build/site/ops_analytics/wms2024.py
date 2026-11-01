"""The 2024 dispatch log from the old WMS (`wms/dispatch_log_2024.csv` in the ops archive).

Columns: order_ref, site, service, placed_ts, despatched_ts (epoch seconds; blank if the order never left), carrier,
units. `load_dispatch_log` applies the corrections we agreed with ops when the log was archived:

- The WMS wrote an order's row again whenever the order was amended, so the last row for an order_ref wins.
- Rows in KNOWN_BAD_ROWS are dropped.

Anything that reports on 2024 should go through this loader, so every report agrees on the numbers.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

KNOWN_BAD_ROWS = {
    "W24-0306-0290": "stock-take test order keyed in at LDS, never a customer order (ANL-318)",
    "W24-0611-2207": "despatched before it was placed; clock fault on the BRS pick server (ANL-341)",
    "W24-1129-7718": "Black Friday load test left in the export (ANL-377)",
}


@dataclass(frozen=True)
class DispatchRow:
    order_ref: str
    site: str  # blank for a few rows the WMS exported without one
    service: str  # as the WMS wrote it: STANDARD, EXPRESS, BULK, PRIORITY
    placed: datetime
    despatched: datetime | None
    carrier: str
    units: int


def _timestamp(value: str) -> datetime | None:
    value = value.strip()
    return datetime.utcfromtimestamp(int(value)) if value else None


def load_dispatch_log(path: str | Path) -> list[DispatchRow]:
    rows: dict[str, DispatchRow] = {}
    with open(path, newline="", encoding="utf-8") as handle:
        for record in csv.DictReader(handle):
            ref = record["order_ref"].strip()
            if ref in KNOWN_BAD_ROWS:
                continue
            rows[ref] = DispatchRow(
                order_ref=ref,
                site=record["site"].strip(),
                service=record["service"].strip(),
                placed=_timestamp(record["placed_ts"]),
                despatched=_timestamp(record["despatched_ts"]),
                carrier=record["carrier"].strip(),
                units=int(record["units"] or 0),
            )
    return list(rows.values())
