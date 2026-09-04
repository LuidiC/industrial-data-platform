from __future__ import annotations

from pathlib import Path

import psycopg

from .generator import GeneratedData

SCHEMA_FILE = Path(__file__).resolve().parents[2] / "database" / "atlas_erp_schema.sql"


def initialize_and_load(dsn: str, data: GeneratedData) -> None:
    with psycopg.connect(dsn) as connection:
        with connection.cursor() as cursor:
            cursor.execute(SCHEMA_FILE.read_text(encoding="utf-8"))
            for table, columns, rows in (
                ("production_lines", ("line_id", "line_name", "status"), data.production_lines),
                (
                    "machines",
                    ("machine_id", "line_id", "machine_name", "machine_type", "status"),
                    data.machines,
                ),
                (
                    "products",
                    ("product_id", "product_name", "product_family", "nominal_cycle_seconds"),
                    data.products,
                ),
                (
                    "production_orders",
                    (
                        "production_order_id",
                        "batch_id",
                        "product_id",
                        "line_id",
                        "planned_quantity",
                        "scheduled_start",
                        "scheduled_end",
                        "status",
                    ),
                    data.production_orders,
                ),
            ):
                quoted = ", ".join(columns)
                placeholders = ", ".join(["%s"] * len(columns))
                updates = ", ".join(
                    f"{column} = EXCLUDED.{column}" for column in columns if column != columns[0]
                )
                cursor.executemany(
                    f"INSERT INTO atlas_erp.{table} ({quoted}) VALUES ({placeholders}) ON CONFLICT ({columns[0]}) DO UPDATE SET {updates}",
                    [tuple(row[column] for column in columns) for row in rows],
                )
        connection.commit()
