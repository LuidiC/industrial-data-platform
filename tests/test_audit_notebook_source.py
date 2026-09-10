from __future__ import annotations

import ast
import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path, PurePosixPath

import pytest

ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK_SOURCE = ROOT / "fabric" / "notebooks" / "nb_bronze_ingestion_audit.py"
TESTED_FUNCTIONS = {
    "_resolve_onelake_source_path",
    "_sha256_file",
    "_prepare_candidate",
    "_preflight",
    "_hash_path",
}


class _Row:
    def __init__(self, values: dict) -> None:
        self.values = values

    def asDict(self, *, recursive: bool) -> dict:  # noqa: N802
        assert recursive is True
        return dict(self.values)


class _Table:
    def __init__(self, rows: list[dict]) -> None:
        self.rows = rows

    def collect(self) -> list[_Row]:
        return [_Row(row) for row in self.rows]


class _Spark:
    def __init__(self, rows: list[dict]) -> None:
        self.rows = rows

    def table(self, name: str) -> _Table:
        assert name == "ingestion_audit"
        return _Table(self.rows)


def _load_notebook_functions() -> dict:
    tree = ast.parse(NOTEBOOK_SOURCE.read_text(encoding="utf-8"), filename=str(NOTEBOOK_SOURCE))
    functions = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in TESTED_FUNCTIONS
    ]
    namespace = {
        "UTC": UTC,
        "Path": Path,
        "PurePosixPath": PurePosixPath,
        "datetime": datetime,
        "hashlib": hashlib,
        "json": json,
        "timedelta": timedelta,
    }
    exec(
        compile(ast.Module(body=functions, type_ignores=[]), str(NOTEBOOK_SOURCE), "exec"),
        namespace,
    )
    return namespace


def _preflight_harness(lakehouse_root: Path, existing: list[dict]) -> tuple[dict, list[dict]]:
    namespace = _load_notebook_functions()
    appended: list[dict] = []
    original_prepare = namespace["_prepare_candidate"]
    namespace.update(
        {
            "SUCCESS_STATUSES": {"SUCCEEDED", "SUCCEEDED_REPLAY"},
            "TABLE_NAME": "ingestion_audit",
            "spark": _Spark(existing),
            "stale_after_hours": 2,
            "_ensure_table": lambda: None,
            "_now": lambda: datetime(2026, 9, 5, 12),
            "_new_id": lambda: f"audit-{len(appended) + 1}",
            "_new_batch_id": lambda: "generated-batch",
            "_timestamp": lambda value: value,
            "_fail_stale": lambda audit_ids, finished_at: None,
            "_append": lambda records: appended.extend(records),
            "_prepare_candidate": lambda candidate: original_prepare(
                candidate, lakehouse_root=lakehouse_root
            ),
        }
    )
    return namespace, appended


def _candidate(source_path: str) -> dict:
    return {
        "execution_id": "pipeline-run-1",
        "pipeline_name": "pl_ingest_mes",
        "source_system": "mes",
        "source_object": "production_events",
        "source_identity_key": "mes|production_events|2025-01|production_events_2025_01.csv",
        "source_file": "production_events_2025_01.csv",
        "source_period": "2025-01",
        "source_path": source_path,
        "transport_source": "onelake_demo_staging",
        "destination_path": (
            "Files/raw/mes/production_events/source_period=2025-01/"
            "batch_id=generated-batch/production_events_2025_01.csv"
        ),
    }


def test_onelake_source_hash_drives_ingest_skip_and_conflict(tmp_path: Path) -> None:
    relative_source = "Files/_demo_source_staging/mes/production_events_2025_01.csv"
    source = tmp_path / relative_source
    source.parent.mkdir(parents=True)
    source.write_bytes(b"event_id,quantity\nPEV-1,10\n")

    namespace, appended = _preflight_harness(tmp_path, [])
    first_plan = namespace["_preflight"]([_candidate(relative_source)])
    expected_digest = hashlib.sha256(source.read_bytes()).hexdigest()
    assert first_plan[0]["action"] == "INGEST"
    assert first_plan[0]["content_sha256"] == expected_digest
    assert first_plan[0]["source_size_bytes"] == source.stat().st_size
    assert json.loads(appended[0]["details_json"])["source_path"] == relative_source

    destination = tmp_path / first_plan[0]["destination_path"]
    destination.parent.mkdir(parents=True)
    destination.write_bytes(source.read_bytes())
    destination_digest, destination_size, file_count = namespace["_hash_path"](
        first_plan[0]["destination_path"], lakehouse_root=tmp_path
    )
    assert (destination_digest, destination_size, file_count) == (
        expected_digest,
        source.stat().st_size,
        1,
    )

    successful = {
        **appended[0],
        "status": "SUCCEEDED",
        "content_sha256": destination_digest,
        "source_size_bytes": destination_size,
    }
    namespace, _ = _preflight_harness(tmp_path, [successful])
    rerun_plan = namespace["_preflight"]([_candidate(relative_source)])
    assert rerun_plan[0]["action"] == "SKIP"

    source.write_bytes(source.read_bytes() + b"PEV-2,11\n")
    namespace, _ = _preflight_harness(tmp_path, [successful])
    changed_plan = namespace["_preflight"]([_candidate(relative_source)])
    assert changed_plan[0]["action"] == "CONFLICT"


def test_onelake_preflight_rejects_missing_source(tmp_path: Path) -> None:
    namespace = _load_notebook_functions()
    with pytest.raises(FileNotFoundError, match="OneLake staging source does not exist"):
        namespace["_prepare_candidate"](
            _candidate("Files/_demo_source_staging/mes/missing.csv"),
            lakehouse_root=tmp_path,
        )


@pytest.mark.parametrize(
    "source_path",
    [
        "../production_events.csv",
        "/lakehouse/default/Files/_demo_source_staging/mes/production_events.csv",
        "Files/_demo_source_staging/../raw/production_events.csv",
        "Files\\_demo_source_staging\\mes\\production_events.csv",
        "Files/raw/mes/production_events.csv",
    ],
)
def test_onelake_preflight_rejects_unsafe_source_path(tmp_path: Path, source_path: str) -> None:
    namespace = _load_notebook_functions()
    with pytest.raises(ValueError, match="source_path"):
        namespace["_prepare_candidate"](_candidate(source_path), lakehouse_root=tmp_path)
