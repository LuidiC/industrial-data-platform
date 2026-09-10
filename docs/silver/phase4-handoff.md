# Phase 4A/4B handoff

## Snapshot

- Timestamp: `2026-09-10T16:03:13-03:00`
- Branch: `feat/phase-4-silver-transformation`
- Git status before this handoff file: clean
- Remote actions: none; no push, pull request, merge, or history rewrite was performed
- Scope stopped at Phase 4A (Silver foundation) and Phase 4B (AtlasERP + MES)

## Local checkpoints

- `7fe7ef3 feat: add AtlasERP and MES Silver transformation`
- `5662bd6 docs: document Silver production slice`
- This handoff is the final local documentation checkpoint.

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
- Pytest: `64 passed, 1 skipped, 1 warning in 63.66s` with `PYTHONPATH=src`.
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

Created notebook `nb_bronze_to_silver`
(`77f29595-9676-4ef6-a914-620be4e872c4`) and attached the existing `lh_bronze` and `lh_silver`
Lakehouses. The first cell contains `domain = "all"` and `processing_run_id = ""`, is marked as a
parameter cell, and the item shows `Salvo` in Fabric.

The complete source could not be transferred into the browser editor: the browser automation
security policy blocked the safe local-to-editor transfer mechanism. The second code cell therefore
remains empty. To avoid creating misleading evidence or executing partial code, the notebook was
not run and `pl_transform_bronze_to_silver` was not created. Consequently:

- Fabric run IDs: none
- Fabric row counts: not observed
- Tenant business-key/reference checks: not executed
- Tenant rerun/idempotency evidence: not available
- Silver Delta materialization in the tenant: not demonstrated

Repository implementation and local tests are complete; tenant execution remains planned, not
demonstrated.

## Manual Fabric completion

1. Open the created notebook at
   `https://app.fabric.microsoft.com/groups/029313a7-3cbc-401c-a1fe-3ee41f001cd1/synapsenotebooks/77f29595-9676-4ef6-a914-620be4e872c4?experience=fabric-developer`.
2. Confirm `lh_bronze` is the default Lakehouse and both `lh_bronze` and `lh_silver` are attached
   with schema-enabled access.
3. Keep the existing parameter cell. In the second code cell, paste
   `from __future__ import annotations`, then all content from the `# CELL` marker onward in
   `fabric/notebooks/nb_bronze_to_silver.py`. Save.
4. Run the notebook with `domain=all` and a new UUID in `processing_run_id`. Capture the exit JSON,
   Spark application/run ID, six table counts, uniqueness, and reference checks.
5. Run it again unchanged with a second UUID. Verify conformed and quarantine row counts are
   identical and capture the second run ID.
6. Follow `fabric/silver-pipeline-build-spec.md` to create the independent
   `pl_transform_bronze_to_silver` pipeline with one Notebook activity, `domain=all`, and
   `processing_run_id=@pipeline().RunId`. Execute it only after both direct notebook runs pass.

## Recommended next action

Complete steps 1-5 above first. If both Fabric runs succeed and counts remain stable, create and run
the pipeline using the checked-in build specification. Stop and diagnose any three-part-name,
schema, or runtime error before starting Gold or Power BI.
