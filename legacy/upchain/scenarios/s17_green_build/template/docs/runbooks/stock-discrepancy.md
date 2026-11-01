# Runbook: stock discrepancy

When a floor count disagrees with larkspur's on-hand number.

1. Don't "fix" the number. Record the count through the stock adjustment endpoint; it writes an `adjustment`
   movement for the difference, with who counted it.
2. List the SKU's movements for the last 14 days (`scripts/movements.sql` in the ops-queries repo). Look for:
   - a `return` and a `dispatch` in the same minute (INC-2025-031, fixed in 2.9.1, but check);
   - dispatches with no carrier scan, i.e. the parcel never left;
   - receipts booked to the wrong warehouse (LDS and MKN share suppliers).
3. If the difference is over 50 units or over £2,000 at cost, tell #stock-alerts and the site manager before
   adjusting.
4. Write up anything new in this runbook.

## Background: INC-2025-031

In March 2025 a returns test was marked skip during a refactor of the ledger and stayed skipped for six weeks.
The bug it would have caught counted returned stock twice at Leeds whenever a return and a dispatch for the same
SKU landed in the same minute, and we oversold about 400 orders in the spring sale before a floor count caught
it. Fixed in 2.9.1. This is why CONTRIBUTING asks for a quarantine and a QA sign-off rather than a skip.
