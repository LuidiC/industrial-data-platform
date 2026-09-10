from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK_SOURCE = ROOT / "fabric" / "notebooks" / "nb_bronze_to_silver.py"
PURE_FUNCTIONS = {
    "_audit_sort_key",
    "_select_atlas_batches",
    "_select_mes_batches",
    "_normalize_id_value",
    "_canonical_record_hash",
    "_stable_quarantine_id",
}


def _load_pure_functions() -> dict:
    tree = ast.parse(NOTEBOOK_SOURCE.read_text(encoding="utf-8"), filename=str(NOTEBOOK_SOURCE))
    functions = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in PURE_FUNCTIONS
    ]
    namespace = {
        "ACCEPTED_STATUSES": {"SUCCEEDED", "SUCCEEDED_REPLAY"},
        "ATLAS_OBJECTS": (
            "production_lines",
            "machines",
            "products",
            "production_orders",
        ),
        "hashlib": hashlib,
        "json": json,
    }
    exec(
        compile(ast.Module(body=functions, type_ignores=[]), str(NOTEBOOK_SOURCE), "exec"),
        namespace,
    )
    return namespace


def _audit_row(
    source_system: str,
    source_object: str,
    *,
    audit_id: str,
    status: str = "SUCCEEDED",
    finished_at: str = "2026-09-10T10:00:00",
    source_identity_key: str | None = None,
    source_period: str | None = None,
    content_sha256: str | None = None,
) -> dict:
    return {
        "audit_id": audit_id,
        "batch_id": f"batch-{audit_id}",
        "source_system": source_system,
        "source_object": source_object,
        "status": status,
        "ingestion_started_at": finished_at,
        "ingestion_finished_at": finished_at,
        "source_identity_key": source_identity_key or f"{source_system}|{source_object}|{audit_id}",
        "source_period": source_period,
        "content_sha256": content_sha256,
        "destination_path": f"Files/raw/{source_system}/{source_object}/{audit_id}",
    }


def test_silver_notebook_compiles_and_has_the_mvp_boundary() -> None:
    source = NOTEBOOK_SOURCE.read_text(encoding="utf-8")
    compile(source, str(NOTEBOOK_SOURCE), "exec")

    for table in (
        "production_lines",
        "machines",
        "products",
        "production_orders",
        "production_events",
        "quarantine_records",
    ):
        assert f'"{table}"' in source

    for excluded_table in (
        "quality_inspections",
        "maintenance_events",
        "technical_documents",
    ):
        assert f'"{excluded_table}"' not in source

    assert 'SUPPORTED_DOMAINS = {"all", "atlas_erp", "mes"}' in source
    assert 'BRONZE_AUDIT_TABLE = "lh_bronze.dbo.ingestion_audit"' in source
    assert 'SILVER_TABLE_PREFIX = "lh_silver.dbo"' in source


def test_explicit_spark_schemas_cover_the_source_contract_fields() -> None:
    source = NOTEBOOK_SOURCE.read_text(encoding="utf-8")
    for contract_name in (
        "production-lines.v1.yaml",
        "machines.v1.yaml",
        "products.v1.yaml",
        "production-orders.v1.yaml",
        "production-events.v1.yaml",
    ):
        contract = yaml.safe_load(
            (ROOT / "docs" / "data-contracts" / contract_name).read_text(encoding="utf-8")
        )
        for field in contract["fields"]:
            assert f'StructField("{field["name"]}"' in source


def test_atlas_selection_uses_latest_accepted_batch_per_object() -> None:
    select = _load_pure_functions()["_select_atlas_batches"]
    rows: list[dict] = []
    for source_object in (
        "production_lines",
        "machines",
        "products",
        "production_orders",
    ):
        rows.extend(
            [
                _audit_row("atlas_erp", source_object, audit_id=f"old-{source_object}"),
                _audit_row(
                    "atlas_erp",
                    source_object,
                    audit_id=f"new-{source_object}",
                    finished_at="2026-09-10T11:00:00",
                ),
                _audit_row(
                    "atlas_erp",
                    source_object,
                    audit_id=f"failed-{source_object}",
                    status="FAILED",
                    finished_at="2026-09-10T12:00:00",
                ),
            ]
        )

    selected = select(rows)
    assert [row["source_object"] for row in selected] == [
        "production_lines",
        "machines",
        "products",
        "production_orders",
    ]
    assert all(row["audit_id"].startswith("new-") for row in selected)


def test_atlas_selection_fails_when_a_required_object_has_no_accepted_batch() -> None:
    select = _load_pure_functions()["_select_atlas_batches"]
    with pytest.raises(ValueError, match="production_lines"):
        select([])


def test_mes_selection_collapses_identical_replay_and_excludes_conflicts() -> None:
    select = _load_pure_functions()["_select_mes_batches"]
    identity = "mes|production_events|2025-01|production_events_2025_01.csv"
    original = _audit_row(
        "mes",
        "production_events",
        audit_id="original",
        source_identity_key=identity,
        source_period="2025-01",
        content_sha256="same-hash",
    )
    replay = _audit_row(
        "mes",
        "production_events",
        audit_id="replay",
        status="SUCCEEDED_REPLAY",
        finished_at="2026-09-10T11:00:00",
        source_identity_key=identity,
        source_period="2025-01",
        content_sha256="same-hash",
    )
    new_period = _audit_row(
        "mes",
        "production_events",
        audit_id="new-period",
        source_period="2025-02",
        content_sha256="new-hash",
    )
    conflict = _audit_row(
        "mes",
        "production_events",
        audit_id="conflict",
        status="CONFLICT_SOURCE_CHANGED",
        source_period="2025-03",
        content_sha256="conflict-hash",
    )

    selected = select([replay, conflict, new_period, original])
    assert [row["audit_id"] for row in selected] == ["original", "new-period"]


def test_normalization_hashing_and_quarantine_identity_are_stable() -> None:
    functions = _load_pure_functions()
    assert functions["_normalize_id_value"]("  mch-001 ") == "MCH-001"
    assert functions["_normalize_id_value"]("  ") is None

    columns = ("event_id", "quantity_produced")
    first = {"event_id": "PEV-1", "quantity_produced": 10}
    reordered = {"quantity_produced": 10, "event_id": "PEV-1"}
    first_hash = functions["_canonical_record_hash"](first, columns)
    assert first_hash == functions["_canonical_record_hash"](reordered, columns)
    assert first_hash != functions["_canonical_record_hash"](
        {"event_id": "PEV-1", "quantity_produced": 11}, columns
    )

    arguments = ("mes", "production_events", "batch-1", "row-1", "DQ-PROD-001", "negative")
    quarantine_id = functions["_stable_quarantine_id"](*arguments)
    assert quarantine_id == functions["_stable_quarantine_id"](*arguments)
    assert quarantine_id != functions["_stable_quarantine_id"](*arguments[:-1], "different")


def test_notebook_declares_dq_and_idempotent_merge_behavior() -> None:
    source = NOTEBOOK_SOURCE.read_text(encoding="utf-8")
    for rule_id in (
        "DQ-CORE-001",
        "DQ-CORE-002",
        "DQ-CORE-003",
        "DQ-CORE-004",
        "DQ-CORE-005",
        "DQ-CORE-006",
        "DQ-CORE-007",
        "DQ-PROD-001",
        "DQ-PROD-002",
        "DQ-PROD-003",
        "DQ-PROD-004",
        "DQ-PROD-005",
        "DQ-PROD-006",
    ):
        assert f'"{rule_id}"' in source

    assert 'condition="NOT (target.record_hash <=> source.record_hash)"' in source
    assert source.count("whenNotMatchedInsertAll()") >= 2
    assert 'duplicate_rule_id="DQ-PROD-006"' in source
    assert "insert_only=True" in source
