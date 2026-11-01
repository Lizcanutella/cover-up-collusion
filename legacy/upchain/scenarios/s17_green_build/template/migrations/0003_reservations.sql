-- FUL-2033: reservations expire; keep them in their own table.
CREATE TABLE reservations (
    order_id  text NOT NULL REFERENCES orders (id),
    sku       text NOT NULL REFERENCES skus (sku),
    warehouse char(3) NOT NULL,
    quantity  integer NOT NULL CHECK (quantity > 0),
    at        timestamp NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
    PRIMARY KEY (order_id, sku)
);
-- TODO(marek): timestamptz everywhere once the app side is aware (ADR 0004 amendment). Separate migration.
