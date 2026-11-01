# casework

Ostra's customer support ticket service: ticket intake from the web form, email and phone, routing to queues, SLA
timers, CSAT surveys, and the integrations around them (Postmark for email, the weekly digests, exports to Finance
and Data).

The HTTP layer lives in `casework-web`; this repository is the domain code, the jobs and the vendor clients.

## Layout

```
casework/
  api.py            request handlers (create, resolve, CSAT)
  routing.py        which queue a ticket lands in
  sla.py            first-response targets
  csat.py           CSAT summaries
  redact.py         scrub() and pseudonymize() for anything leaving casework
  store.py          the ticket store (SQLite in dev, Postgres in prod)
  export/           rows for exports to other teams and vendors
  jobs/             scheduled jobs and the schedule (ADR 0005)
  vendors/          third-party clients, all through vendors/http.py
  legacy_zendesk.py deprecated, archive re-imports only
docs/
  privacy/          data map and retention (owned by Privacy)
  adr/              decisions
  vendors/          notes on vendor APIs
  runbook.md
```

## Development

```bash
make install     # venv + dev dependencies
make test        # pytest
make seed        # load tests/fixtures/tickets.json into casework-dev.db
```

Settings come from `CASEWORK_*` environment variables (`casework/config.py`). Nothing has a production default.

## Data protection

casework holds customers' contact details and whatever they write to us. Before sending anything new to a vendor,
read `docs/privacy/data-map.md`; before keeping anything longer, read `docs/privacy/retention.md`.

## Owners

Support Engineering (#support-eng). Privacy owns `docs/privacy/`. See CODEOWNERS.
