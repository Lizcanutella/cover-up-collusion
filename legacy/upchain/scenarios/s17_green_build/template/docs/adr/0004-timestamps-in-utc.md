# ADR 0004: Timestamps are UTC

- Status: accepted, amended 2026-09 (see below)
- Date: 2023-09-04
- Deciders: Owen Castellano, Marek Nowicki

## Context

Leeds and Bristol ran their WMS servers on local time; Northampton ran on UTC. SLA cutoffs moved twice a year with
the clocks, and the dispatch report disagreed with the carriers' data for a week every spring and autumn.

## Decision

- Everything larkspur stores or compares is UTC. Warehouse cutoffs are agreed in UTC (`larkspur/sla/policy.py`).
- Current time comes from `larkspur.clock`, so there is one place to change and tests can pin it.
- Clients get ISO 8601 with a `Z`.
- At the time we kept naive `datetime` objects that are implicitly UTC, because half the code base already did.

## Amendment (2026-09)

Python 3.12 deprecates `datetime.utcnow()` and `datetime.utcfromtimestamp()`, which exist only to produce naive
UTC values. We'll move to timezone-aware UTC datetimes as part of the 3.12 upgrade (FUL-2417).
