# Phase 4A/4B Silver production slice

## Status and scope

Phase 4A/4B is implemented in repository code for AtlasERP and MES. It is not described as
demonstrated in Microsoft Fabric until a tenant execution is recorded. Quality, MaintControl,
Technical Documents, Gold, and Power BI remain outside this slice.

Silver contains typed, standardized, deduplicated, quality-controlled records at source grain.
Facts, dimensions, KPIs, aggregates, and consumer-facing analytical relationships belong in Gold.

## Implemented tables

| Table | Business key | Grain | Write behavior |
|---|---|---|---|
| `production_lines` | `line_id` | One production line | MERGE; update when the canonical record hash changes |
| `machines` | `machine_id` | One machine | MERGE; update when the canonical record hash changes |
| `products` | `product_id` | One product | MERGE; update when the canonical record hash changes |
| `production_orders` | `production_order_id` | One production order and lot | MERGE; update when the canonical record hash changes |
| `production_events` | `event_id` | One completed machine/order interval | Insert-safe MERGE; existing identical rows are unchanged |
| `quarantine_records` | `quarantine_id` | One source-record/rule failure | Insert-safe MERGE by deterministic identity |

Every conformed table carries only these shared technical fields:

- `source_system`
- `source_object`
- `source_batch_id`
- `source_file`
- `processed_at` in UTC
- `record_hash` over canonical business columns

## Bronze selection and dependency order

`lh_bronze.dbo.ingestion_audit` is the control plane. Failed, started, skipped, and conflict rows
are never read as Silver inputs.

- AtlasERP selects the latest `SUCCEEDED` or `SUCCEEDED_REPLAY` audit row independently for each
  required object. Missing accepted evidence fails before transformation.
- MES selects every accepted logical file version. An identical replay with the same source
  identity and content hash collapses to the original successful input before file reading.
- Audited destination paths are validated as relative paths below `Files` before they resolve
  beneath the default `lh_bronze` Lakehouse mount.

The notebook processes `production_lines`, `machines`, `products`, `production_orders`, and then
`production_events`. This makes line, product, order, and machine references available before MES
validation.

## Standardization and data quality

The notebook uses explicit Spark schemas and the source fields declared in the versioned contracts.
It trims strings, turns empty strings into null, uppercases documented identifiers, canonicalizes
enumerated text, stores timestamps in UTC, stores the shift business date as a Spark date, and uses
integral quantity fields. It does not create unknown members, sentinel dates, or corrected Bronze
files.

The Phase 4 slice executes the existing `DQ-PROD-*` rules and the minimal cataloged `DQ-CORE-*`
rules needed for required values, type conversion, enumerations, references, uniqueness, temporal
ordering, and numeric bounds. Critical failures are removed from the conformed output and written
to `quarantine_records` with the original JSON row and source context.

Duplicate handling is deterministic. The canonical occurrence remains eligible for Silver and
later occurrences are quarantined. An event whose key already exists with the same record hash is
a no-op; the same key with a different payload is quarantined. The deterministic quarantine hash
includes the source batch, row locator, rule, and reason, so an identical rerun does not duplicate
rejections.

## Notebook execution

Source: `fabric/notebooks/nb_bronze_to_silver.py`

Parameters:

| Parameter | Supported value | Purpose |
|---|---|---|
| `domain` | `all`, `atlas_erp`, or `mes` | Selects the explicit domain functions to execute |
| `processing_run_id` | Non-secret pipeline run ID | Correlates quarantine and notebook output with orchestration |

Attach `lh_bronze` as the default Lakehouse so its audited `Files/...` paths resolve under
`/lakehouse/default`. Add `lh_silver` to the notebook and retain schema support so the notebook can
write `lh_silver.dbo.*`. Set the Spark session time zone to UTC; the notebook also enforces this at
runtime.

For the MVP pipeline, use one notebook invocation with `domain=all` and
`processing_run_id=@pipeline().RunId`. The notebook returns table-level valid input, quarantine
failure, and resulting Silver counts. Run it twice against unchanged Bronze and verify that all
business-table and quarantine counts remain unchanged.

The exact independent pipeline build recipe is in
[`fabric/silver-pipeline-build-spec.md`](../../fabric/silver-pipeline-build-spec.md).

## Repository validation versus tenant evidence

Repository tests validate contracts, deterministic input selection, replay collapse, canonical
hash stability, quarantine identity stability, declared DQ behavior, and Delta merge intent. They
do not execute Spark or prove that a Fabric item ran. Record tenant run IDs, table counts, reference
checks, and rerun results in the Phase 4 handoff only after observing them.
