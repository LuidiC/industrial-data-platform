from __future__ import annotations

# ruff: noqa: E402, F821, I001
# Fabric notebook source
# Attach lh_gold as the default Lakehouse and add lh_silver with schemas enabled.

# PARAMETERS CELL
processing_run_id = ""

# CELL -----------------------------------------------------------------------
import json
import uuid

from pyspark.sql import DataFrame
from pyspark.sql import functions as F


SILVER_TABLES = {
    "production_lines": "lh_silver.dbo.production_lines",
    "machines": "lh_silver.dbo.machines",
    "products": "lh_silver.dbo.products",
    "production_orders": "lh_silver.dbo.production_orders",
    "production_events": "lh_silver.dbo.production_events",
}
GOLD_TABLES = {
    "dim_date": "lh_gold.dbo.dim_date",
    "dim_product": "lh_gold.dbo.dim_product",
    "dim_machine": "lh_gold.dbo.dim_machine",
    "dim_production_line": "lh_gold.dbo.dim_production_line",
    "fact_production_event": "lh_gold.dbo.fact_production_event",
}
PUBLISH_ORDER = (
    "dim_date",
    "dim_product",
    "dim_machine",
    "dim_production_line",
    "fact_production_event",
)
REQUIRED_COLUMNS = {
    "production_lines": {"line_id", "line_name", "status"},
    "machines": {"machine_id", "line_id", "machine_name", "machine_type", "status"},
    "products": {
        "product_id",
        "product_name",
        "product_family",
        "nominal_cycle_seconds",
    },
    "production_orders": {
        "production_order_id",
        "batch_id",
        "product_id",
        "line_id",
        "scheduled_start",
        "scheduled_end",
    },
    "production_events": {
        "event_id",
        "production_order_id",
        "batch_id",
        "product_id",
        "line_id",
        "machine_id",
        "event_started_at",
        "event_ended_at",
        "shift",
        "shift_business_date",
        "quantity_produced",
        "quantity_rejected",
    },
}
ACCEPTED_SHIFTS = ("SHIFT-A", "SHIFT-B", "SHIFT-C")


def _assert_zero(value: int, message: str) -> None:
    if value != 0:
        raise ValueError(f"{message} Found {value} invalid row(s).")


def _require_source_tables() -> dict[str, DataFrame]:
    missing_tables = [
        table_name
        for table_name in SILVER_TABLES.values()
        if not spark.catalog.tableExists(table_name)
    ]
    if missing_tables:
        raise ValueError(f"Required Silver tables do not exist: {missing_tables}")

    frames = {name: spark.table(table_name) for name, table_name in SILVER_TABLES.items()}
    missing_columns = {
        name: sorted(REQUIRED_COLUMNS[name] - set(frame.columns))
        for name, frame in frames.items()
        if REQUIRED_COLUMNS[name] - set(frame.columns)
    }
    if missing_columns:
        raise ValueError(f"Required Silver columns do not exist: {missing_columns}")
    return frames


def _validate_key(frame: DataFrame, column: str, label: str) -> None:
    _assert_zero(
        frame.filter(F.col(column).isNull()).count(),
        f"{label}.{column} must not be null.",
    )
    duplicate_count = (
        frame.groupBy(column).count().filter(F.col("count") > 1).select(column).count()
    )
    _assert_zero(duplicate_count, f"{label}.{column} must be unique.")


def _validate_reference(
    fact: DataFrame,
    fact_column: str,
    dimension: DataFrame,
    dimension_column: str,
    label: str,
) -> None:
    missing_count = (
        fact.select(F.col(fact_column).alias("_fact_key"))
        .join(
            dimension.select(F.col(dimension_column).alias("_dimension_key")),
            F.col("_fact_key") == F.col("_dimension_key"),
            "left_anti",
        )
        .count()
    )
    _assert_zero(missing_count, f"Every fact {label} must resolve to its dimension.")


def _build_dim_date(events: DataFrame) -> DataFrame:
    bounds = events.agg(
        F.min("shift_business_date").alias("minimum_date"),
        F.max("shift_business_date").alias("maximum_date"),
    ).first()
    if bounds.minimum_date is None or bounds.maximum_date is None:
        raise ValueError("production_events must contain at least one operational business date.")

    dates = spark.range(1).select(
        F.explode(F.sequence(F.lit(bounds.minimum_date), F.lit(bounds.maximum_date))).alias(
            "calendar_date"
        )
    )
    day_of_week_number = F.pmod(F.dayofweek("calendar_date") + F.lit(5), F.lit(7)) + F.lit(1)
    return dates.select(
        F.date_format("calendar_date", "yyyyMMdd").cast("int").alias("date_key"),
        "calendar_date",
        F.year("calendar_date").alias("year_number"),
        F.quarter("calendar_date").alias("quarter_number"),
        F.concat(F.lit("Q"), F.quarter("calendar_date")).alias("quarter_label"),
        F.month("calendar_date").alias("month_number"),
        F.date_format("calendar_date", "MMMM").alias("month_name"),
        F.date_format("calendar_date", "MMM").alias("month_short_name"),
        F.date_format("calendar_date", "yyyy-MM").alias("year_month"),
        F.dayofmonth("calendar_date").alias("day_of_month"),
        day_of_week_number.alias("day_of_week_number"),
        F.date_format("calendar_date", "EEEE").alias("day_of_week_name"),
        (day_of_week_number >= F.lit(6)).alias("is_weekend"),
    )


def _build_gold_frames(silver: dict[str, DataFrame]) -> dict[str, DataFrame]:
    lines = silver["production_lines"]
    machines = silver["machines"]
    products = silver["products"]
    events = silver["production_events"]

    dim_date = _build_dim_date(events)
    dim_product = products.select(
        "product_id",
        "product_name",
        "product_family",
        "nominal_cycle_seconds",
    )
    dim_machine = machines.select(
        "machine_id",
        "machine_name",
        "machine_type",
        F.col("status").alias("machine_status"),
        F.col("line_id").alias("owning_line_id"),
    )
    dim_production_line = lines.select(
        F.col("line_id").alias("production_line_id"),
        F.col("line_name").alias("production_line_name"),
        F.col("status").alias("production_line_status"),
    )
    fact_production_event = events.select(
        "event_id",
        "production_order_id",
        "batch_id",
        F.date_format("shift_business_date", "yyyyMMdd").cast("int").alias("date_key"),
        F.col("shift_business_date").alias("production_date"),
        "product_id",
        "machine_id",
        F.col("line_id").alias("production_line_id"),
        F.col("shift").alias("shift_code"),
        F.col("event_started_at").alias("event_started_at_utc"),
        F.col("event_ended_at").alias("event_ended_at_utc"),
        F.col("quantity_produced").alias("produced_quantity"),
        F.col("quantity_rejected").alias("rejected_quantity"),
        (F.col("quantity_produced") - F.col("quantity_rejected")).alias("accepted_quantity"),
    )
    return {
        "dim_date": dim_date,
        "dim_product": dim_product,
        "dim_machine": dim_machine,
        "dim_production_line": dim_production_line,
        "fact_production_event": fact_production_event,
    }


def _quantity_totals(frame: DataFrame, prefix: str) -> dict[str, int]:
    row = frame.agg(
        F.sum(f"{prefix}produced_quantity").alias("produced_quantity"),
        F.sum(f"{prefix}rejected_quantity").alias("rejected_quantity"),
    ).first()
    return {
        "produced_quantity": int(row.produced_quantity or 0),
        "rejected_quantity": int(row.rejected_quantity or 0),
    }


def _validate_gold(silver: dict[str, DataFrame], gold: dict[str, DataFrame]) -> dict[str, int]:
    lines = silver["production_lines"]
    machines = silver["machines"]
    products = silver["products"]
    events = silver["production_events"]
    fact = gold["fact_production_event"]

    _validate_key(lines, "line_id", "production_lines")
    _validate_key(machines, "machine_id", "machines")
    _validate_key(products, "product_id", "products")
    _validate_key(events, "event_id", "production_events")
    _validate_key(gold["dim_date"], "date_key", "dim_date")
    _validate_key(gold["dim_product"], "product_id", "dim_product")
    _validate_key(gold["dim_machine"], "machine_id", "dim_machine")
    _validate_key(
        gold["dim_production_line"],
        "production_line_id",
        "dim_production_line",
    )

    silver_event_count = events.count()
    fact_count = fact.count()
    if fact_count != silver_event_count:
        raise ValueError(
            "Gold fact row count must equal Silver production_events row count. "
            f"Silver={silver_event_count}, Gold={fact_count}."
        )

    _validate_reference(fact, "product_id", gold["dim_product"], "product_id", "product")
    _validate_reference(fact, "machine_id", gold["dim_machine"], "machine_id", "machine")
    _validate_reference(
        fact,
        "production_line_id",
        gold["dim_production_line"],
        "production_line_id",
        "production line",
    )
    _validate_reference(fact, "date_key", gold["dim_date"], "date_key", "date")

    machine_line_mismatches = (
        fact.alias("event")
        .join(gold["dim_machine"].alias("machine"), "machine_id", "inner")
        .filter(F.col("event.production_line_id") != F.col("machine.owning_line_id"))
        .count()
    )
    _assert_zero(
        machine_line_mismatches,
        "An event production line must agree with its machine owning line.",
    )

    _assert_zero(
        fact.filter(F.col("produced_quantity").isNull() | (F.col("produced_quantity") < 0)).count(),
        "produced_quantity must be present and non-negative.",
    )
    _assert_zero(
        fact.filter(F.col("rejected_quantity").isNull() | (F.col("rejected_quantity") < 0)).count(),
        "rejected_quantity must be present and non-negative.",
    )
    _assert_zero(
        fact.filter(F.col("rejected_quantity") > F.col("produced_quantity")).count(),
        "rejected_quantity must not exceed produced_quantity.",
    )
    _assert_zero(
        fact.filter(
            F.col("accepted_quantity").isNull()
            | (
                F.col("accepted_quantity")
                != F.col("produced_quantity") - F.col("rejected_quantity")
            )
        ).count(),
        "accepted_quantity must equal produced_quantity minus rejected_quantity.",
    )
    _assert_zero(
        fact.filter(
            F.col("shift_code").isNull() | ~F.col("shift_code").isin(*ACCEPTED_SHIFTS)
        ).count(),
        "shift_code must stay inside the accepted enumeration.",
    )

    silver_totals = _quantity_totals(
        events.select(
            F.col("quantity_produced").alias("silver_produced_quantity"),
            F.col("quantity_rejected").alias("silver_rejected_quantity"),
        ),
        "silver_",
    )
    gold_totals = _quantity_totals(fact, "")
    if gold_totals != silver_totals:
        raise ValueError(
            "Gold quantity totals must reconcile to Silver production_events. "
            f"Silver={silver_totals}, Gold={gold_totals}."
        )
    return {
        **gold_totals,
        "accepted_quantity": gold_totals["produced_quantity"] - gold_totals["rejected_quantity"],
    }


def _order_alignment_diagnostics(events: DataFrame, orders: DataFrame) -> dict[str, int | bool]:
    event_order_ids = events.select("production_order_id").distinct()
    orders_without_events = orders.select("production_order_id").join(
        event_order_ids, "production_order_id", "left_anti"
    )
    aligned = events.alias("event").join(orders.alias("order"), "production_order_id", "inner")

    batch_mismatches = aligned.filter(F.col("event.batch_id") != F.col("order.batch_id")).count()
    product_mismatches = aligned.filter(
        F.col("event.product_id") != F.col("order.product_id")
    ).count()
    line_mismatches = aligned.filter(F.col("event.line_id") != F.col("order.line_id")).count()
    outside_schedule = aligned.filter(
        (F.col("event.event_started_at") < F.col("order.scheduled_start"))
        | (F.col("event.event_ended_at") > F.col("order.scheduled_end"))
    ).count()
    event_orders_missing_from_orders = event_order_ids.join(
        orders.select("production_order_id"), "production_order_id", "left_anti"
    ).count()
    planned_metrics_eligible = all(
        value == 0
        for value in (
            event_orders_missing_from_orders,
            orders_without_events.count(),
            batch_mismatches,
            product_mismatches,
            line_mismatches,
            outside_schedule,
        )
    )
    return {
        "distinct_event_order_ids": event_order_ids.count(),
        "orders_without_events": orders_without_events.count(),
        "event_orders_missing_from_orders": event_orders_missing_from_orders,
        "event_order_batch_mismatches": batch_mismatches,
        "event_order_product_mismatches": product_mismatches,
        "event_order_line_mismatches": line_mismatches,
        "events_outside_order_schedule": outside_schedule,
        "planned_metrics_eligible": planned_metrics_eligible,
    }


def _publish(gold: dict[str, DataFrame]) -> dict[str, int]:
    for name in PUBLISH_ORDER:
        (
            gold[name]
            .write.format("delta")
            .mode("overwrite")
            .option("overwriteSchema", "true")
            .saveAsTable(GOLD_TABLES[name])
        )
    return {name: spark.table(GOLD_TABLES[name]).count() for name in PUBLISH_ORDER}


# CELL -----------------------------------------------------------------------
PROCESSING_RUN_ID = str(processing_run_id).strip() or str(uuid.uuid4())
spark.conf.set("spark.sql.session.timeZone", "UTC")

silver_frames = _require_source_tables()
gold_frames = _build_gold_frames(silver_frames)
quantity_totals = _validate_gold(silver_frames, gold_frames)
order_alignment = _order_alignment_diagnostics(
    silver_frames["production_events"], silver_frames["production_orders"]
)
source_row_counts = {name: frame.count() for name, frame in silver_frames.items()}
gold_row_counts = _publish(gold_frames)

if gold_row_counts["fact_production_event"] != source_row_counts["production_events"]:
    raise ValueError(
        "Published Gold fact row count does not reconcile to Silver production_events."
    )

output = {
    "status": "SUCCEEDED",
    "processing_run_id": PROCESSING_RUN_ID,
    "silver_source_row_counts": source_row_counts,
    "gold_table_row_counts": gold_row_counts,
    "total_produced_quantity": quantity_totals["produced_quantity"],
    "total_rejected_quantity": quantity_totals["rejected_quantity"],
    "total_accepted_quantity": quantity_totals["accepted_quantity"],
    "validation_status": "PASSED",
    "order_alignment_diagnostics": order_alignment,
}

try:
    from notebookutils import mssparkutils

    mssparkutils.notebook.exit(json.dumps(output, default=str, sort_keys=True))
except ImportError:
    print(json.dumps(output, default=str, sort_keys=True))
