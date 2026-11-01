-- ADR 0001: movements are never updated or deleted.
CREATE FUNCTION movements_append_only() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'movements are append-only; record a correcting movement instead';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER movements_no_update BEFORE UPDATE OR DELETE ON movements
    FOR EACH ROW EXECUTE FUNCTION movements_append_only();
