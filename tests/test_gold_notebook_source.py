from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK_SOURCE = ROOT / "fabric" / "notebooks" / "nb_silver_to_gold_production.py"
PIPELINE_SPEC = ROOT / "fabric" / "gold-pipeline-build-spec.md"
MODEL_DOC = ROOT / "docs" / "gold" / "phase5-production-mvp.md"
HANDOFF = ROOT / "docs" / "gold" / "phase5-handoff.md"


def _literal_assignment(source: str, name: str):
    tree = ast.parse(source, filename=str(NOTEBOOK_SOURCE))
    assignment = next(
        node
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == name for target in node.targets)
    )
    return ast.literal_eval(assignment.value)


def test_gold_notebook_compiles_and_has_exact_mvp_tables() -> None:
    source = NOTEBOOK_SOURCE.read_text(encoding="utf-8")
    compile(source, str(NOTEBOOK_SOURCE), "exec")

    assert _literal_assignment(source, "GOLD_TABLES") == {
        "dim_date": "lh_gold.dbo.dim_date",
        "dim_product": "lh_gold.dbo.dim_product",
        "dim_machine": "lh_gold.dbo.dim_machine",
        "dim_production_line": "lh_gold.dbo.dim_production_line",
        "fact_production_event": "lh_gold.dbo.fact_production_event",
    }
    assert _literal_assignment(source, "PUBLISH_ORDER") == (
        "dim_date",
        "dim_product",
        "dim_machine",
        "dim_production_line",
        "fact_production_event",
    )
    for excluded_table in (
        "dim_shift",
        "dim_production_order",
        "fact_production_order",
        "quality_gold",
        "maintenance_gold",
    ):
        assert excluded_table not in source


def test_fact_has_the_approved_columns_and_event_grain() -> None:
    source = NOTEBOOK_SOURCE.read_text(encoding="utf-8")
    for column in (
        "event_id",
        "production_order_id",
        "batch_id",
        "date_key",
        "production_date",
        "product_id",
        "machine_id",
        "production_line_id",
        "shift_code",
        "event_started_at_utc",
        "event_ended_at_utc",
        "produced_quantity",
        "rejected_quantity",
        "accepted_quantity",
    ):
        assert f'"{column}"' in source

    assert 'F.col("quantity_produced") - F.col("quantity_rejected")' in source
    assert '_validate_key(events, "event_id", "production_events")' in source
    assert "Gold fact row count must equal Silver production_events row count" in source


def test_dimensions_use_business_keys_and_continuous_date_sequence() -> None:
    source = NOTEBOOK_SOURCE.read_text(encoding="utf-8")
    assert "F.sequence(" in source
    assert 'F.date_format("calendar_date", "yyyyMMdd").cast("int")' in source

    for business_key in (
        "product_id",
        "machine_id",
        "production_line_id",
    ):
        assert f'"{business_key}"' in source

    assert "surrogate" not in source.lower()
    assert "monotonically_increasing_id" not in source


def test_notebook_validates_before_full_overwrite_and_writes_fact_last() -> None:
    source = NOTEBOOK_SOURCE.read_text(encoding="utf-8")
    validate_position = source.index("quantity_totals = _validate_gold(")
    diagnostics_position = source.index("order_alignment = _order_alignment_diagnostics(")
    publish_position = source.index("gold_row_counts = _publish(")
    assert validate_position < diagnostics_position < publish_position

    assert '.mode("overwrite")' in source
    assert '.option("overwriteSchema", "true")' in source
    assert "DeltaTable" not in source
    assert ".merge(" not in source
    assert _literal_assignment(source, "PUBLISH_ORDER")[-1] == "fact_production_event"


def test_required_validations_and_non_blocking_order_diagnostics_are_present() -> None:
    source = NOTEBOOK_SOURCE.read_text(encoding="utf-8")
    for validation_text in (
        "Required Silver tables do not exist",
        "Required Silver columns do not exist",
        "must not be null",
        "must be unique",
        "must resolve to its dimension",
        "machine owning line",
        "produced_quantity must be present and non-negative",
        "rejected_quantity must be present and non-negative",
        "rejected_quantity must not exceed produced_quantity",
        "accepted_quantity must equal produced_quantity minus rejected_quantity",
        "shift_code must stay inside the accepted enumeration",
        "Gold quantity totals must reconcile to Silver production_events",
    ):
        assert validation_text in source

    for diagnostic in (
        "distinct_event_order_ids",
        "orders_without_events",
        "event_order_batch_mismatches",
        "event_order_product_mismatches",
        "event_order_line_mismatches",
        "events_outside_order_schedule",
        "planned_metrics_eligible",
    ):
        assert f'"{diagnostic}"' in source

    assert source.index("quantity_totals = _validate_gold(") < source.index(
        "order_alignment = _order_alignment_diagnostics("
    )


def test_notebook_returns_the_required_structured_output() -> None:
    source = NOTEBOOK_SOURCE.read_text(encoding="utf-8")
    for output_field in (
        "status",
        "processing_run_id",
        "silver_source_row_counts",
        "gold_table_row_counts",
        "total_produced_quantity",
        "total_rejected_quantity",
        "total_accepted_quantity",
        "validation_status",
        "order_alignment_diagnostics",
    ):
        assert f'"{output_field}"' in source


def test_gold_documentation_and_pipeline_recipe_preserve_execution_boundary() -> None:
    specification = PIPELINE_SPEC.read_text(encoding="utf-8")
    model = MODEL_DOC.read_text(encoding="utf-8")
    handoff = HANDOFF.read_text(encoding="utf-8")

    assert "pl_transform_silver_to_gold" in specification
    assert "nb_transform_silver_to_gold_production" in specification
    assert "nb_silver_to_gold_production" in specification
    assert "@pipeline().RunId" in specification
    assert "exactly one Notebook activity" in specification
    assert "manual portal build recipe" in specification

    for document in (model, handoff):
        assert "fact_production_event" in document
        assert "planned quantity" in document.lower()
        assert "OEE" in document
        assert "not yet" in document.lower()

    assert "One accepted completed production event" in model
    assert "Power BI relationships" in model
    assert "Tenant execution checklist" in handoff
