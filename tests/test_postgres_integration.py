from __future__ import annotations

import os
from pathlib import Path

import psycopg
import pytest

from atlas_simulator.config import load_config
from atlas_simulator.generator import generate
from atlas_simulator.postgres import initialize_and_load


@pytest.mark.integration
def test_atlas_erp_schema_loads_and_queries() -> None:
    dsn = os.getenv("ATLAS_ERP_TEST_DSN")
    if not dsn:
        pytest.skip("Set ATLAS_ERP_TEST_DSN to run PostgreSQL integration tests.")
    root = Path(__file__).resolve().parents[1]
    data = generate(load_config(root / "config" / "simulator.default.toml"), inject_anomalies=False)
    initialize_and_load(dsn, data)
    initialize_and_load(dsn, data)
    with psycopg.connect(dsn) as connection, connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        assert cursor.fetchone()[0] == 1
        cursor.execute("SELECT to_regclass('atlas_erp.production_orders')")
        assert cursor.fetchone()[0] == "atlas_erp.production_orders"
        cursor.execute("SELECT count(*) FROM atlas_erp.machines")
        assert cursor.fetchone()[0] == 12
        cursor.execute("SELECT count(*) FROM atlas_erp.production_orders")
        assert cursor.fetchone()[0] == 360
        cursor.execute(
            "SELECT count(*) FROM atlas_erp.machines m LEFT JOIN atlas_erp.production_lines l ON l.line_id = m.line_id WHERE l.line_id IS NULL"
        )
        assert cursor.fetchone()[0] == 0
        cursor.execute(
            "SELECT count(*) FROM atlas_erp.production_orders o LEFT JOIN atlas_erp.products p ON p.product_id = o.product_id WHERE p.product_id IS NULL"
        )
        assert cursor.fetchone()[0] == 0
        cursor.execute(
            "SELECT count(*) FROM atlas_erp.production_orders o LEFT JOIN atlas_erp.production_lines l ON l.line_id = o.line_id WHERE l.line_id IS NULL"
        )
        assert cursor.fetchone()[0] == 0
        cursor.execute(
            "SELECT p.product_family, count(*) FROM atlas_erp.production_orders o JOIN atlas_erp.products p ON p.product_id = o.product_id GROUP BY p.product_family"
        )
        assert len(cursor.fetchall()) == 3
        cursor.execute(
            "SELECT has_table_privilege('atlas_fabric_reader', 'atlas_erp.production_orders', 'SELECT')"
        )
        assert cursor.fetchone()[0] is True
        cursor.execute("SELECT count(*) FROM atlas_erp.production_orders")
        assert cursor.fetchone()[0] == 360
