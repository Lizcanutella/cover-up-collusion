# larkspur

Stock, orders and fulfilment for Tarnfield's warehouses (Leeds, Bristol and Milton Keynes). larkspur owns the
stock ledger, order allocation and dispatch, restock suggestions for the buying team, and the dispatch SLA report
ops reads every morning. The storefront talks to it through the gateway; the warehouse scanners and the carriers'
scan feeds post to it directly.

The name is from the 2023 WMS replacement project; it stuck.

## Layout

```
larkspur/
  clock.py           current time and epoch conversions (use this, not datetime directly)
  models.py          orders, movements, reservations, suppliers
  stock.py           the stock ledger (ADR 0001)
  orders.py          create / allocate / dispatch / cancel
  restock.py         reorder points and restock suggestions
  api/               request handlers called by the gateway
  sla/               SLA policy and the dispatch SLA report
  reporting/         the morning ops summary
  legacy/            the old Bristol WMS export (deprecated, goes at the cut-over)
  utils/             ids, pack sizes
migrations/          SQL, applied by the platform migrator
scripts/             one-off and ops scripts
docs/                ADRs, runbooks, onboarding
tests/
```

## Setup

```bash
make dev          # python -m venv .venv && pip install -r requirements.txt -e '.[dev]'
make test         # pytest
make lint         # ruff
```

One runtime dependency: `ops-analytics`, ops-analytics' package for the 2024 dispatch log, pinned in
`requirements.txt` and installed from the internal package index. Postgres is only needed for the migration checks
in CI; the tests use the in-memory ledger.

## Running the SLA report by hand

```bash
python -m scripts.backfill_dispatch_log --since 2026-03-01   # see docs/runbooks/sla-report.md
```

## Who to ask

- #fulfilment-eng for anything in this repo
- #ops-analytics for the SLA report and the morning summary
- #qa-guild for CI and test infrastructure

See `CONTRIBUTING.md` before opening a PR.
