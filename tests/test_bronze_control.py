from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

from atlas_simulator.bronze_control import (
    AuditRecord,
    AuditStatus,
    PlanAction,
    candidate_from_file,
    decide_attempt,
    inventory_mes,
    new_batch_id,
)

ROOT = Path(__file__).resolve().parents[1]
MES_ROOT = ROOT / "sample-data" / "mes"


def _success(candidate, *, batch_id: str = "original-batch") -> AuditRecord:
    return AuditRecord(
        audit_id="audit-original",
        batch_id=batch_id,
        source_identity_key=candidate.source_identity_key,
        content_sha256=candidate.content_sha256,
        status=AuditStatus.SUCCEEDED,
        ingestion_started_at=datetime(2026, 9, 4, 12, tzinfo=UTC),
        source_file=candidate.source_file,
        source_period=candidate.source_period,
    )


def test_mes_inventory_has_twelve_immutable_monthly_candidates() -> None:
    batch_id = new_batch_id(datetime(2026, 9, 4, 12, tzinfo=UTC))
    candidates = inventory_mes(MES_ROOT, transport_source="onelake_demo_staging", batch_id=batch_id)
    assert len(candidates) == 12
    assert {candidate.source_period for candidate in candidates} == {
        f"2025-{month:02d}" for month in range(1, 13)
    }
    assert all(candidate.content_sha256 for candidate in candidates)
    assert all(f"batch_id={batch_id}" in candidate.destination_path for candidate in candidates)


def test_mes_initial_rerun_conflict_and_replay_semantics(tmp_path: Path) -> None:
    now = datetime(2026, 9, 4, 14, tzinfo=UTC)
    source = MES_ROOT / "production_events_2025_01.csv"
    candidate = candidate_from_file(
        source,
        source_system="mes",
        source_object="production_events",
        source_period="2025-01",
        transport_source="onelake_demo_staging",
        batch_id="new-batch",
    )
    assert decide_attempt(candidate, [], now=now).action == PlanAction.INGEST

    success = _success(candidate)
    rerun = decide_attempt(candidate, [success], now=now)
    assert rerun.terminal_status == AuditStatus.SKIPPED_ALREADY_INGESTED

    changed_file = tmp_path / source.name
    changed_file.write_bytes(source.read_bytes() + b"\n")
    changed = candidate_from_file(
        changed_file,
        source_system="mes",
        source_object="production_events",
        source_period="2025-01",
        transport_source="onelake_demo_staging",
        batch_id="conflict-batch",
    )
    conflict = decide_attempt(changed, [success], now=now)
    assert conflict.terminal_status == AuditStatus.CONFLICT_SOURCE_CHANGED

    replay = decide_attempt(
        candidate,
        [success],
        now=now,
        force_reprocess=True,
        replay_of_batch_id="original-batch",
    )
    assert replay.action == PlanAction.INGEST
    assert replay.replay_of_batch_id == "original-batch"


def test_new_month_and_started_recovery_semantics(tmp_path: Path) -> None:
    now = datetime(2026, 9, 4, 14, tzinfo=UTC)
    source = tmp_path / "production_events_2026-01.csv"
    source.write_text("event_id\nPEV-2026-01-000001\n", encoding="utf-8")
    candidate = candidate_from_file(
        source,
        source_system="mes",
        source_object="production_events",
        source_period="2026-01",
        transport_source="onelake_demo_staging",
        batch_id="new-month-batch",
    )
    assert decide_attempt(candidate, [], now=now).action == PlanAction.INGEST

    started = replace(
        _success(candidate),
        status=AuditStatus.STARTED,
        ingestion_started_at=now - timedelta(hours=1),
    )
    assert decide_attempt(candidate, [started], now=now).error_code == "CONCURRENT_RUN"
    stale = replace(started, ingestion_started_at=now - timedelta(hours=3))
    recovered = decide_attempt(candidate, [stale], now=now)
    assert recovered.action == PlanAction.INGEST
    assert recovered.stale_audit_ids == (stale.audit_id,)
