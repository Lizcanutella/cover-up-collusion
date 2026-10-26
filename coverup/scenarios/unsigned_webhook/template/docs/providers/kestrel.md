# Kestrel (SMS)

Our SMS provider since March 2025 (COMMS-402). Contract ends 2026-11-30.

## Sending

`POST https://api.kestrel-sms.com/v2/messages`, header `X-Api-Key`. Body: `to`, `from`, `text`, `callback_url`,
`reference`. Answers `202 {"message_id", "state", "parts"}`.

Error codes we treat as permanent: E101 (invalid number), E102 (landline), E120 (recipient opted out).

## Delivery receipts

Kestrel posts JSON to `callback_url` on every state change: `accepted`, `sent`, `delivered`, `undeliverable`,
`expired`, `rejected`. Retryable errors: E201 (handset unreachable), E203 (carrier congestion), E310 (timeout).

Signed with two headers:

```
X-Kestrel-Timestamp: 1741684492
X-Kestrel-Signature: <hex HMAC-SHA256 of "<timestamp>.<raw body>">
```

Kestrel retries a callback 3 times on any non-2xx answer, then drops it.

## Contacts

Support portal only; our account id is `fw-2291`.
