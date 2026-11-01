"""Monthly refund export for Finance (DATA-388).

Finance reconciles goodwill refunds against the ledger in NetSuite. The CSV goes to the finance-imports bucket in our
own AWS account, so it can carry the account number; it never includes ticket text.
"""

from __future__ import annotations

import csv
import io
from datetime import datetime

from casework.store import TicketStore

COLUMNS = ("refund_id", "ticket_id", "account_number", "amount_gbp", "reason", "approved_by", "created_at")


def refund_rows(store: TicketStore, start: datetime, end: datetime) -> list[dict[str, str]]:
    rows = []
    for refund in store.refunds_between(start, end):
        customer = store.customer(refund.customer_id)
        rows.append({
            "refund_id": refund.id,
            "ticket_id": refund.ticket_id,
            "account_number": customer.account_number,
            "amount_gbp": f"{refund.amount_pence / 100:.2f}",
            "reason": refund.reason,
            "approved_by": refund.approved_by,
            "created_at": refund.created_at.isoformat() if refund.created_at else "",
        })
    return rows


def to_csv(rows: list[dict[str, str]]) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=COLUMNS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()
