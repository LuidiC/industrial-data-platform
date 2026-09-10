from __future__ import annotations

# ruff: noqa: E402, F821, I001
# Fabric notebook source
# Attach lh_bronze as the default Lakehouse so audited Files paths resolve under
# /lakehouse/default. Add lh_silver to the notebook and keep schemas enabled.

# PARAMETERS CELL
domain = "all"  # all | atlas_erp | mes
processing_run_id = ""

# CELL -----------------------------------------------------------------------
import hashlib
import json
import uuid
from datetime import UTC, datetime
from pathlib import PurePosixPath

from delta.tables import DeltaTable
from pyspark.sql import functions as F
from pyspark.sql import Window
from pyspark.sql.types import (
    LongType,
    StringType,
    StructField,
    StructType,
    TimestampType,
)


BRONZE_AUDIT_TABLE = "lh_bronze.dbo.ingestion_audit"
SILVER_TABLE_PREFIX = "lh_silver.dbo"
ACCEPTED_STATUSES = {"SUCCEEDED", "SUCCEEDED_REPLAY"}
SUPPORTED_DOMAINS = {"all", "atlas_erp", "mes"}
ATLAS_OBJECTS = (
    "production_lines",
    "machines",
    "products",
    "production_orders",
)
TECHNICAL_COLUMNS = (
    "source_system",
    "source_object",
    "source_batch_id",
    "source_file",
    "processed_at",
    "record_hash",
)

PRODUCTION_LINES_SCHEMA = StructType(
    [
        StructField("line_id", StringType(), True),
        StructField("line_name", StringType(), True),
        StructField("status", StringType(), True),
    ]
)
MACHINES_SCHEMA = StructType(
    [
        StructField("machine_id", StringType(), True),
        StructField("line_id", StringType(), True),
        StructField("machine_name", StringType(), True),
        StructField("machine_type", StringType(), True),
        StructField("status", StringType(), True),
    ]
)
PRODUCTS_SCHEMA = StructType(
    [
        StructField("product_id", StringType(), True),
        StructField("product_name", StringType(), True),
        StructField("product_family", StringType(), True),
        StructField("nominal_cycle_seconds", LongType(), True),
    ]
)
PRODUCTION_ORDERS_SCHEMA = StructType(
    [
        StructField("production_order_id", StringType(), True),
        StructField("batch_id", StringType(), True),
        StructField("product_id", StringType(), True),
        StructField("line_id", StringType(), True),
        StructField("planned_quantity", LongType(), True),
        StructField("scheduled_start", TimestampType(), True),
        StructField("scheduled_end", TimestampType(), True),
        StructField("status", StringType(), True),
    ]
)
PRODUCTION_EVENTS_RAW_SCHEMA = StructType(
    [
        StructField("event_id", StringType(), True),
        StructField("production_order_id", StringType(), True),
        StructField("batch_id", StringType(), True),
        StructField("product_id", StringType(), True),
        StructField("line_id", StringType(), True),
        StructField("machine_id", StringType(), True),
        StructField("event_started_at", StringType(), True),
        StructField("event_ended_at", StringType(), True),
        StructField("shift", StringType(), True),
        StructField("shift_business_date", StringType(), True),
        StructField("quantity_produced", StringType(), True),
        StructField("quantity_rejected", StringType(), True),
        StructField("status", StringType(), True),
    ]
)
QUARANTINE_SCHEMA = StructType(
    [
        StructField("quarantine_id", StringType(), False),
        StructField("processing_run_id", StringType(), False),
        StructField("source_system", StringType(), False),
        StructField("source_object", StringType(), False),
        StructField("source_batch_id", StringType(), False),
        StructField("source_file", StringType(), True),
        StructField("business_key", StringType(), True),
        StructField("source_row_locator", StringType(), False),
        StructField("rule_id", StringType(), False),
        StructField("reason", StringType(), False),
        StructField("original_row_json", StringType(), False),
        StructField("quarantined_at", TimestampType(), False),
    ]
)


def _audit_sort_key(row: dict) -> tuple[str, str, str]:
    finished = row.get("ingestion_finished_at") or row.get("ingestion_started_at") or ""
    return str(finished), str(row.get("ingestion_started_at") or ""), str(row.get("audit_id") or "")


def _select_atlas_batches(rows: list[dict]) -> list[dict]:
    selected: list[dict] = []
    for source_object in ATLAS_OBJECTS:
        candidates = [
            row
            for row in rows
            if row.get("source_system") == "atlas_erp"
            and row.get("source_object") == source_object
            and row.get("status") in ACCEPTED_STATUSES
        ]
        if not candidates:
            raise ValueError(f"No accepted Bronze batch found for atlas_erp.{source_object}.")
        selected.append(max(candidates, key=_audit_sort_key))
    return selected


def _select_mes_batches(rows: list[dict]) -> list[dict]:
    candidates = [
        row
        for row in rows
        if row.get("source_system") == "mes"
        and row.get("source_object") == "production_events"
        and row.get("status") in ACCEPTED_STATUSES
    ]
    accepted: dict[tuple[str, str], dict] = {}
    for row in candidates:
        logical_version = (
            str(row.get("source_identity_key") or ""),
            str(row.get("content_sha256") or row.get("destination_path") or ""),
        )
        current = accepted.get(logical_version)
        preference = (
            row.get("status") != "SUCCEEDED",
            *_audit_sort_key(row),
        )
        if current is None:
            accepted[logical_version] = row
        else:
            current_preference = (
                current.get("status") != "SUCCEEDED",
                *_audit_sort_key(current),
            )
            if preference < current_preference:
                accepted[logical_version] = row
    if not accepted:
        raise ValueError("No accepted Bronze batches found for mes.production_events.")
    return sorted(
        accepted.values(),
        key=lambda row: (
            str(row.get("source_period") or ""),
            str(row.get("source_identity_key") or ""),
            str(row.get("destination_path") or ""),
        ),
    )


def _normalize_id_value(value) -> str | None:
    if value is None or not str(value).strip():
        return None
    return str(value).strip().upper()


def _canonical_record_hash(record: dict, columns: tuple[str, ...]) -> str:
    payload = {column: record.get(column) for column in columns}
    serialized = json.dumps(payload, sort_keys=False, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _stable_quarantine_id(
    source_system: str,
    source_object: str,
    source_batch_id: str,
    source_row_locator: str,
    rule_id: str,
    reason: str,
) -> str:
    values = (
        source_system,
        source_object,
        source_batch_id,
        source_row_locator,
        rule_id,
        reason,
    )
    return hashlib.sha256("||".join(values).encode("utf-8")).hexdigest()


def _table(name: str) -> str:
    return f"{SILVER_TABLE_PREFIX}.{name}"


def _bronze_path(destination_path: str) -> str:
    relative = PurePosixPath(destination_path)
    if relative.is_absolute() or ".." in relative.parts or not relative.parts:
        raise ValueError(f"Unsafe audited Bronze destination path: {destination_path}")
    if relative.parts[0] != "Files":
        raise ValueError(f"Audited Bronze destination must be below Files: {destination_path}")
    return relative.as_posix()


def _null_if_empty(column):
    if isinstance(column, str):
        column = F.col(column)
    text = F.trim(column.cast("string"))
    return F.when(text == "", F.lit(None)).otherwise(text)


def _normalized_id(column):
    return F.upper(_null_if_empty(column))


def _normalized_text(column):
    return _null_if_empty(column)


def _normalized_code(column):
    return F.lower(_null_if_empty(column))


def _json_struct(columns: tuple[str, ...]):
    return F.to_json(
        F.struct(*[F.col(column).alias(column) for column in columns]),
        options={"ignoreNullFields": "false"},
    )


def _failure(rule_id: str, reason: str):
    return F.struct(F.lit(rule_id).alias("rule_id"), F.lit(reason).alias("reason"))


def _with_failures(frame, checks: list[tuple[object, str, str]]):
    failures = F.array(
        *[F.when(condition, _failure(rule_id, reason)) for condition, rule_id, reason in checks]
    )
    return frame.withColumn("_dq_failures", F.filter(failures, lambda item: item.isNotNull()))


def _append_failure(frame, condition, rule_id: str, reason: str):
    return frame.withColumn(
        "_dq_failures",
        F.when(
            condition,
            F.concat(F.col("_dq_failures"), F.array(_failure(rule_id, reason))),
        ).otherwise(F.col("_dq_failures")),
    )


def _mark_reference(frame, column: str, reference_table: str, reference_column: str, marker: str):
    references = (
        spark.table(reference_table)
        .select(F.col(reference_column).alias(f"_{marker}_key"))
        .distinct()
        .withColumn(marker, F.lit(True))
    )
    return frame.join(
        references,
        F.col(column) == F.col(f"_{marker}_key"),
        "left",
    ).drop(f"_{marker}_key")


def _decorate(frame, audit: dict, business_columns: tuple[str, ...]):
    destination_path = str(audit["destination_path"])
    source_file = audit.get("source_file") or PurePosixPath(destination_path).name
    frame = (
        frame.withColumn("source_system", F.lit(audit["source_system"]))
        .withColumn("source_object", F.lit(audit["source_object"]))
        .withColumn("source_batch_id", F.lit(audit["batch_id"]))
        .withColumn("source_file", F.lit(source_file))
        .withColumn("processed_at", F.lit(PROCESSING_TIMESTAMP).cast("timestamp"))
        .withColumn("record_hash", F.sha2(_json_struct(business_columns), 256))
    )
    return frame.withColumn(
        "_source_row_locator",
        F.sha2(
            F.concat_ws(
                "||",
                F.lit(destination_path),
                F.coalesce(F.col("_original_row_json"), F.lit("{}")),
            ),
            256,
        ),
    )


def _mark_duplicate_business_keys(frame, business_key: str, rule_id: str):
    order = Window.partitionBy(business_key).orderBy(
        F.col("record_hash"), F.col("_original_row_json"), F.col("source_batch_id")
    )
    counts = Window.partitionBy(business_key)
    frame = (
        frame.withColumn("_duplicate_rank", F.row_number().over(order))
        .withColumn("_duplicate_count", F.count(F.lit(1)).over(counts))
        .withColumn(
            "_source_row_locator",
            F.when(
                F.col("_duplicate_rank") > 1,
                F.concat(
                    F.col("_source_row_locator"),
                    F.lit("#duplicate-"),
                    F.col("_duplicate_rank").cast("string"),
                ),
            ).otherwise(F.col("_source_row_locator")),
        )
    )
    condition = (
        F.col(business_key).isNotNull()
        & (F.col("_duplicate_count") > 1)
        & (F.col("_duplicate_rank") > 1)
    )
    return _append_failure(
        frame,
        condition,
        rule_id,
        f"Duplicate business key in accepted Bronze input: {business_key}.",
    )


def _ensure_quarantine_table() -> None:
    name = _table("quarantine_records")
    if not spark.catalog.tableExists(name):
        spark.createDataFrame([], QUARANTINE_SCHEMA).write.format("delta").mode(
            "error"
        ).saveAsTable(name)


def _write_quarantine(frame, business_key: str) -> int:
    rejected = frame.filter(F.size("_dq_failures") > 0)
    failures = rejected.select(
        "source_system",
        "source_object",
        "source_batch_id",
        "source_file",
        F.col(business_key).cast("string").alias("business_key"),
        F.col("_source_row_locator").alias("source_row_locator"),
        F.explode("_dq_failures").alias("failure"),
        F.col("_original_row_json").alias("original_row_json"),
    ).select(
        "source_system",
        "source_object",
        "source_batch_id",
        "source_file",
        "business_key",
        "source_row_locator",
        F.col("failure.rule_id").alias("rule_id"),
        F.col("failure.reason").alias("reason"),
        "original_row_json",
    )
    failures = (
        failures.withColumn(
            "quarantine_id",
            F.sha2(
                F.concat_ws(
                    "||",
                    "source_system",
                    "source_object",
                    "source_batch_id",
                    "source_row_locator",
                    "rule_id",
                    "reason",
                ),
                256,
            ),
        )
        .withColumn("processing_run_id", F.lit(PROCESSING_RUN_ID))
        .withColumn("quarantined_at", F.lit(PROCESSING_TIMESTAMP).cast("timestamp"))
        .select(*[field.name for field in QUARANTINE_SCHEMA.fields])
    )
    count = failures.count()
    if count:
        (
            DeltaTable.forName(spark, _table("quarantine_records"))
            .alias("target")
            .merge(failures.alias("source"), "target.quarantine_id = source.quarantine_id")
            .whenNotMatchedInsertAll()
            .execute()
        )
    return count


def _mark_existing_event_conflicts(frame, business_key: str, target_table: str):
    if not spark.catalog.tableExists(target_table):
        return frame
    existing = spark.table(target_table).select(
        F.col(business_key).alias("_existing_key"),
        F.col("record_hash").alias("_existing_record_hash"),
    )
    frame = frame.join(existing, F.col(business_key) == F.col("_existing_key"), "left")
    conflict = F.col("_existing_key").isNotNull() & ~F.col("record_hash").eqNullSafe(
        F.col("_existing_record_hash")
    )
    frame = _append_failure(
        frame,
        conflict,
        "DQ-CORE-005",
        f"Business key already exists with a different payload: {business_key}.",
    )
    return frame.drop("_existing_key", "_existing_record_hash")


def _merge_table(frame, table_name: str, business_key: str, *, insert_only: bool) -> None:
    if not spark.catalog.tableExists(table_name):
        frame.write.format("delta").mode("error").saveAsTable(table_name)
        return
    merge = (
        DeltaTable.forName(spark, table_name)
        .alias("target")
        .merge(
            frame.alias("source"),
            f"target.`{business_key}` = source.`{business_key}`",
        )
    )
    if not insert_only:
        assignments = {column: f"source.`{column}`" for column in frame.columns}
        merge = merge.whenMatchedUpdate(
            condition="NOT (target.record_hash <=> source.record_hash)",
            set=assignments,
        )
    merge.whenNotMatchedInsertAll().execute()


def _publish(
    frame,
    table_name: str,
    business_key: str,
    business_columns: tuple[str, ...],
    *,
    duplicate_rule_id: str = "DQ-CORE-005",
    insert_only: bool = False,
) -> dict:
    frame = _mark_duplicate_business_keys(frame, business_key, duplicate_rule_id)
    target = _table(table_name)
    if insert_only:
        frame = _mark_existing_event_conflicts(frame, business_key, target)
    rejected_count = _write_quarantine(frame, business_key)
    valid = frame.filter(F.size("_dq_failures") == 0).select(*business_columns, *TECHNICAL_COLUMNS)
    valid_count = valid.count()
    _merge_table(valid, target, business_key, insert_only=insert_only)
    return {
        "table": table_name,
        "valid_input_rows": valid_count,
        "quarantine_failures": rejected_count,
        "silver_rows": spark.table(target).count(),
    }


def _read_atlas(audit: dict, schema: StructType):
    return spark.read.schema(schema).parquet(_bronze_path(audit["destination_path"]))


def _transform_production_lines(audit: dict) -> dict:
    business = ("line_id", "line_name", "status")
    raw = _read_atlas(audit, PRODUCTION_LINES_SCHEMA).withColumn(
        "_original_row_json", _json_struct(business)
    )
    frame = raw.select(
        _normalized_id("line_id").alias("line_id"),
        _normalized_text("line_name").alias("line_name"),
        _normalized_code("status").alias("status"),
        "_original_row_json",
    )
    frame = _decorate(frame, audit, business)
    frame = _with_failures(
        frame,
        [
            (F.col("line_id").isNull(), "DQ-CORE-001", "Required field is missing: line_id."),
            (
                F.col("line_name").isNull(),
                "DQ-CORE-001",
                "Required field is missing: line_name.",
            ),
            (F.col("status").isNull(), "DQ-CORE-001", "Required field is missing: status."),
            (
                F.col("status").isNotNull() & ~F.col("status").isin("active", "maintenance"),
                "DQ-CORE-003",
                "Value is outside the contract enumeration: status.",
            ),
        ],
    )
    return _publish(frame, "production_lines", "line_id", business)


def _transform_machines(audit: dict) -> dict:
    business = ("machine_id", "line_id", "machine_name", "machine_type", "status")
    raw = _read_atlas(audit, MACHINES_SCHEMA).withColumn(
        "_original_row_json", _json_struct(business)
    )
    frame = raw.select(
        _normalized_id("machine_id").alias("machine_id"),
        _normalized_id("line_id").alias("line_id"),
        _normalized_text("machine_name").alias("machine_name"),
        _normalized_code("machine_type").alias("machine_type"),
        _normalized_code("status").alias("status"),
        "_original_row_json",
    )
    frame = _decorate(frame, audit, business)
    frame = _mark_reference(frame, "line_id", _table("production_lines"), "line_id", "_line_ok")
    checks = [
        (F.col(column).isNull(), "DQ-CORE-001", f"Required field is missing: {column}.")
        for column in business
    ]
    checks.extend(
        [
            (
                F.col("machine_type").isNotNull()
                & ~F.col("machine_type").isin("assembly", "press", "inspection", "packaging"),
                "DQ-CORE-003",
                "Value is outside the contract enumeration: machine_type.",
            ),
            (
                F.col("status").isNotNull() & ~F.col("status").isin("active", "maintenance"),
                "DQ-CORE-003",
                "Value is outside the contract enumeration: status.",
            ),
            (
                F.col("line_id").isNotNull() & F.col("_line_ok").isNull(),
                "DQ-CORE-004",
                "Required reference does not exist: line_id.",
            ),
        ]
    )
    frame = _with_failures(frame, checks).drop("_line_ok")
    return _publish(frame, "machines", "machine_id", business)


def _transform_products(audit: dict) -> dict:
    business = ("product_id", "product_name", "product_family", "nominal_cycle_seconds")
    raw = _read_atlas(audit, PRODUCTS_SCHEMA).withColumn(
        "_original_row_json", _json_struct(business)
    )
    frame = raw.select(
        _normalized_id("product_id").alias("product_id"),
        _normalized_text("product_name").alias("product_name"),
        _normalized_code("product_family").alias("product_family"),
        F.col("nominal_cycle_seconds").cast("long").alias("nominal_cycle_seconds"),
        "_original_row_json",
    )
    frame = _decorate(frame, audit, business)
    checks = [
        (F.col(column).isNull(), "DQ-CORE-001", f"Required field is missing: {column}.")
        for column in business
    ]
    checks.extend(
        [
            (
                F.col("product_family").isNotNull()
                & ~F.col("product_family").isin("hydraulic", "electrical", "mechanical"),
                "DQ-CORE-003",
                "Value is outside the contract enumeration: product_family.",
            ),
            (
                F.col("nominal_cycle_seconds").isNotNull() & (F.col("nominal_cycle_seconds") < 1),
                "DQ-CORE-007",
                "Numeric value is outside the contract range: nominal_cycle_seconds.",
            ),
        ]
    )
    frame = _with_failures(frame, checks)
    return _publish(frame, "products", "product_id", business)


def _transform_production_orders(audit: dict) -> dict:
    business = (
        "production_order_id",
        "batch_id",
        "product_id",
        "line_id",
        "planned_quantity",
        "scheduled_start",
        "scheduled_end",
        "status",
    )
    raw = _read_atlas(audit, PRODUCTION_ORDERS_SCHEMA).withColumn(
        "_original_row_json", _json_struct(business)
    )
    frame = raw.select(
        _normalized_id("production_order_id").alias("production_order_id"),
        _normalized_id("batch_id").alias("batch_id"),
        _normalized_id("product_id").alias("product_id"),
        _normalized_id("line_id").alias("line_id"),
        F.col("planned_quantity").cast("long").alias("planned_quantity"),
        F.col("scheduled_start").cast("timestamp").alias("scheduled_start"),
        F.col("scheduled_end").cast("timestamp").alias("scheduled_end"),
        _normalized_code("status").alias("status"),
        "_original_row_json",
    )
    frame = _decorate(frame, audit, business)
    frame = _mark_reference(frame, "product_id", _table("products"), "product_id", "_product_ok")
    frame = _mark_reference(frame, "line_id", _table("production_lines"), "line_id", "_line_ok")
    checks = [
        (F.col(column).isNull(), "DQ-CORE-001", f"Required field is missing: {column}.")
        for column in business
    ]
    checks.extend(
        [
            (
                F.col("planned_quantity").isNotNull() & (F.col("planned_quantity") < 1),
                "DQ-CORE-007",
                "Numeric value is outside the contract range: planned_quantity.",
            ),
            (
                F.col("status").isNotNull() & ~F.col("status").isin("completed"),
                "DQ-CORE-003",
                "Value is outside the contract enumeration: status.",
            ),
            (
                F.col("scheduled_start").isNotNull()
                & F.col("scheduled_end").isNotNull()
                & (F.col("scheduled_end") <= F.col("scheduled_start")),
                "DQ-CORE-006",
                "End timestamp must be later than start timestamp.",
            ),
            (
                F.col("product_id").isNotNull() & F.col("_product_ok").isNull(),
                "DQ-CORE-004",
                "Required reference does not exist: product_id.",
            ),
            (
                F.col("line_id").isNotNull() & F.col("_line_ok").isNull(),
                "DQ-CORE-004",
                "Required reference does not exist: line_id.",
            ),
        ]
    )
    frame = _with_failures(frame, checks).drop("_product_ok", "_line_ok")
    return _publish(frame, "production_orders", "production_order_id", business)


def _read_mes(audits: list[dict]):
    frames = []
    business = tuple(field.name for field in PRODUCTION_EVENTS_RAW_SCHEMA.fields)
    for audit in audits:
        raw = (
            spark.read.option("header", True)
            .option("mode", "PERMISSIVE")
            .schema(PRODUCTION_EVENTS_RAW_SCHEMA)
            .csv(_bronze_path(audit["destination_path"]))
            .withColumn("_original_row_json", _json_struct(business))
            .withColumn("_audit_batch_id", F.lit(audit["batch_id"]))
            .withColumn("_audit_source_file", F.lit(audit.get("source_file")))
            .withColumn("_audit_destination_path", F.lit(audit["destination_path"]))
        )
        frames.append(raw)
    result = frames[0]
    for frame in frames[1:]:
        result = result.unionByName(frame)
    return result


def _transform_production_events(audits: list[dict]) -> dict:
    business = tuple(field.name for field in PRODUCTION_EVENTS_RAW_SCHEMA.fields)
    raw = _read_mes(audits)
    raw = raw.select(
        *[F.col(column).alias(f"_raw_{column}") for column in business],
        "_original_row_json",
        "_audit_batch_id",
        "_audit_source_file",
        "_audit_destination_path",
    )
    frame = raw.select(
        _normalized_id("_raw_event_id").alias("event_id"),
        _normalized_id("_raw_production_order_id").alias("production_order_id"),
        _normalized_id("_raw_batch_id").alias("batch_id"),
        _normalized_id("_raw_product_id").alias("product_id"),
        _normalized_id("_raw_line_id").alias("line_id"),
        _normalized_id("_raw_machine_id").alias("machine_id"),
        F.to_timestamp(_null_if_empty(F.col("_raw_event_started_at"))).alias("event_started_at"),
        F.to_timestamp(_null_if_empty(F.col("_raw_event_ended_at"))).alias("event_ended_at"),
        F.upper(_null_if_empty(F.col("_raw_shift"))).alias("shift"),
        F.to_date(_null_if_empty(F.col("_raw_shift_business_date"))).alias("shift_business_date"),
        _null_if_empty(F.col("_raw_quantity_produced")).cast("long").alias("quantity_produced"),
        _null_if_empty(F.col("_raw_quantity_rejected")).cast("long").alias("quantity_rejected"),
        _normalized_code("_raw_status").alias("status"),
        *[F.col(f"_raw_{column}") for column in business],
        "_original_row_json",
        F.lit("mes").alias("source_system"),
        F.lit("production_events").alias("source_object"),
        F.col("_audit_batch_id").alias("source_batch_id"),
        F.coalesce(
            F.col("_audit_source_file"),
            F.regexp_extract("_audit_destination_path", r"([^/]+)$", 1),
        ).alias("source_file"),
        F.lit(PROCESSING_TIMESTAMP).cast("timestamp").alias("processed_at"),
        "_audit_destination_path",
    )
    frame = frame.withColumn("record_hash", F.sha2(_json_struct(business), 256)).withColumn(
        "_source_row_locator",
        F.sha2(
            F.concat_ws("||", "_audit_destination_path", "_original_row_json"),
            256,
        ),
    )
    frame = _mark_reference(frame, "machine_id", _table("machines"), "machine_id", "_machine_ok")
    frame = _mark_reference(
        frame,
        "production_order_id",
        _table("production_orders"),
        "production_order_id",
        "_order_ok",
    )
    frame = _mark_reference(frame, "product_id", _table("products"), "product_id", "_product_ok")
    frame = _mark_reference(frame, "line_id", _table("production_lines"), "line_id", "_line_ok")

    required = (
        "event_id",
        "production_order_id",
        "batch_id",
        "product_id",
        "line_id",
        "machine_id",
        "shift",
        "status",
    )
    checks = [
        (F.col(column).isNull(), "DQ-CORE-001", f"Required field is missing: {column}.")
        for column in required
    ]
    for raw_column, typed_column in (
        ("event_started_at", "event_started_at"),
        ("event_ended_at", "event_ended_at"),
        ("shift_business_date", "shift_business_date"),
        ("quantity_produced", "quantity_produced"),
        ("quantity_rejected", "quantity_rejected"),
    ):
        raw_value = _null_if_empty(F.col(f"_raw_{raw_column}"))
        checks.append(
            (
                raw_value.isNull(),
                "DQ-CORE-001",
                f"Required field is missing: {raw_column}.",
            )
        )
        checks.append(
            (
                raw_value.isNotNull() & F.col(typed_column).isNull(),
                "DQ-CORE-002",
                f"Value cannot be parsed as the declared type: {raw_column}.",
            )
        )
    checks.extend(
        [
            (
                F.col("event_id").isNotNull()
                & ~F.col("event_id").rlike(r"^PEV-\d{4}-\d{2}-\d{6}$"),
                "DQ-PROD-002",
                "Production event identifier does not match the documented format.",
            ),
            (
                F.col("quantity_produced").isNotNull() & (F.col("quantity_produced") < 0),
                "DQ-PROD-001",
                "Production quantity cannot be negative.",
            ),
            (
                F.col("quantity_rejected").isNotNull() & (F.col("quantity_rejected") < 0),
                "DQ-CORE-007",
                "Numeric value is outside the contract range: quantity_rejected.",
            ),
            (
                F.col("quantity_produced").isNotNull()
                & F.col("quantity_rejected").isNotNull()
                & (F.col("quantity_rejected") > F.col("quantity_produced")),
                "DQ-CORE-007",
                "Rejected quantity cannot exceed produced quantity.",
            ),
            (
                F.col("status").isNotNull() & (F.col("status") != "completed"),
                "DQ-PROD-005",
                "Production event status must be completed.",
            ),
            (
                F.col("shift").isNotNull() & ~F.col("shift").isin("SHIFT-A", "SHIFT-B", "SHIFT-C"),
                "DQ-CORE-003",
                "Value is outside the contract enumeration: shift.",
            ),
            (
                F.col("event_started_at").isNotNull()
                & F.col("event_ended_at").isNotNull()
                & (F.col("event_ended_at") <= F.col("event_started_at")),
                "DQ-CORE-006",
                "End timestamp must be later than start timestamp.",
            ),
            (
                F.col("machine_id").isNotNull() & F.col("_machine_ok").isNull(),
                "DQ-PROD-003",
                "Production event references an unknown machine.",
            ),
            (
                F.col("production_order_id").isNotNull() & F.col("_order_ok").isNull(),
                "DQ-PROD-004",
                "Production event references an unknown production order.",
            ),
            (
                F.col("product_id").isNotNull() & F.col("_product_ok").isNull(),
                "DQ-CORE-004",
                "Required reference does not exist: product_id.",
            ),
            (
                F.col("line_id").isNotNull() & F.col("_line_ok").isNull(),
                "DQ-CORE-004",
                "Required reference does not exist: line_id.",
            ),
        ]
    )
    frame = _with_failures(frame, checks).drop(
        "_machine_ok", "_order_ok", "_product_ok", "_line_ok"
    )
    return _publish(
        frame,
        "production_events",
        "event_id",
        business,
        duplicate_rule_id="DQ-PROD-006",
        insert_only=True,
    )


def _load_audit_rows() -> list[dict]:
    return [
        row.asDict(recursive=True)
        for row in spark.table(BRONZE_AUDIT_TABLE)
        .filter(F.col("status").isin(*sorted(ACCEPTED_STATUSES)))
        .collect()
    ]


def _transform_atlas_erp(audit_rows: list[dict]) -> list[dict]:
    selected = {row["source_object"]: row for row in _select_atlas_batches(audit_rows)}
    return [
        _transform_production_lines(selected["production_lines"]),
        _transform_machines(selected["machines"]),
        _transform_products(selected["products"]),
        _transform_production_orders(selected["production_orders"]),
    ]


def _transform_mes(audit_rows: list[dict]) -> list[dict]:
    required = tuple(_table(name) for name in ATLAS_OBJECTS)
    missing = [name for name in required if not spark.catalog.tableExists(name)]
    if missing:
        raise ValueError(f"MES requires the AtlasERP Silver tables: {missing}")
    return [_transform_production_events(_select_mes_batches(audit_rows))]


# CELL -----------------------------------------------------------------------
domain = str(domain).strip().lower()
if domain not in SUPPORTED_DOMAINS:
    raise ValueError(f"Unsupported domain: {domain}. Expected one of {sorted(SUPPORTED_DOMAINS)}.")

PROCESSING_RUN_ID = str(processing_run_id).strip() or str(uuid.uuid4())
PROCESSING_TIMESTAMP = datetime.now(UTC).replace(tzinfo=None)
spark.conf.set("spark.sql.session.timeZone", "UTC")
_ensure_quarantine_table()
audit_rows = _load_audit_rows()
results: list[dict] = []

if domain in {"all", "atlas_erp"}:
    results.extend(_transform_atlas_erp(audit_rows))
if domain in {"all", "mes"}:
    results.extend(_transform_mes(audit_rows))

output = {
    "status": "SUCCEEDED",
    "domain": domain,
    "processing_run_id": PROCESSING_RUN_ID,
    "processed_at": PROCESSING_TIMESTAMP.isoformat() + "Z",
    "results": results,
}

try:
    from notebookutils import mssparkutils

    mssparkutils.notebook.exit(json.dumps(output, default=str, sort_keys=True))
except ImportError:
    print(json.dumps(output, default=str, sort_keys=True))
