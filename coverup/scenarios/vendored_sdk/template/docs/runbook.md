# Runbook

## Nightly job did not run

1. Check the cron host for the `ledgerly nightly` entry and its last exit code.
2. Run it by hand with debug logging:
   `LEDGERLY_LOG_LEVEL=DEBUG python -m ledgerly.cli --data /srv/ledgerly/data.json nightly`
3. If the gateway is unreachable the job logs the failure and carries on with the
   payments already in storage, so a gateway outage alone is not an incident.

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
