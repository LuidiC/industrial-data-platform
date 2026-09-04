CREATE SCHEMA IF NOT EXISTS atlas_erp;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'atlas_fabric_reader') THEN
        CREATE ROLE atlas_fabric_reader LOGIN PASSWORD 'atlas_reader_local_only' NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT;
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS atlas_erp.production_lines (
    line_id TEXT PRIMARY KEY,
    line_name TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('active', 'maintenance'))
);

CREATE TABLE IF NOT EXISTS atlas_erp.machines (
    machine_id TEXT PRIMARY KEY,
    line_id TEXT NOT NULL REFERENCES atlas_erp.production_lines(line_id),
    machine_name TEXT NOT NULL,
    machine_type TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('active', 'maintenance'))
);

CREATE TABLE IF NOT EXISTS atlas_erp.products (
    product_id TEXT PRIMARY KEY,
    product_name TEXT NOT NULL,
    product_family TEXT NOT NULL,
    nominal_cycle_seconds INTEGER NOT NULL CHECK (nominal_cycle_seconds > 0)
);

CREATE TABLE IF NOT EXISTS atlas_erp.production_orders (
    production_order_id TEXT PRIMARY KEY,
    batch_id TEXT NOT NULL UNIQUE,
    product_id TEXT NOT NULL REFERENCES atlas_erp.products(product_id),
    line_id TEXT NOT NULL REFERENCES atlas_erp.production_lines(line_id),
    planned_quantity INTEGER NOT NULL CHECK (planned_quantity > 0),
    scheduled_start TIMESTAMPTZ NOT NULL,
    scheduled_end TIMESTAMPTZ NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('released', 'completed')),
    CHECK (scheduled_end > scheduled_start)
);

REVOKE ALL ON SCHEMA atlas_erp FROM PUBLIC;
REVOKE ALL ON ALL TABLES IN SCHEMA atlas_erp FROM PUBLIC;
GRANT USAGE ON SCHEMA atlas_erp TO atlas_fabric_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA atlas_erp TO atlas_fabric_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA atlas_erp GRANT SELECT ON TABLES TO atlas_fabric_reader;
