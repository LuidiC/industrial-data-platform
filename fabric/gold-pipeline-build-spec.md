# Phase 5 Gold production pipeline build specification

## Boundary

Build one independent Data Factory pipeline named `pl_transform_silver_to_gold`. It transforms only
the accepted Phase 4 production slice from `lh_silver` into the five-table production star schema
in `lh_gold`.

Do not invoke or alter `pl_transform_bronze_to_silver`. Do not add Quality, Maintenance, Technical
Documents, quarantine analytics, OEE, planned quantity, production attainment, Power BI refresh,
or deployment activities.

This document is a manual portal build recipe, not invented pipeline-export JSON. Repository code
and a published item are not Fabric execution evidence.

## Notebook item

Create a Fabric notebook named `nb_silver_to_gold_production` from
`notebooks/nb_silver_to_gold_production.py`.

1. Use Fabric Runtime 2.0 where available for the workspace.
2. Attach `lh_gold` as the default Lakehouse and keep schemas enabled.
3. Add `lh_silver` and confirm three-part reads through `lh_silver.dbo`.
4. Confirm three-part writes through `lh_gold.dbo`.
5. Mark `processing_run_id` in the first cell as a parameter.
6. Do not change the source or target constants unless the tenant uses different, verified
   Lakehouse/schema names.

The notebook reads:

```text
lh_silver.dbo.production_lines
lh_silver.dbo.machines
lh_silver.dbo.products
lh_silver.dbo.production_orders
lh_silver.dbo.production_events
```

It full-overwrites these Delta tables after all pre-publish hard validations pass:

```text
lh_gold.dbo.dim_date
lh_gold.dbo.dim_product
lh_gold.dbo.dim_machine
lh_gold.dbo.dim_production_line
lh_gold.dbo.fact_production_event
```

`production_orders` is read only for non-blocking alignment diagnostics. The notebook does not
publish planned quantity or production attainment.

## Pipeline graph

The pipeline has no parameters for this MVP and exactly one Notebook activity:

```text
pl_transform_silver_to_gold
    |
    +--> nb_transform_silver_to_gold_production
```

Configure the activity as follows:

| Setting | Value |
|---|---|
| Activity name | `nb_transform_silver_to_gold_production` |
| Notebook | `nb_silver_to_gold_production` |
| Connection | Existing approved same-workspace notebook connection |
| Wait for completion | Enabled |
| Base parameter `processing_run_id` | `@pipeline().RunId` |
| Secure input/output | Not required; this flow carries no credential |

Use workspace identity. It requires read access to `lh_silver` and create/update access to
`lh_gold`; do not place credentials in the pipeline or notebook.

## First validation run

Run the pipeline only after the accepted Silver pipeline has completed successfully. Save the
pipeline Run ID and notebook exit JSON, then confirm:

1. The activity and pipeline succeeded.
2. All five Gold tables exist in `lh_gold.dbo`.
3. The notebook reports `validation_status = PASSED`.
4. Gold dimension counts reconcile to their Silver sources.
5. `fact_production_event` count equals `production_events` count. The accepted starting snapshot
   is expected to produce 540 fact rows, but this count is evidence rather than transformation
   logic.
6. Produced and rejected totals exactly match Silver; accepted equals produced minus rejected.
7. Every fact key resolves and machine/line ownership agrees.
8. Order-alignment diagnostics are captured but no planned or attainment KPI is exposed.

## Idempotency validation run

Run the same pipeline again without changing Silver. Capture the second Run ID and notebook exit
JSON. Compare both runs:

- all five row counts are identical;
- fact business keys are identical and unique;
- produced, rejected, and accepted totals are identical;
- date boundaries and dimension members are identical;
- order-alignment diagnostics are identical.

A full overwrite creates a new Delta version, but the logical Gold contents must converge to the
same result. Do not describe the Gold pipeline as demonstrated until both tenant runs and their
evidence are recorded in the Phase 5 handoff.

If three-part table names fail, stop without changing the model. Confirm schema support and both
Lakehouse attachments before considering a tenant-specific name adjustment.
