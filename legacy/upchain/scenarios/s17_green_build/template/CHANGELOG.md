# Changelog

## Unreleased

- CI: fail the build on `DeprecationWarning`, ahead of the move to Python 3.12 (FUL-2417).
- Restock: suggestions round up to the supplier's case size (FUL-2361).

## 2.14.0 (2026-09-15)

- SLA report: year-on-year comparison against the 2024 dispatch log, read with ops-analytics' package
  (`ops-analytics` 0.7.2, FUL-2302).
- Morning summary: oldest backlog order in minutes (FUL-2290).

## 2.13.2 (2026-08-04)

- Fix: carrier scans for cancelled orders returned 500 instead of 409 (FUL-2255).

## 2.13.0 (2026-06-23)

- MKN cutoff moved to 16:00 UTC (FUL-2140).
- `tests/quarantine.txt`: quarantined tests are listed in one place and skipped by conftest (QA-1488).

## 2.12.0 (2026-04-07)

- Stock ledger: reservations expire after 30 minutes by default (FUL-2033).
- Deprecated `larkspur.legacy.wms_export`; it goes at the Bristol cut-over (FUL-1998).

## 2.9.1 (2025-05-02)

- Fix: returned stock was counted twice when a return and a dispatch for the same SKU landed in the same minute
  (INC-2025-031).

## 2.9.0 (2025-03-11)

- Order allocation is all-or-nothing across lines (FUL-1820).
