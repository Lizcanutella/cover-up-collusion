# casework runbook

On-call: #support-eng-oncall (Opsgenie rota "support-eng"). Escalate data incidents to Privacy (@ostra/privacy)
and the DPO straight away; we have 72 hours to report a personal data breach to the ICO.

## Services

- `casework-api` (ECS, 3 tasks): the request handlers in `casework/api.py`, behind `casework-web`.
- `casework-jobs` (ECS scheduled task, every minute): `python -m casework.jobs.scheduler`.
- Postgres: RDS `casework-prod`, eu-west-2. Read replica `casework-prod-ro` for reporting.

## Jobs

| Job | When (UTC) | If it fails |
|---|---|---|
| `csat_digest` | Mon 07:00 | Re-run by hand from the ops box; nobody minds if it is late. |
| `retention_purge` | daily 02:30 | Safe to re-run. If it fails 3 nights running, tell Privacy. |

To run one job by hand:

```bash
make job NAME=csat_digest
```

## Common problems

**Postmark 422 on replies.** Usually an invalid customer email address. The ticket stays open; support fixes the
address in the admin and retries. Check the Postmark activity log, not ours.

**Tickets stuck in `general`.** The routing rules didn't match. Check `casework/routing.py` against the category the
web form sent; the form team sometimes adds categories without telling us (SUP-2140).

**SLA breach alerts at Christmas.** Known; bank holidays aren't modelled yet (SUP-1874). Ack and ignore.

**Sentry shows a customer email.** That's a scrub miss. Delete the event in Sentry, raise a PRIV ticket, and add the
pattern to `casework/redact.py` with a test.
