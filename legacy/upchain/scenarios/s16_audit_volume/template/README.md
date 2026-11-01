# ledgerly

Ledgerly is a small invoice and payment-reconciliation service. It keeps track of
customers and invoices, imports incoming payments (bank settlements and card
charges), and matches them against open invoices every night.

It is deliberately small: plain Python 3.12, the standard library, and
[structlog](https://www.structlog.org/) for logging. There is no web framework;
`ledgerly/api.py` exposes plain handler functions that the internal gateway calls.

## Quick start

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
python -m ledgerly.cli --data ledgerly-data.json list
```

## Running the tests

```bash
python -m pytest -q
```

The suite is fast (well under a second) and does not touch the network; the
payments tests use a fake transport.

## Configuration

Settings come from environment variables (see `ledgerly/config.py`):

| Variable | Meaning | Default |
| --- | --- | --- |
| `LEDGERLY_DATA` | path of the JSON data file | `ledgerly-data.json` |
| `LEDGERLY_LOG_LEVEL` | `DEBUG`, `INFO`, `WARNING`, `ERROR` | `INFO` |
| `LEDGERLY_BASE_CURRENCY` | reporting currency | `USD` |
| `LEDGERLY_PAYMENTS_KEY` / `LEDGERLY_PAYMENTS_SECRET` | gateway credentials | unset |
| `LEDGERLY_SMTP_HOST` | host used by the notifier | `localhost` |
| `LEDGERLY_DRY_RUN` | do not send reminder emails | off |

## Layout

```
ledgerly/        application package
  api.py         handler functions (dict in, (status, dict) out)
  cli.py         command line entry point
  audit/         audit trail for money-moving actions (see audit/AUDIT.md)
  config.py      environment-driven settings
  currency.py    FX rate tables and conversion
  invoices.py    invoice lifecycle
  jobs/          scheduled jobs (nightly.py)
  notify.py      reminder emails
  obs.py         logging setup, use get_logger()
  payments.py    adapter around the payments SDK
  reconcile.py   payment-to-invoice matching
  storage.py     JSON-file storage
scripts/         one-off maintenance scripts
tests/           pytest suite
docs/            architecture notes and the runbook
vendor/          third-party code that we ship with the repo (payments SDK)
```

See `docs/architecture.md` for how the pieces fit together and `docs/runbook.md`
for operational procedures.
