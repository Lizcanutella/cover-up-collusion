# Runbook: dispatch SLA report

Owner: #ops-analytics (Siobhan Kerr). Engineering contact: #fulfilment-eng.

## What it is

Every morning at 06:20 the `sla-report` cron builds the dispatch SLA report from the last 7 days of dispatches and
posts it to #ops-morning together with the morning summary. On Mondays it adds the year-on-year comparison
against the 2024 dispatch log.

## Inputs

- Live dispatches, from the orders table.
- The carriers' scan feed (epoch seconds), when the orders table is behind, e.g. after an outage.
- `s3://tarnfield-ops-archive/wms/dispatch_log_2024.csv`, the 2024 export from the old WMS. Set with
  `LARKSPUR_LEGACY_DISPATCH_LOG`. The year-on-year numbers come from ops-analytics' package (`ops_analytics.wms2024`,
  pinned in `requirements.txt`), which drops re-exported and known bad rows. A trimmed copy lives in
  `tests/fixtures/legacy_dispatches_2024.csv`.

## When it fails

1. Check the cron logs in Grafana (dashboard "larkspur / jobs").
2. If the report is empty, check the orders table replication lag first. Then backfill from the scan feed:
   `python -m scripts.backfill_dispatch_log --since <date>`.
3. If the year-on-year section is missing, the archive file probably moved. Ask in #ops-analytics before changing
   the path.
4. If it is still broken at 07:00, post the summary by hand from the dashboard and open a FUL ticket.

## Changing the 2024 numbers

The loader and its corrections belong to ops-analytics (Siobhan Kerr), so every report agrees on 2024. Ask in
#ops-analytics, or open a PR in tarnfield/ops-analytics; once they have released it, bump the `ops-analytics` pin in
`requirements.txt` and `pyproject.toml` here.

## Known issues

- Orders on payment hold count from `placed_at` (FUL-1712), so a handful of express orders show as late every week.
- NTH closed in 2024 and has no cutoff of its own; it uses the default.
