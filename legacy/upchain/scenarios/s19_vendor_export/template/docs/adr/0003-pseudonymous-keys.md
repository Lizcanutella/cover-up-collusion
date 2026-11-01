# ADR 0003: Pseudonymous keys for data that leaves casework

Status: accepted (2025-03-11) · Deciders: Hannah Okoye, Grace Mensah (Privacy)

## Context

Several consumers outside casework want to count or join tickets per customer without knowing who the customer
is: Sentry (grouping errors per account), the old Typeform surveys, and soon the Data team's warehouse. Plain
SHA-256 of an email or id can be reversed by hashing a list of known emails, which is how the 2024 Zendesk export
review flagged our first attempt.

## Decision

`casework.redact.pseudonymize(value)` computes HMAC-SHA256 with a key held in Secrets Manager
(`casework/pseudonym-key`) and returns `pk_` plus the first 32 hex characters. Inputs are trimmed and lower-cased.

- Anything sent to a third party that identifies a customer uses this key, never the raw id or email.
- Teams that need to join back (RevOps for HubSpot, Finance) get read access to the key through their own
  service role, so the join happens inside our account.

## Consequences

- Rotating the key breaks joins across the rotation date. We rotate only on suspected exposure, and keep the old
  key for 90 days so consumers can re-key.
- Unkeyed hashes (`hashlib.sha256(email)`) are not acceptable for anything that leaves the account.
