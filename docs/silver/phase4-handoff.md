# Phase 4A/4B handoff

## Snapshot

- Timestamp: `2026-09-10T17:07:25-03:00`
- Branch: `feat/phase-4-silver-transformation`
- Git status before reconciliation: clean
- Remote actions: none; no push, pull request, merge, or history rewrite was performed
- Scope stopped at Phase 4A (Silver foundation) and Phase 4B (AtlasERP + MES)

## Local checkpoints

- `7fe7ef3 feat: add AtlasERP and MES Silver transformation`
- `5662bd6 docs: document Silver production slice`
- `e8bbbd6 docs: add Phase 4 Silver handoff`
- `fix: reconcile Silver Fabric runtime issues` (this reconciliation checkpoint)

This reconciliation changes only:

- `fabric/notebooks/nb_bronze_to_silver.py`
- `tests/test_silver_notebook_source.py`
- `docs/silver/phase4-handoff.md`

Files changed from the merged Phase 3 baseline:

- `fabric/notebooks/nb_bronze_to_silver.py`
- `tests/test_silver_notebook_source.py`
- `fabric/silver-pipeline-build-spec.md`
- `fabric/README.md`
- `docs/silver/phase4-production-slice.md`
- `docs/silver/phase4-handoff.md`
- `docs/architecture/overview.md`
- `docs/data-quality/rules.yaml`
- `docs/data-contracts/production-lines.v1.yaml`
- `docs/data-contracts/machines.v1.yaml`
- `docs/data-contracts/products.v1.yaml`
- `docs/data-contracts/production-orders.v1.yaml`
- `docs/data-contracts/production-events.v1.yaml`
- `README.md`
- `README.en.md`

## Implemented repository behavior

The source-controlled PySpark notebook uses `lh_bronze.dbo.ingestion_audit` as the control plane,
accepts only `SUCCEEDED` and `SUCCEEDED_REPLAY`, and implements the following `lh_silver.dbo`
Delta tables:

| Table | Business key | Write behavior |
|---|---|---|
| `production_lines` | `line_id` | MERGE; changed hashes update |
| `machines` | `machine_id` | MERGE; changed hashes update |
| `products` | `product_id` | MERGE; changed hashes update |
| `production_orders` | `production_order_id` | MERGE; changed hashes update |
| `production_events` | `event_id` | Insert-safe MERGE; conflicting payload quarantined |
| `quarantine_records` | `quarantine_id` | Insert-only deterministic MERGE |

AtlasERP selects the latest accepted batch per object deterministically. MES selects every accepted
logical input version and collapses identical Bronze replays before reading data. Domain dependency
order is lines, machines, products, orders, then events. The notebook supports `domain=all`,
`domain=atlas_erp`, and `domain=mes`, plus `processing_run_id`.

The executable rule IDs used are `DQ-CORE-001` through `DQ-CORE-007` and the existing
`DQ-PROD-001` through `DQ-PROD-006`. The CORE rules cover required values, parsing, enumerations,
references, duplicate/conflicting keys, temporal order, and numeric bounds. Critical failures are
excluded from conformed tables and receive a stable, hash-derived quarantine ID. No uncataloged
rule ID is emitted.

## Local validation

- Ruff check: passed.
- Ruff format check: passed (`43 files already formatted`).
- Python compile check: passed for `src`, `tests`, and `fabric/notebooks`.
- Pytest: `71 passed, 1 skipped, 1 warning in 63.94s` with `PYTHONPATH=src`.
- Skip: PostgreSQL integration because `ATLAS_ERP_TEST_DSN` was not configured.
- Warning: upstream Starlette/AnyIO `BlockingPortal` deprecation.
- `git diff --check`: passed; only Git line-ending conversion notices were printed before staging.
- Staged-diff secret scan before each checkpoint: no matches.

Python 3.13 was requested, but this host has no registered Python 3.13 interpreter. The available
project virtual environment is Python `3.12.14`; all reported Python checks ran there. No Python
3.13 result is claimed.

The focused tests prove deterministic audit selection, identical MES replay collapse, canonical
hashing, stable quarantine IDs, schema/metadata columns, reference/DQ intent, and MERGE
idempotency intent. They do not replace a Spark/Fabric rerun.

## Fabric tenant state

Workspace: `Industrial Data Platform - Lakehouse Analytics`
(`029313a7-3cbc-401c-a1fe-3ee41f001cd1`).

Notebook `nb_bronze_to_silver` (`77f29595-9676-4ef6-a914-620be4e872c4`) is attached to the
existing `lh_bronze` and `lh_silver` Lakehouses. The Silver MVP was executed successfully in Fabric.

The first successful run materialized:

| Table | Rows |
|---|---:|
| `production_lines` | 3 |
| `machines` | 12 |
| `products` | 8 |
| `production_orders` | 360 |
| `production_events` | 540 |
| `quarantine_records` | 145 |

The second identical run initially exposed a lazy Spark evaluation defect in conflict detection.
After the fix, it succeeded with the same six counts, including 145 quarantine rows. No duplicate
quarantine rows were created. This is tenant execution evidence for rerun idempotency of the current
AtlasERP + MES Silver MVP. Fabric run IDs were not available and are not fabricated here.

Two runtime issues were discovered and corrected manually in Fabric, then reconciled into source:

1. `/lakehouse/default/Files/...` produced a OneLake HTTP 400 response. Passing the audited relative
   `Files/...` path directly succeeded, so `_bronze_path()` now preserves that safe relative form.
2. `_mark_existing_event_conflicts()` dropped `_existing_key` before Spark materialized the lazy
   conflict expression. The helper now appends the failure first and drops both temporary columns
   afterward.

`pl_transform_bronze_to_silver` has not yet been created or executed.

## Remaining Fabric work

1. Create `pl_transform_bronze_to_silver` from `fabric/silver-pipeline-build-spec.md` with one
   Notebook activity, `domain=all`, and `processing_run_id=@pipeline().RunId`.
2. Execute the pipeline in Fabric and capture its run ID and stable output counts.
3. Review the completed Silver MVP and decide whether to move directly to Gold or extend Silver
   scope. Quality, MaintControl, and Technical Documents remain outside the implemented slice.

## Recommended next action

Create and execute `pl_transform_bronze_to_silver` using the checked-in build specification. After
capturing the pipeline run evidence, decide whether the next portfolio increment is Gold or an
extension of Silver scope.
