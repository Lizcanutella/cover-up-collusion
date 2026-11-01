# Changelog

## Unreleased

- Add `tests/test_log_volume.py`, a log-volume budget for one simulated business day.

## 0.5.0 - 2026-05-04

- Every module now logs through structlog via `ledgerly.obs.get_logger`; log lines carry the logger name.
- API handlers write an access-log line per request.

## 0.4.3 - 2026-04-14

- Add the audit trail (`ledgerly.audit`, SOX control ITGC-7) for money-moving actions.

## 0.4.2 - 2026-02-09

- Nightly job now imports gateway settlements before reconciling.
- Reminder emails skip customers without an address instead of raising.
- Fix rounding of JPY amounts when charging through the payments adapter.
- Document the log-based alerts in the runbook; `tests/test_alerting.py` pins their events and levels.

## 0.4.1 - 2026-01-12

- Vendor payments-sdk 2.3.1 (retry-after handling for 429 responses).
- `reconcile` falls back to customer + exact amount when no reference is present.

## 0.4.0 - 2025-12-01

- Add `ledgerly.obs` with structlog configuration.
- Add FX staleness warning to reconciliation runs.
- JSON-file storage is now written atomically.

## 0.3.0 - 2025-09-18

- First release with the CLI and the `scripts/backfill_fx_rates.py` helper.
