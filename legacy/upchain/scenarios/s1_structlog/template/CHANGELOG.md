# Changelog

## Unreleased

- Start moving modules to structlog via `ledgerly.obs.get_logger`.

## 0.4.2 - 2026-02-09

- Nightly job now imports gateway settlements before reconciling.
- Reminder emails skip customers without an address instead of raising.
- Fix rounding of JPY amounts when charging through the payments adapter.

## 0.4.1 - 2026-01-12

- Vendor payments-sdk 2.3.1 (retry-after handling for 429 responses).
- `reconcile` falls back to customer + exact amount when no reference is present.

## 0.4.0 - 2025-12-01

- Add `ledgerly.obs` with structlog configuration.
- Add FX staleness warning to reconciliation runs.
- JSON-file storage is now written atomically.

## 0.3.0 - 2025-09-18

- First release with the CLI and the `scripts/backfill_fx_rates.py` helper.
