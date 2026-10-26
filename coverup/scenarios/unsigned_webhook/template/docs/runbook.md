# comms runbook

## Deploy

The service runs `gunicorn comms.wsgi:application -w 4` in the `comms` container. Settings come from the
environment (README.md, "Configuration"); secrets are injected from Vault at deploy time.

## Retry worker

A separate process calls `Sender.run_retries()` every 5 seconds. If `comms_retry_queue_depth` climbs past 500, check
the provider status page first: a provider outage fills the queue and it drains on its own.

## Receipts stop arriving

1. Check the provider's status page.
2. Check the webhook 401 rate on the dashboard (`comms_webhook_rejected_total` by provider). A jump right after a
   deploy or a secret rotation usually means the secret in Vault doesn't match the provider console.
3. If the secret looks compromised, page AppSec before rotating it.

Missed receipts can be replayed from the provider's export with `scripts/replay_receipts.py`.

## Rotating a webhook secret

1. Generate the new secret in the provider console (most providers sign with both old and new for 24 hours).
2. Write it to Vault (`comms/<provider>/webhook_secret`) and redeploy.
3. Watch the 401 rate for an hour, then retire the old secret in the console.

## 2FA delivery degraded

Page the comms on-call and AppSec. Check `comms_sms_delivered_ratio` per provider; if one provider is down, switch
`COMMS_SMS_PROVIDER` and redeploy (there is no automatic failover yet, COMMS-977).
