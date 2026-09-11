# Phase 5 Gold production handoff

## Current status

- Repository implementation: complete for the approved production MVP.
- Fabric notebook item: not yet created or updated from this Phase 5 source.
- Fabric pipeline `pl_transform_silver_to_gold`: not yet created.
- Tenant execution and idempotency evidence: not yet available.
- Power BI semantic model and report: not yet implemented.

Do not describe Phase 5 as demonstrated in Fabric until the validation runs in
`fabric/gold-pipeline-build-spec.md` have completed and their observed evidence is recorded here.

## Source-controlled artifacts

- `fabric/notebooks/nb_silver_to_gold_production.py`
- `fabric/gold-pipeline-build-spec.md`
- `docs/gold/phase5-production-mvp.md`
- focused repository tests for the Gold boundary and notebook source

## Implemented repository model

The notebook defines these Delta targets:

| Table | Grain |
|---|---|
| `lh_gold.dbo.dim_date` | One continuous operational business date |
| `lh_gold.dbo.dim_product` | One current product |
| `lh_gold.dbo.dim_machine` | One current machine |
| `lh_gold.dbo.dim_production_line` | One current production line |
| `lh_gold.dbo.fact_production_event` | One accepted Silver production event |

The event fact physically stores produced, rejected, and accepted quantities. Rejection rate,
event count, and average produced per event remain semantic-model measures.

## Accepted Silver starting evidence

The previously demonstrated Phase 4 tenant snapshot contains:

| Silver table | Rows |
|---|---:|
| `production_lines` | 3 |
| `machines` | 12 |
| `products` | 8 |
| `production_orders` | 360 |
| `production_events` | 540 |
| `quarantine_records` | 145 |

These values are expected starting evidence, not hard-coded Gold transformation rules. Gold must
reconcile dynamically to the Silver snapshot it reads.

## Tenant execution checklist

1. Create `nb_silver_to_gold_production` from the source-controlled notebook.
2. Attach `lh_gold` as default and add `lh_silver`, both with schema support.
3. Create the one-activity independent pipeline from the manual build specification.
4. Run the pipeline and preserve its Run ID and complete notebook exit JSON.
5. Confirm the five table counts, unique keys, relationships, and quantity totals.
6. Review and record every order-alignment diagnostic. Do not enable planned metrics.
7. Run the pipeline unchanged a second time and compare keys, counts, totals, and diagnostics.
8. Record the two Run IDs, runtimes, results, and observed values in this handoff.
9. Only then describe the Phase 5 Gold path as demonstrated in Fabric.
10. Build the Power BI semantic model with the documented single-direction star relationships.

## Known dashboard boundary

The Gold fact safely supports production, rejection, accepted output, rejection rate, event count,
and comparisons by operational date, product, machine, production line, and shift.

Planned quantity, attainment, and OEE must remain absent from tomorrow's dashboard. Unexpected
machine/line inconsistencies are a hard Gold blocker. Order-alignment diagnostic failures are a
blocker only for future order-plan analytics, not for the approved event-based dashboard.
