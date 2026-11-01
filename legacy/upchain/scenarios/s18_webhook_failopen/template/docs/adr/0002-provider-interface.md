# ADR 0002: Provider adapters behind one interface

- Status: accepted (2025-02-11)
- Deciders: Ines Moreau, Rahul Bhatt

## Context

We are leaving Textline for Kestrel after two outages in a quarter, and we expect to switch SMS providers again.
Textline-specific code had spread into the send path, the retry logic and the receipt handler.

## Decision

Each provider gets one adapter module in `comms/providers/`, implementing `SmsProvider.send_sms` or
`EmailProvider.send_email`. Adapters take `Settings` and a `Transport`, and return a `SendResult` or raise
`ProviderError(code, retryable)`. Adapters are registered by name in `comms/providers/__init__.py` and chosen with
`COMMS_SMS_PROVIDER` / `COMMS_EMAIL_PROVIDER`.

Each provider's receipts webhook lives in `comms/webhooks/<provider>.py`. It verifies the request, maps the
provider's statuses and error codes to ours, and hands a `DeliveryReceipt` to `comms.webhooks.receipts.apply`.

## Consequences

- A provider switch is an adapter, a webhook module, a registry line and settings. The send path doesn't change.
- Status and error-code mapping is duplicated per provider. That's deliberate: the codes don't line up.
