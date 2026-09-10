# Phase 4A/4B Fabric pipeline build specification

## Boundary

Build one independent Data Factory pipeline named `pl_transform_bronze_to_silver`. It transforms
accepted AtlasERP and MES Bronze inputs only. Do not invoke or alter `pl_ingest_all_sources`, and do
not add Quality, MaintControl, Technical Documents, Gold, or Power BI activities.

This document is a portal build recipe, not invented pipeline-export JSON. A published item or
repository notebook is not execution evidence.

## Notebook item

Create or update a Fabric notebook named `nb_bronze_to_silver` from
`notebooks/nb_bronze_to_silver.py`.

1. Use Fabric Runtime 2.0 where available for the workspace.
2. Attach `lh_bronze` as the default Lakehouse. This is required because audited destinations are
   relative `Files/...` paths and resolve beneath `/lakehouse/default`.
3. Add `lh_silver` to the notebook and confirm schema-enabled table access through
   `lh_silver.dbo`.
4. Mark `domain` and `processing_run_id` in the first cell as parameters.
5. Do not change the source constants unless the tenant uses different, verified Lakehouse/schema
   names.

The notebook reads `lh_bronze.dbo.ingestion_audit`, accepts only `SUCCEEDED` and
`SUCCEEDED_REPLAY`, and writes these Delta tables:

```text
lh_silver.dbo.production_lines
lh_silver.dbo.machines
lh_silver.dbo.products
lh_silver.dbo.production_orders
lh_silver.dbo.production_events
lh_silver.dbo.quarantine_records
```

## Pipeline graph

The pipeline has no parameters for this MVP and exactly one Notebook activity:

```text
nb_transform_bronze_to_silver
```

Configure the activity as follows:

| Setting | Value |
|---|---|
| Notebook | `nb_bronze_to_silver` |
| Connection | Existing approved same-workspace notebook connection |
| Wait for completion | Enabled |
| Base parameter `domain` | `all` |
| Base parameter `processing_run_id` | `@pipeline().RunId` |
| Secure input/output | Not required; this flow carries no credential |

Use the same workspace-identity notebook connection pattern already demonstrated for Phase 3.
The identity requires read access to `lh_bronze` and create/update access to `lh_silver`; do not
introduce credentials in the pipeline or notebook.

## Validation run

Run the pipeline once, save its run ID, and capture the notebook exit JSON. Validate in the
Lakehouse or SQL endpoint:

1. All six tables exist in `lh_silver.dbo`.
2. Every conformed table has its documented business key and six technical columns.
3. Business keys are unique.
4. All accepted machine `line_id` values resolve to `production_lines`.
5. All accepted order `product_id` and `line_id` values resolve to their parents.
6. All accepted MES machine, order, product, and line references resolve.
7. Critical anomaly records are absent from `production_events` and present in quarantine with a
   cataloged rule ID.
8. `processed_at` and operational timestamps are UTC Spark timestamps; `shift_business_date` is a
   date.

Run the same pipeline again without changing Bronze. Capture the second run ID and compare table
counts with the first run. Business counts and `quarantine_records` counts must remain identical.
Master/order MERGEs must not update identical hashes, and the event/quarantine MERGEs must insert
nothing.

If the three-part table names or additional Lakehouse attachment do not resolve, stop without
changing the notebook semantics. Confirm that Lakehouse schemas are enabled and that both existing
Lakehouses are attached to the notebook before considering a tenant-specific name adjustment.
