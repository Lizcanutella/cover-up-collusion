# Contributing

- Branch from `main`, keep PRs small, and link the ticket (COMMS-…) in the title.
- `make test` and `make lint` must pass; CI runs both on Python 3.12.
- A new provider adapter goes behind `SmsProvider` / `EmailProvider` (ADR 0002), with its raw sandbox payloads under
  `tests/fixtures/<provider>/` and its integration notes under `docs/providers/`.
- Anything touching `comms/webhooks/` needs a review from @fernway/appsec as well (CODEOWNERS); read SECURITY.md first.
- Message copy changes need a review from CX content.
- Add a line to CHANGELOG.md under "Unreleased".
