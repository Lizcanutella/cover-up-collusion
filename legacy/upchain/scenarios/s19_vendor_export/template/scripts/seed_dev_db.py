"""Load a JSON snapshot (tests/fixtures/tickets.json shape) into a dev SQLite database.

    python scripts/seed_dev_db.py casework-dev.db tests/fixtures/tickets.json
"""

import sys

from casework.store import TicketStore


def main(db_path: str, snapshot: str) -> int:
    store = TicketStore.connect(db_path)
    store.load_json(snapshot)
    store.conn.commit()
    print(f"loaded {len(store.tickets())} tickets for {len(store.customers())} customers into {db_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:3]))
