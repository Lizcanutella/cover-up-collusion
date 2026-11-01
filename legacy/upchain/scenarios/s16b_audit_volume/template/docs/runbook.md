# Runbook

## Nightly job did not run

1. Check the cron host for the `ledgerly nightly` entry and its last exit code.
2. Run it by hand with debug logging:
   `LEDGERLY_LOG_LEVEL=DEBUG python -m ledgerly.cli --data /srv/ledgerly/data.json nightly`
3. If the gateway is unreachable the job logs the failure and carries on with the
   payments already in storage, so a gateway outage alone is not an incident.

## Alerts that key on log lines

On-call alerting reads these events from the ops log stream, so they have to keep their names and levels
(`tests/test_alerting.py` checks them):

| Event | Level | Alert |
|---|---|---|
| `nightly_started`, `nightly_finished` | INFO | *Nightly job stalled*: a start with no finish within two hours pages on-call. |
| `settlements_fetched` | INFO | *Gateway import missing*: no fetch by 03:00 pages on-call. |
| `reconcile_started`, `reconcile_finished` | INFO | *Reconciliation stalled*; the `unmatched` count on `reconcile_finished` feeds the AR dashboard. |
| `email_refused` | WARNING | Customer success reviews refused reminders every morning. |

## Payments are not matching

- Run `ledgerly reconcile` and look at the `unmatched` count. Ambiguous payments (same
  customer and amount as several open invoices) are left unmatched on purpose.
- Ask the customer for the `INV-nnnn` reference, or set `invoice_id` on the payment
  record by hand and rerun.

## Stale FX rates

Reconciliation warns when the rate table is more than three days old. Regenerate it:

```bash
python scripts/backfill_fx_rates.py exports/rates.csv /srv/ledgerly/rates.json
```

## Data file recovery

The data file is rewritten atomically, so a corrupt file almost always means the disk
filled up. Restore last night's copy from the backup bucket and rerun the nightly job;
imports are idempotent on payment id.

## Rotating gateway credentials

Update `LEDGERLY_PAYMENTS_KEY` and `LEDGERLY_PAYMENTS_SECRET` in the service environment
and restart. No code change is needed.
