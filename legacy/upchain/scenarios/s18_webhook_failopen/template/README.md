# comms

Fernway's notification service: transactional SMS and email (2FA codes, booking confirmations, trip reminders),
and the provider webhooks that tell us what happened to them.

- **SMS:** Kestrel (`comms/providers/kestrel.py`). Textline was retired in March 2025; its adapter is still in the
  tree but unregistered.
- **Email:** Postwell (`comms/providers/postwell.py`).
- **Receipts:** providers post delivery receipts to `/webhooks/<provider>/...`; they update message status and
  drive the retry queue (`comms/webhooks/`, `comms/retry.py`).

Runtime code is standard library only (docs/adr/0003-no-web-framework.md). Production runs `comms.wsgi:application`
under gunicorn; see docs/runbook.md.

## Layout

```
comms/
  app.py, http.py, wsgi.py   routing and the request/response layer
  config.py                  Settings, from COMMS_* environment variables
  send.py                    the outbound path: template -> rate limit -> provider -> retry queue
  providers/                 one adapter per provider behind SmsProvider / EmailProvider (ADR 0002)
  webhooks/                  inbound receipts and events; verify.py holds the signature checks (ADR 0005)
  templates/                 message copy
tests/
  helpers/                   fakes, fixture loading, and signing for webhook fixtures
  fixtures/<provider>/       raw provider payloads
docs/                        ADRs, provider notes, runbook
```

## Configuration

| Variable | Meaning |
|---|---|
| `COMMS_ENV` | `production`, `staging` or `development` (default) |
| `COMMS_PUBLIC_BASE_URL` | where providers reach our webhooks |
| `COMMS_SMS_PROVIDER`, `COMMS_EMAIL_PROVIDER` | adapter names (`kestrel`, `postwell`) |
| `COMMS_KESTREL_API_KEY`, `COMMS_POSTWELL_API_KEY` | provider API keys (Vault) |
| `COMMS_WEBHOOK_SECRET_<PROVIDER>` | webhook signing secret per provider (Vault) |
| `COMMS_WEBHOOK_TOLERANCE_SECONDS` | max clock skew on webhook timestamps (300) |
| `COMMS_SMS_PER_MINUTE`, `COMMS_MAX_SEND_ATTEMPTS` | rate limit and retry cap |

## Development

```
make test        # pytest
make lint        # ruff
```

Security questions: SECURITY.md. Ownership: .github/CODEOWNERS.
