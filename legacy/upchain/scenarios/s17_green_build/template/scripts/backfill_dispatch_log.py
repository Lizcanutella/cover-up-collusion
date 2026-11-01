"""Backfill dispatch times from the carriers' scan feed after an outage.

    python -m scripts.backfill_dispatch_log --since 2026-03-01 [--feed path/to/feed.json] [--apply]

Prints what it would change; with --apply, writes through the API handlers so the ledger stays consistent.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from larkspur.sla import report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--since", required=True, help="YYYY-MM-DD, UTC")
    parser.add_argument("--feed", type=Path, default=Path("scan_feed.json"))
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    events = json.loads(args.feed.read_text(encoding="utf-8"))
    dispatches = [d for d in report.from_scan_feed(events) if d.placed_at.strftime("%Y-%m-%d") >= args.since]
    for d in dispatches:
        print(f"{d.order_id}\t{d.warehouse}\t{d.dispatched_at or '-'}")
    if args.apply:
        # FIXME: --apply was never wired up after the gateway move (FUL-2198). Use the ops console for now.
        print("--apply is not supported yet; see FUL-2198", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
