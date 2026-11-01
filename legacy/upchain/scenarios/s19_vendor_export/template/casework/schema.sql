-- casework schema. Production runs this on Postgres (see docs/runbook.md); dev and tests use SQLite.
-- Timestamps are ISO 8601 strings in UTC.

CREATE TABLE IF NOT EXISTS customers (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    email           TEXT NOT NULL,
    phone           TEXT NOT NULL DEFAULT '',
    address_line1   TEXT NOT NULL DEFAULT '',
    city            TEXT NOT NULL DEFAULT '',
    postcode        TEXT NOT NULL DEFAULT '',
    account_number  TEXT NOT NULL DEFAULT '',
    created_at      TEXT,
    vulnerable      INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS tickets (
    id                  TEXT PRIMARY KEY,
    customer_id         TEXT NOT NULL REFERENCES customers(id),
    subject             TEXT NOT NULL,
    body                TEXT NOT NULL,
    category            TEXT NOT NULL DEFAULT 'other',
    channel             TEXT NOT NULL DEFAULT 'email',
    status              TEXT NOT NULL DEFAULT 'open',
    priority            TEXT NOT NULL DEFAULT 'normal',
    created_at          TEXT,
    first_response_at   TEXT,
    resolved_at         TEXT,
    csat                INTEGER,
    assignee            TEXT NOT NULL DEFAULT '',
    queue               TEXT NOT NULL DEFAULT '',
    tags                TEXT NOT NULL DEFAULT ''   -- comma-separated
);

CREATE INDEX IF NOT EXISTS tickets_resolved_at ON tickets (resolved_at);
CREATE INDEX IF NOT EXISTS tickets_customer ON tickets (customer_id);

CREATE TABLE IF NOT EXISTS refunds (
    id              TEXT PRIMARY KEY,
    ticket_id       TEXT NOT NULL REFERENCES tickets(id),
    customer_id     TEXT NOT NULL REFERENCES customers(id),
    amount_pence    INTEGER NOT NULL,
    reason          TEXT NOT NULL,
    approved_by     TEXT NOT NULL,
    created_at      TEXT
);
