# Security

How we keep the comms service safe. AppSec (@fernway/appsec) owns this document; ask in #appsec.

## Reporting a vulnerability

Don't open an issue or a PR for it. Email security@fernway.io or post in #appsec-private. Anything that could
affect 2FA delivery goes to the AppSec on-call straight away.

## Dependencies

- Runtime code is standard library only (ADR 0003). A new runtime dependency needs an AppSec review on a SEC ticket.
- Dev dependencies are pinned in pyproject.toml; Renovate opens the bump PRs and CI runs `pip-audit` on them.

## Secrets

- Provider API keys and webhook signing secrets come from the environment (`COMMS_*`), injected from Vault at
  deploy time. Never commit them, including in fixtures or docs. Tests use the throwaway `TEST_SECRET` in
  tests/helpers/signing.py.
- To rotate a webhook secret, follow docs/runbook.md ("Rotating a webhook secret"); the last rotation was SEC-1388.

## Logging

- Never log message bodies, OTP codes or full phone numbers; use `comms.phone.mask()`.
- Webhook payloads may be logged at DEBUG only, with bodies redacted.

## Inbound webhooks

{warning}

## Outbound requests

- Provider calls go through `comms.providers.transport` with an explicit timeout. Don't disable TLS verification.

---

Last reviewed 2026-07-30.
