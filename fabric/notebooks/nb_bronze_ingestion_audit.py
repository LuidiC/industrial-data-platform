from __future__ import annotations

# ruff: noqa: E402, F821, I001
# Fabric notebook source
# Attach this notebook to lh_bronze before running it.

# PARAMETERS CELL
mode = "initialize"  # initialize | preflight | finalize
payload_json = "[]"
copy_results_json = "[]"
stale_after_hours = 2

# CELL -----------------------------------------------------------------------
import hashlib
import json
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path, PurePosixPath

from delta.tables import DeltaTable
from pyspark.sql import Row
from pyspark.sql import functions as F
from pyspark.sql.types import (
    BooleanType,
    LongType,
    StringType,
    StructField,
    StructType,
    TimestampType,
)


TABLE_NAME = "ingestion_audit"
SUCCESS_STATUSES = {"SUCCEEDED", "SUCCEEDED_REPLAY"}
AUDIT_SCHEMA = StructType(
    [
        StructField("audit_id", StringType(), False),
        StructField("batch_id", StringType(), False),
        StructField("execution_id", StringType(), False),
        StructField("parent_execution_id", StringType(), True),
        StructField("pipeline_name", StringType(), False),
        StructField("source_system", StringType(), False),
        StructField("source_object", StringType(), False),
        StructField("source_identity_key", StringType(), False),
        StructField("source_file", StringType(), True),
        StructField("source_period", StringType(), True),
        StructField("transport_source", StringType(), False),
        StructField("destination_path", StringType(), False),
        StructField("ingestion_started_at", TimestampType(), False),
        StructField("ingestion_finished_at", TimestampType(), True),
        StructField("status", StringType(), False),
        StructField("records_read", LongType(), True),
        StructField("records_written", LongType(), True),
        StructField("files_read", LongType(), True),
        StructField("files_written", LongType(), True),
        StructField("source_last_modified", TimestampType(), True),
        StructField("source_size_bytes", LongType(), True),
        StructField("content_sha256", StringType(), True),
        StructField("error_code", StringType(), True),
        StructField("error_message", StringType(), True),
        StructField("force_reprocess", BooleanType(), False),
        StructField("replay_of_batch_id", StringType(), True),
        StructField("extract_window_start", TimestampType(), True),
        StructField("extract_window_end", TimestampType(), True),
        StructField("details_json", StringType(), True),
    ]
)


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _timestamp(value):
    if value in (None, ""):
        return None
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return parsed.astimezone(UTC).replace(tzinfo=None)


def _new_id() -> str:
    return str(uuid.uuid4())


def _new_batch_id() -> str:
    return f"{datetime.now(UTC):%Y%m%dT%H%M%S%fZ}-{uuid.uuid4().hex[:12]}"


def _empty_record() -> dict:
    return {field.name: None for field in AUDIT_SCHEMA.fields}


def _ensure_table() -> None:
    if not spark.catalog.tableExists(TABLE_NAME):
        spark.createDataFrame([], AUDIT_SCHEMA).write.format("delta").mode("error").saveAsTable(
            TABLE_NAME
        )


def _append(records: list[dict]) -> None:
    if records:
        rows = [Row(**{**_empty_record(), **record}) for record in records]
        spark.createDataFrame(rows, AUDIT_SCHEMA).write.format("delta").mode("append").saveAsTable(
            TABLE_NAME
        )


def _fail_stale(audit_ids: list[str], finished_at: datetime) -> None:
    if not audit_ids:
        return
    DeltaTable.forName(spark, TABLE_NAME).update(
        condition=F.col("audit_id").isin(audit_ids) & (F.col("status") == "STARTED"),
        set={
            "status": F.lit("FAILED"),
            "ingestion_finished_at": F.lit(finished_at),
            "error_code": F.lit("STALE_STARTED"),
            "error_message": F.lit("Recovered by a later preflight after the stale threshold."),
        },
    )


def _resolve_onelake_source_path(
    source_path: str, *, lakehouse_root: Path | None = None
) -> tuple[Path, str]:
    if not isinstance(source_path, str) or not source_path.strip():
        raise ValueError("source_path is required when transport_source is onelake_demo_staging.")
    if "\\" in source_path:
        raise ValueError("source_path must use Lakehouse-relative POSIX separators.")

    relative = PurePosixPath(source_path)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("source_path must remain relative to the attached Lakehouse.")
    staging_root = PurePosixPath("Files/_demo_source_staging")
    if relative == staging_root or not relative.is_relative_to(staging_root):
        raise ValueError("source_path must be a file below Files/_demo_source_staging.")

    root = (lakehouse_root or Path("/lakehouse/default")).resolve()
    resolved = (root / Path(*relative.parts)).resolve()
    if not resolved.is_relative_to(root):
        raise ValueError("source_path resolves outside the attached Lakehouse.")
    if not resolved.exists():
        raise FileNotFoundError(f"OneLake staging source does not exist: {source_path}")
    if not resolved.is_file():
        raise ValueError(f"OneLake staging source is not a file: {source_path}")
    return resolved, relative.as_posix()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _prepare_candidate(candidate: dict, *, lakehouse_root: Path | None = None) -> dict:
    prepared = dict(candidate)
    if prepared.get("transport_source") != "onelake_demo_staging":
        return prepared

    source, normalized_source_path = _resolve_onelake_source_path(
        prepared.get("source_path"), lakehouse_root=lakehouse_root
    )
    prepared["content_sha256"] = _sha256_file(source)
    prepared["source_size_bytes"] = source.stat().st_size
    details = dict(prepared.get("details") or {})
    details["source_path"] = normalized_source_path
    prepared["details"] = details
    return prepared


def _preflight(candidates: list[dict]) -> list[dict]:
    _ensure_table()
    now = _now()
    existing = [row.asDict(recursive=True) for row in spark.table(TABLE_NAME).collect()]
    stale_ids: list[str] = []
    audit_rows: list[dict] = []
    plan: list[dict] = []

    for raw_candidate in candidates:
        candidate = _prepare_candidate(raw_candidate)
        identity = candidate["source_identity_key"]
        relevant = [row for row in existing if row["source_identity_key"] == identity]
        fresh_started = [
            row
            for row in relevant
            if row["status"] == "STARTED"
            and now - row["ingestion_started_at"] < timedelta(hours=stale_after_hours)
        ]
        stale_ids.extend(
            row["audit_id"]
            for row in relevant
            if row["status"] == "STARTED"
            and now - row["ingestion_started_at"] >= timedelta(hours=stale_after_hours)
        )
        successful = sorted(
            (row for row in relevant if row["status"] in SUCCESS_STATUSES),
            key=lambda row: row["ingestion_started_at"],
            reverse=True,
        )
        force_reprocess = bool(candidate.get("force_reprocess", False))
        replay_of_batch_id = candidate.get("replay_of_batch_id")
        action = "INGEST"
        status = "STARTED"
        error_code = None
        final = False

        if fresh_started:
            action, status, error_code, final = "BLOCK", "FAILED", "CONCURRENT_RUN", True
        elif force_reprocess:
            replay = next(
                (row for row in successful if row["batch_id"] == replay_of_batch_id), None
            )
            if replay is None:
                action, status, error_code, final = (
                    "CONFLICT",
                    "CONFLICT_SOURCE_CHANGED",
                    "INVALID_REPLAY_REFERENCE",
                    True,
                )
            elif any(
                (
                    replay["content_sha256"] != candidate.get("content_sha256"),
                    replay["source_file"] != candidate.get("source_file"),
                    replay["source_period"] != candidate.get("source_period"),
                )
            ):
                action, status, error_code, final = (
                    "CONFLICT",
                    "CONFLICT_SOURCE_CHANGED",
                    "REPLAY_SOURCE_MISMATCH",
                    True,
                )
        elif (
            successful
            and candidate.get("content_sha256") is None
            and candidate.get("transport_source") in {"postgresql_gateway", "maintcontrol_https"}
        ):
            action, status, error_code, final = (
                "SKIP",
                "SKIPPED_ALREADY_INGESTED",
                "ALREADY_INGESTED",
                True,
            )
        elif successful and successful[0]["content_sha256"] == candidate.get("content_sha256"):
            action, status, error_code, final = (
                "SKIP",
                "SKIPPED_ALREADY_INGESTED",
                "ALREADY_INGESTED",
                True,
            )
        elif successful:
            action, status, error_code, final = (
                "CONFLICT",
                "CONFLICT_SOURCE_CHANGED",
                "SOURCE_IDENTITY_HASH_CHANGED",
                True,
            )

        audit_id = _new_id()
        batch_id = candidate.get("batch_id") or _new_batch_id()
        audit_rows.append(
            {
                "audit_id": audit_id,
                "batch_id": batch_id,
                "execution_id": candidate["execution_id"],
                "parent_execution_id": candidate.get("parent_execution_id"),
                "pipeline_name": candidate["pipeline_name"],
                "source_system": candidate["source_system"],
                "source_object": candidate["source_object"],
                "source_identity_key": identity,
                "source_file": candidate.get("source_file"),
                "source_period": candidate.get("source_period"),
                "transport_source": candidate["transport_source"],
                "destination_path": candidate["destination_path"],
                "ingestion_started_at": now,
                "ingestion_finished_at": now if final else None,
                "status": status,
                "source_last_modified": _timestamp(candidate.get("source_last_modified")),
                "source_size_bytes": candidate.get("source_size_bytes"),
                "content_sha256": candidate.get("content_sha256"),
                "error_code": error_code,
                "error_message": candidate.get("error_message") if final else None,
                "force_reprocess": force_reprocess,
                "replay_of_batch_id": replay_of_batch_id,
                "extract_window_start": _timestamp(candidate.get("extract_window_start")),
                "extract_window_end": _timestamp(candidate.get("extract_window_end")),
                "details_json": json.dumps(candidate.get("details", {}), sort_keys=True),
            }
        )
        plan.append({**candidate, "audit_id": audit_id, "batch_id": batch_id, "action": action})

    _fail_stale(stale_ids, now)
    _append(audit_rows)
    return plan


def _hash_path(
    destination_path: str, *, lakehouse_root: Path | None = None
) -> tuple[str, int, int]:
    path = (lakehouse_root or Path("/lakehouse/default")) / destination_path.removeprefix("/")
    if path.is_file():
        files = [path]
    else:
        files = sorted(candidate for candidate in path.rglob("*") if candidate.is_file())
    digest = hashlib.sha256()
    size = 0
    for file_path in files:
        if not path.is_file():
            relative = file_path.relative_to(path).as_posix()
            digest.update(relative.encode("utf-8"))
        with file_path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                size += len(block)
                digest.update(block)
    return digest.hexdigest(), size, len(files)


def _finalize(results: list[dict]) -> list[dict]:
    _ensure_table()
    table = DeltaTable.forName(spark, TABLE_NAME)
    finalized: list[dict] = []
    for result in results:
        status = result.get("status", "FAILED")
        updates = {
            "ingestion_finished_at": F.lit(_now()),
            "status": F.lit(status),
            "records_read": F.lit(result.get("records_read")).cast("long"),
            "records_written": F.lit(result.get("records_written")).cast("long"),
            "files_read": F.lit(result.get("files_read")).cast("long"),
            "files_written": F.lit(result.get("files_written")).cast("long"),
            "error_code": F.lit(result.get("error_code")),
            "error_message": F.lit(result.get("error_message")),
            "details_json": F.lit(json.dumps(result.get("details", {}), sort_keys=True)),
        }
        if status in SUCCESS_STATUSES:
            digest, size, file_count = _hash_path(result["destination_path"])
            updates.update(
                {
                    "content_sha256": F.lit(digest),
                    "source_size_bytes": F.lit(size).cast("long"),
                    "files_written": F.lit(file_count).cast("long"),
                }
            )
        table.update(F.col("audit_id") == result["audit_id"], updates)
        finalized.append({"audit_id": result["audit_id"], "status": status})
    return finalized


# CELL -----------------------------------------------------------------------
if mode == "initialize":
    _ensure_table()
    output = {"table": TABLE_NAME, "status": "READY"}
elif mode == "preflight":
    output = {"plan": _preflight(json.loads(payload_json))}
elif mode == "finalize":
    output = {"finalized": _finalize(json.loads(copy_results_json))}
else:
    raise ValueError(f"Unsupported mode: {mode}")

try:
    from notebookutils import mssparkutils

    mssparkutils.notebook.exit(json.dumps(output, default=str, sort_keys=True))
except ImportError:
    print(json.dumps(output, default=str, sort_keys=True))
