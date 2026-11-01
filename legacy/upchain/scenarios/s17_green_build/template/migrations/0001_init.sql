-- larkspur initial schema (2023-05)
CREATE TABLE skus (
    sku         text PRIMARY KEY,
    description text NOT NULL,
    case_size   integer NOT NULL DEFAULT 1 CHECK (case_size > 0)
);

CREATE TABLE movements (
    id         bigserial PRIMARY KEY,
    sku        text NOT NULL REFERENCES skus (sku),
    warehouse  char(3) NOT NULL,
    delta      integer NOT NULL CHECK (delta <> 0),
    reason     text NOT NULL,
    ref        text NOT NULL DEFAULT '',
    at         timestamp NOT NULL DEFAULT (now() AT TIME ZONE 'utc')
);
CREATE INDEX movements_sku_warehouse ON movements (sku, warehouse);

CREATE TABLE orders (
    id            text PRIMARY KEY,
    customer_id   text NOT NULL,
    warehouse     char(3) NOT NULL,
    priority      text NOT NULL DEFAULT 'standard',
    status        text NOT NULL DEFAULT 'new',
    placed_at     timestamp NOT NULL,
    dispatched_at timestamp,
    cancelled_at  timestamp,
    cancel_reason text NOT NULL DEFAULT ''
);
