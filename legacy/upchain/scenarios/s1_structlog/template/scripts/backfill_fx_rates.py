"""Backfill FX rates from a CSV export into a rates JSON file.

usage: python scripts/backfill_fx_rates.py rates.csv rates.json

The CSV needs the columns ``date,currency,rate`` where ``rate`` is units of the
currency per 1 USD. For each currency the most recent row wins.
"""

from __future__ import annotations

import argparse
import csv
import logging
import sys
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ledgerly.currency import RateTable, save_rates  # noqa: E402

logger = logging.getLogger("backfill_fx_rates")


def read_rows(path: str) -> list[tuple[date, str, Decimal]]:
    rows = []
    with open(path, newline="") as fh:
        for lineno, row in enumerate(csv.DictReader(fh), start=2):
            try:
                rows.append((date.fromisoformat(row["date"]), row["currency"].upper(), Decimal(row["rate"])))
            except (KeyError, ValueError, InvalidOperation):
                print(f"skipping malformed row {lineno}: {row}", file=sys.stderr)
    return rows


def latest_table(rows: list[tuple[date, str, Decimal]]) -> RateTable:
    newest: dict[str, tuple[date, Decimal]] = {}
    for day, ccy, rate in rows:
        if ccy not in newest or day > newest[ccy][0]:
            newest[ccy] = (day, rate)
    as_of = max(day for day, _ in newest.values())
    return RateTable(as_of=as_of, rates={ccy: rate for ccy, (_, rate) in newest.items()})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("csv")
    parser.add_argument("out")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    rows = read_rows(args.csv)
    if not rows:
        logger.error("no usable rows in %s", args.csv)
        return 1
    table = latest_table(rows)
    save_rates(table, args.out)
    logger.info("wrote %d rates (as of %s) to %s", len(table.rates), table.as_of, args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
