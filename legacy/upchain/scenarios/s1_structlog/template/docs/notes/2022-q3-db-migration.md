# 2022 Q3: moving billing-core off the old MySQL host

*Status: done. Kept for reference. Some details are out of date.*

When this project was still the internal `billing-core` service we moved its data from
the aging MySQL 5.7 host to the shared Postgres cluster. Notes from that migration:

- The cutover happened on a Saturday night with writes frozen for about 40 minutes.
- Invoice ids were re-issued with the `INV-` prefix at that point; anything older than
  that still has a numeric id in the archive exports.
- Money columns were `DOUBLE` in the old schema. We converted to `NUMERIC(12,2)` and
  found 17 invoices where the stored total differed from the sum of its lines by a
  cent. Finance signed off on using the line sum.
- Connection pooling was set to 10 per worker; this turned out to be too many for the
  shared cluster and was lowered to 4 a month later.

The service has since been rewritten as `ledgerly` and now uses a JSON data file, so
none of the Postgres tooling mentioned above is in this repository any more. The
archive exports still live in the finance bucket under `billing-core/2022/`.
