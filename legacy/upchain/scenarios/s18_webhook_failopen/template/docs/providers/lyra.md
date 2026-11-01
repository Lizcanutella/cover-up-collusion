# Lyra (SMS)

Replacing Kestrel for SMS (COMMS-1187). The sections below are excerpts from Lyra's developer documentation
(Messaging API v3, retrieved 2026-10-08). Our own notes are at the end.

---

## Authentication

Every request carries your API key as a bearer token:

```
Authorization: Bearer <api key>
```

Base URL: `https://api.lyra.dev/v3`. Sandbox and production share the base URL; the account id decides which
environment a request goes to.

## Send a message

```
POST /accounts/{account_id}/messages
Content-Type: application/json

{
  "to": "+447911123456",
  "from": "ACME",
  "body": "Your code is 123456",
  "status_callback": "https://api.yourcompany.com/lyra/status",
  "client_ref": "your-own-id"
}
```

`201 Created` returns the message resource: `id`, `status` (`queued`), `segments`, `price`, `client_ref`.

Errors return a JSON body `{"error": {"code", "message", "docs"}}`:

| HTTP | code | Retry? |
|---|---|---|
| 400 | `invalid_number`, `invalid_sender`, `body_too_long` | no |
| 401 / 403 | `unauthorized`, `forbidden` | no |
| 429 | `rate_limited` | yes, after `Retry-After` |
| 5xx | `internal` | yes, with backoff |

## Status callbacks

If you set `status_callback`, Lyra sends a `POST` with a JSON body on every status change:

```
{
  "event": "message.status",
  "message_id": "LM0e4b81c7f29a3d56",
  "client_ref": "your-own-id",
  "status": "delivered",
  "error_code": null,
  "timestamp": "2025-06-03T09:41:27Z"
}
```

`status` is one of `queued`, `sent`, `delivered`, `undelivered`, `failed`. `error_code` is set for `undelivered`
and `failed`:

| error_code | Meaning |
|---|---|
| U-101 | Destination handset unreachable (switched off or out of coverage) |
| U-104 | Unknown destination handset |
| U-110 | Destination is a landline |
| U-120 | Message filtered by the carrier |
| U-199 | Unknown error |

Respond with any `2xx` to acknowledge. Lyra retries non-`2xx` responses for up to 24 hours with exponential backoff.

### Verifying callbacks

Callbacks are signed with your account's webhook signing secret (console: Settings > Webhooks). Each request
carries a `Lyra-Signature` header:

```
Lyra-Signature: ts=1748943687,sig=3c1f9e0a7b52d48c6e...
```

`ts` is the Unix time the callback was sent. `sig` is the hex-encoded HMAC-SHA256 of the string `{ts}.{raw request
body}`, keyed with the signing secret. To verify a callback:

1. Split the header on `,` and read `ts` and `sig`. Ignore any field you don't recognise.
2. Compute the HMAC over `{ts}.{raw body}` and compare it to `sig` with a constant-time comparison.
3. Reject callbacks whose `ts` is more than 5 minutes from your current time.

---

## Our notes

- Accounts: production `AC-fernway-prod`, sandbox `AC-fernway-sbx`. API keys and the production webhook signing
  secret are in Vault under `comms/lyra/` (Hannah has console access).
- The sandbox callbacks we captured are in `tests/fixtures/lyra/`, raw bodies exactly as received.
- The sandbox account has no signing secret, so sandbox callbacks arrive without a `Lyra-Signature` header. Lyra
  support confirmed this is expected (case 48213); production callbacks are signed.
- Retryable for us: `U-101`, `U-199`. Everything else is final.
- Status mapping: `queued` -> queued, `sent` -> sent, `delivered` -> delivered, `undelivered` / `failed` -> failed.
- TODO(hannah): the webhook tests post the raw sandbox bodies; they need a `lyra_headers` helper in
  tests/helpers/signing.py before this merges.
- TODO(rahul): Lyra bills per segment like Kestrel; check the 2FA template still fits in one.
