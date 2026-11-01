# Lumen ingestion API: the parts we use

Notes from Lumen's docs (v1, Aug 2026) and the onboarding call with their solutions engineer. Contract and API key
request: PROC-118. Key is in Secrets Manager as `casework/lumen-api-key`; staging has its own key.

## Appending rows

```
POST https://ingest.lumenhq.com/v1/datasets/{dataset}/rows
Authorization: Bearer <api key>
Content-Type: application/json

{"rows": [{...}, {...}]}
```

- At most 500 rows per request; larger requests get a 413.
- Rows are JSON objects. The dataset's schema is inferred from the first batch and widened when new keys appear;
  a key with a different type than before is a 400 for the whole request.
- Timestamps: ISO 8601 strings with an offset. Lumen converts to UTC.
- Success is `200 {"accepted": n}`. Anything else means nothing from that request was stored, so retrying the same
  request is safe.
- Appends only; deletions go through Lumen support (about 30 days).

## Datasets

The Data team creates datasets on their side. For support they have set up `support_tickets`, with
`hubspot_join_key` as the HubSpot connector's match column.

## HubSpot connector

Lumen can enrich a dataset with HubSpot contact properties (lifecycle stage, tariff, region). The connector joins
rows to HubSpot contacts on the contact's email address only: the dataset's match column must hold the
contact's primary email. Custom HubSpot properties and hashed values aren't supported as match keys. Rows that
don't match are kept, without the HubSpot columns. The Data team switches the connector on per dataset.

## Region

Lumen's ingestion and storage are in us-east-1. They have an EU region on their roadmap for 2027.

## Rate limits

60 requests a minute per key. Our weekly volume is a few thousand tickets, so a handful of requests.
