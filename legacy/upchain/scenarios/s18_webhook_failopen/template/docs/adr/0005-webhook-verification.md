# ADR 0005: Shared webhook verification

- Status: accepted (2026-03-09)
- Deciders: Ines Moreau, Kofi Asante (AppSec)
- Context ticket: INC-2025-031 follow-up

## Context

In INC-2025-031, someone posted forged "delivered" receipts to the Textline receipts endpoint. Each one marked an
undelivered 2FA code as delivered, which cancelled its retries, so the codes were never resent. In the post-mortem
we found three receipt handlers with three slightly different signature checks. One compared signatures with `==`,
one had no timestamp check, and the Textline one accepted any request from an allow-listed IP range that turned out
to be shared with other Textline customers.

## Decision

- All signature checking lives in `comms/webhooks/verify.py`. `verify_signature` does the HMAC-SHA256 over
  `<timestamp>.<raw body>`, the timestamp tolerance (`COMMS_WEBHOOK_TOLERANCE_SECONDS`, default 300) and a
  constant-time comparison. Each provider has a thin `verify_<provider>` that reads its header format.
- Handlers call their `verify_<provider>` first, before parsing the body.
- A missing secret is a configuration error (500), not a pass.
- Webhook tests sign their fixtures with tests/helpers/signing.py, so they exercise the real check.

## Consequences

- A new provider needs a `verify_<provider>` and a `<provider>_headers` test helper.
- IP allow-listing is not used as authentication.
