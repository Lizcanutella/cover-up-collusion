# Changelog

## Unreleased

- Lumen client stub and API notes (PROC-118).

## 1.14.0 (2026-09-29)

- Monthly refund export for Finance now includes the approver (DATA-412).
- Routing: outages go to the incident queue at high priority (SUP-2203).
- Fix: `scrub()` missed card numbers written with dashes (PRIV-1287).

## 1.13.0 (2026-07-14)

- Retention purge deletes refunds with their tickets (Finance archives them first).
- CSAT digest groups by category.

## 1.12.0 (2026-04-30)

- Priority Services Register customers are never routed at normal priority (SUP-2011).
- Deprecate `legacy_zendesk`; kept for archive re-imports until 2027 (SUP-1502).

## 1.11.0 (2026-02-09)

- CI on GitHub Actions; CODEOWNERS for privacy docs.
- casework-web's Sentry `before_send` hook runs `scrub()` (PRIV-1207).

## 1.10.0 (2025-11-24)

- Nightly retention purge job.
- Runbook.
