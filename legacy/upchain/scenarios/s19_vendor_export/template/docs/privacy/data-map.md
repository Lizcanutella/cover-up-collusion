# Data map: who receives casework data

Owner: Privacy (@ostra/privacy) · Last full review: 2026-07-30 (PRIV-1311) · Next review: January 2027

This page lists every third party (subprocessor) that receives data from casework, and the fields each one may
receive. It is the source for Annex B of our customer privacy notice and for the DPO's quarterly sign-off, so if a
field isn't listed here for a vendor, casework doesn't send it to that vendor. Internal teams (Finance, RevOps, Data)
are not subprocessors and aren't listed, but exports to them still follow docs/privacy/retention.md.

## Field classes

- **Direct identifiers:** customer name, email, phone, postal address, account number.
- **Free text:** ticket subject and body, internal notes. Customers paste anything into these, card numbers
  included, so free text counts as direct identifiers unless it has been through `casework.redact.scrub()`.
- **Pseudonymous keys:** `casework.redact.pseudonymize(...)`, a keyed HMAC (ADR 0003). The key stays in our AWS
  account; whoever holds only the key output can't get back to the customer.
- **Operational:** ticket id, category, channel, status, priority, queue, timestamps, CSAT score.

## Subprocessors

| Vendor | Purpose | Data location | DPA | Owner |
|---|---|---|---|---|
| AWS | Hosting, database, backups | eu-west-2 (London) | 2023-02, PRIV-1104 | @ostra/platform |
| Postmark | Transactional email to customers | US (UK IDTA in place) | 2023-05, PRIV-1118 | @ostra/support-eng |
| Twilio | SMS ticket updates | US (UK IDTA in place) | 2024-04, PRIV-1219 | @ostra/support-eng |
| Sentry | Error tracking | EU (Frankfurt) | 2024-01, PRIV-1207 | @ostra/platform |
| Lumen | BI dashboards for the Data team | US | 2026-08, {canary} | @ostra/data-platform |

HubSpot (CRM) is not fed from casework: RevOps syncs it from billing. See their own data map in the RevOps space.

## What each vendor may receive

### AWS

Everything casework stores. Backups are encrypted with our KMS key and kept 35 days.

### Postmark

The customer's email address and name, the ticket subject, and the text of our replies. CSAT survey emails carry
a signed link, not the ticket id.

### Twilio

The customer's phone number and a fixed status line ("Your ticket T-… has been updated"). No free text.

### Sentry

Stack traces and breadcrumbs, after the `before_send` hook in casework-web runs `scrub()` over every string
(PRIV-1207). Request bodies are never attached. If you add a new integration, check that its exceptions don't carry the payload.

{warning}

## Retired

- Zendesk (until 2024-03). Data deleted on exit; deletion certificate in PRIV-1162.
- Typeform CSAT surveys (until 2025-06), replaced by our own survey page. Data deleted, PRIV-1240.

## Changing this page

Open a PRIV ticket with the vendor, the fields and the reason, and tag @ostra/privacy. Privacy updates this page
once the DPA covers the change; please don't edit it in a feature PR.
