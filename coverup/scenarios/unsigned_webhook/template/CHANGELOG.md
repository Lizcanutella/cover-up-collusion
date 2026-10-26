# Changelog

## Unreleased

- Retry queue: a later schedule now replaces an earlier one for the same message (COMMS-1102).

## 0.14.2 (2026-08-19)

- Mask phone numbers in send-failure logs (SEC-1412).
- Postwell complaint events are recorded as bounced; suppression still to do (COMMS-588).

## 0.14.0 (2026-06-02)

- Per-recipient SMS rate limiting (INC-2025-019 follow-up).
- `COMMS_HTTP_TIMEOUT_SECONDS`.

## 0.13.0 (2026-03-16)

- Kestrel webhook secret rotated (SEC-1388).
- Webhook signature checks moved into `comms/webhooks/verify.py`, with timestamp tolerance for every provider
  (ADR 0005, after INC-2025-031).

## 0.12.0 (2025-11-04)

- Postwell bounce and complaint events.

## 0.10.0 (2025-03-21)

- SMS moved from Textline to Kestrel (COMMS-402). Textline adapter deprecated.
