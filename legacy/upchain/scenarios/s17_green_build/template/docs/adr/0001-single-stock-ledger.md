# ADR 0001: One stock ledger, no quantity columns

- Status: accepted
- Date: 2023-05-16
- Deciders: Owen Castellano, Ruth Adebayo

## Context

The old WMS kept a `quantity` column per SKU and location and updated it in place. Every stock discrepancy
investigation started with "we don't know how it got to this number". Counts drifted after failed dispatches, and
returns were applied twice at least once a quarter.

## Decision

Stock on hand is the sum of movements (`receipt`, `dispatch`, `adjustment`, `return`, `write_off`). Nothing stores
a running total. Reservations are separate rows and never change on-hand stock; available = on hand minus live
reservations. A floor count is recorded as an `adjustment` for the difference, with who counted it in `ref`.

## Consequences

- Any number can be explained by listing its movements.
- Reads are a sum. Fine at our size (about 40M movements); a nightly snapshot table backs the dashboards.
- Corrections are new movements, never edits. This is enforced in the database with a trigger
  (`migrations/0002_movements_append_only.sql`).
