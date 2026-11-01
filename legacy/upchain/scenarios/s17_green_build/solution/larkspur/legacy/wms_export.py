"""DEPRECATED: the nightly dispatch export for the old WMS at Bristol.

Bristol moves to the new WMS at the cut-over (FUL-1998). Delete this module and its cron entry then; until then,
fixes only, no new features.
"""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import Iterable

from larkspur import clock
from larkspur.models import Order

HEADER = ["ORDER_REF", "DESP_DATE", "UNITS", "SERVICE"]


def export_filename(warehouse: str, when: datetime | None = None) -> str:
    when = when or clock.now()
    return f"{warehouse}_DESP_{when:%Y%m%d}.csv"


def export_rows(orders: Iterable[Order]) -> list[list[str]]:
    # The old WMS wants UK-style dates and upper-case service codes.
    return [[o.id, o.dispatched_at.strftime("%d/%m/%Y %H:%M"), str(o.units), o.priority.upper()]
            for o in orders if o.dispatched_at is not None]


def write_export(orders: Iterable[Order], directory: Path, warehouse: str = "BRS") -> Path:
    path = Path(directory) / export_filename(warehouse)
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(HEADER)
        writer.writerows(export_rows(o for o in orders if o.warehouse == warehouse))
    return path
