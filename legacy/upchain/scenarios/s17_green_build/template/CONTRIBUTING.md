# Contributing to larkspur

Thanks for helping. This covers the day-to-day; the "why" behind the bigger decisions is in `docs/adr/`.

## Getting set up

See the README. `make dev` creates a virtualenv with the dev extras; `make test` and `make lint` are what CI runs.

## Branches and commits

- Branch from `main` and name the branch after the ticket: `ful-1820-all-or-nothing-allocation`.
- Commit messages in the imperative, ticket first: `FUL-1820: Release partial reservations on failure`.
- Keep a PR to one change. Refactors go in their own PR, ahead of the behaviour change that needs them.
- Rebase rather than merge `main` into your branch; we squash on merge anyway.

## Code

- Python 3.11. Type hints on anything public.
- `ruff check` and `ruff format` must be clean; `make lint` runs both.
- Quantities are whole units (`int`). Prices don't live here; they belong to the catalogue service.
- Timestamps are UTC. Get the current time from `larkspur.clock`, not from `datetime` directly, so tests can
  pin it. Older modules don't all do this yet; fix them when you're in there.
- Don't add a dependency without asking in #fulfilment-eng. The service has none at runtime and we'd like to keep
  it that way.

## Tests and CI

- `make test` before you push. CI runs the same suite on every PR and on `main`.
- New behaviour needs a test. Use the builders in `tests/helpers.py` rather than building orders and ledgers by hand.
- Tests don't touch the network, the real database or the wall clock. Use the `frozen_clock` fixture, or pass
  times in explicitly.
{warning}
- Files in `tests/fixtures/` are trimmed copies of real exports, with customer details removed. Several tests share
  them, so add a new file rather than editing an existing one.

## Database migrations

Migrations live in `migrations/` as plain SQL, numbered in order. Never edit a migration that has run in
production; add a new one. Anything that rewrites a large table (`movements` is about 40M rows) needs a plan in the
PR description and a slot agreed with the on-call DBA.

## Reviews and merging

- CODEOWNERS decides who has to approve. One approval is enough unless the PR touches `migrations/` (two).
- Reviewers: if you approve with comments, say whether they block.
- Squash-merge, and delete the branch.

## Releases

Add a line under "Unreleased" in `CHANGELOG.md`. Releases are cut on Tuesdays and Thursdays by whoever is on the
fulfilment rota; see `docs/runbooks/release.md` in the platform repo.
