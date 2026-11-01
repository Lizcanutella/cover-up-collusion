# ADR 0005: In-repo job schedule instead of Airflow

Status: accepted (2025-06-16) · Deciders: Tom Hartley, Rhys Pemberton

## Context

We had two cron jobs on the ops box and were about to add a third. The Data team offered space on their Airflow,
but our jobs are small, need casework's code and settings, and Airflow would add a deploy step owned by another
team.

## Decision

Jobs live in `casework/jobs/`. `scheduler.py` holds the list (name, five-field cron in UTC, function). ECS runs
`python -m casework.jobs.scheduler` every minute and it runs what is due. Each job is a function taking a
`JobContext` (store, settings, `now`, optional HTTP transport), so tests can run any job at a fixed time with a
recording transport.

## Consequences

- No retries or backfill. A job that fails logs to Sentry (the casework-web project) and runs again at its next slot; jobs must be safe to
  re-run (idempotent or append-only on the receiving side).
- The cron parser is deliberately tiny (`*`, numbers, comma lists, day names). If you need ranges or steps, add
  them with tests.
- If we ever have more than ~10 jobs, revisit.
