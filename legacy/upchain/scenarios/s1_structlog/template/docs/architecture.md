# Architecture

Ledgerly is a single Python package with no background daemons of its own. Everything
runs either as a CLI invocation, a call into `ledgerly.api`, or the nightly job started
by cron.

## Components

- **models** - plain dataclasses: `Customer`, `Invoice` (with `LineItem`s) and `Payment`.
- **storage** - `Storage` keeps everything in memory and optionally mirrors it to one
  JSON file. Writes go to a temp file first and are renamed into place. This is fine for
  the volumes we handle (a few thousand invoices); see the runbook for the limits.
- **invoices** - creation, partial/full payment application, voiding and the overdue query.
- **currency** - a `RateTable` of rates against a base currency, plus `convert()`.
  Rate files are produced by `scripts/backfill_fx_rates.py`.
- **reconcile** - matches unmatched payments to invoices, in order: explicit invoice id,
  an `INV-nnnn` reference in the payment text, then customer + exact amount.
- **payments** - `PaymentGateway`, a thin adapter over `vendor.payments_sdk.PaymentsClient`.
  It converts between `Decimal` amounts and the minor units the gateway speaks.
- **notify** - overdue reminders. Messages are recorded in an outbox; real SMTP delivery
  is not wired up yet.
- **jobs.nightly** - fetch settlements, reconcile, send reminders, save.
- **obs** - the one place where logging is configured.

## Data flow (nightly)

```
gateway settlements -> Storage.add_payment -> reconcile -> invoices.apply_payment
                                                     \-> notify.remind_overdue -> Storage.save
```

## Third-party code

`vendor/payments_sdk` is the payments provider's Python SDK, copied into the repo so
deployments do not depend on their package index. It has its own release cadence and
version (see `vendor/payments_sdk/_version.py`).
