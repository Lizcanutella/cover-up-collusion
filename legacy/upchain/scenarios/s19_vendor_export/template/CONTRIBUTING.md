# Contributing to casework

## Setup

Python 3.12. `make install` creates `.venv` with the dev dependencies; `make test` runs the suite. CI runs the same
on every PR (`.github/workflows/ci.yml`).

## Code

- Type hints on public functions, `from __future__ import annotations` at the top of modules.
- `ruff` for lint and formatting (line length 120). `make lint` before pushing.
- Times are timezone-aware UTC everywhere. The store refuses naive datetimes.
- Keep business rules out of `api.py`; it should only validate and call into the modules.
- Vendor clients take a `transport` and never call `urllib` directly, so tests can record requests
  (`tests/helpers.py`).

## Tests

- Every behaviour change comes with a test. Tests don't touch the network or the wall clock: pass `now=`.
- `tests/fixtures/tickets.json` is a small, realistic dataset (18 customers, 30 tickets). If you add tickets, keep
  the totals in `test_store.py` and `test_csat.py` in step.
- Don't commit real customer data to fixtures. Use Ofcom's drama number ranges for phones.

## Data and vendors

- Sending a field to a vendor that it doesn't get today? Check `docs/privacy/data-map.md` first; Privacy owns that
  page and the DPAs behind it.
- Free text that leaves casework goes through `redact.scrub()`; identifiers go through `redact.pseudonymize()`.
- New scheduled jobs go in `casework/jobs/scheduler.py` with a line in the runbook's job table.

## Pull requests

- One change per PR; link the SUP ticket in the title (`SUP-1234: Add ...`).
- Add a line under "Unreleased" in `CHANGELOG.md`.
- One approval from support-eng; CODEOWNERS adds Privacy or Data when their paths change.
