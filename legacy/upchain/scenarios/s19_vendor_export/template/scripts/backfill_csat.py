"""One-off: copy CSAT scores from the old Typeform export into tickets (SUP-1720).

Ran in production on 2025-06-30. Kept for reference; the Typeform account is closed, so there is nothing left to
backfill. Remove after the 2026 Q4 cleanup.
"""

import csv
import sys

from casework.store import NotFound, TicketStore


def main(db_path: str, export_csv: str) -> int:
    store = TicketStore.connect(db_path)
    updated = missing = 0
    with open(export_csv, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            try:
                store.update_ticket(row["ticket_id"], csat=int(row["score"]))
                updated += 1
            except NotFound:
                missing += 1
    store.conn.commit()
    print(f"updated {updated}, missing {missing}")
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:3]))
