# Phase 5 Gold production handoff

## Current status

- Repository implementation: complete for the approved production MVP.
- Fabric notebook `nb_silver_to_gold_production`: published and successfully executed twice
  directly from the source-controlled implementation.
- Fabric pipeline `pl_transform_silver_to_gold`: created, validated with no errors, and
  successfully executed with one Notebook activity.
- Tenant execution and idempotency evidence: accepted on 2026-09-10/11.
- Power BI semantic model and report: not yet implemented at the Phase 5 handoff; subsequently
  implemented and validated in Phase 6.

Phase 5 may now be described as demonstrated in Fabric for the approved Gold production MVP. This
Phase 5 evidence does not itself extend to Power BI, planned-production metrics, OEE, or later
domains. Phase 6 Power BI evidence is recorded separately in
[`docs/power-bi/phase6-production-dashboard.md`](../power-bi/phase6-production-dashboard.md).

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

- [x] Publish `nb_silver_to_gold_production` from the source-controlled implementation.
- [x] Attach `lh_gold` as default and add `lh_silver`.
- [x] Execute the notebook twice unchanged and compare outputs.
- [x] Create and validate the independent one-activity pipeline.
- [x] Pass `processing_run_id = @pipeline().RunId` and execute the pipeline successfully.
- [x] Verify the final five-table Gold state, reconciled quantities, and order diagnostics.
- [x] Keep planned-production metrics and OEE outside the accepted MVP.

## Fabric items

| Item | Fabric item ID | Configuration |
|---|---|---|
| `nb_silver_to_gold_production` | `ba52532c-9e0a-41cc-9976-6c26cc737e03` | `lh_gold` default; `lh_silver` attached; `processing_run_id` parameter cell |
| `pl_transform_silver_to_gold` | `4b144484-ce80-493c-96ae-639b8aa9fe77` | One activity: `nb_transform_silver_to_gold_production` |

The activity references `nb_silver_to_gold_production` and passes the string parameter
`processing_run_id = @pipeline().RunId`.

## Direct notebook evidence

Both direct executions used the same unchanged notebook and Silver snapshot. Their different
generated processing IDs and identical published results demonstrate convergence for this MVP.

| Run | Completed (America/Sao_Paulo) | Transformation runtime | `processing_run_id` | Result |
|---|---|---:|---|---|
| Direct 1 | 2026-09-10 21:26:25 | 2 min 1 sec | `81172b89-abcb-43fa-a6cd-309a43e1fcdf` | `SUCCEEDED` / `PASSED` |
| Direct 2 | 2026-09-10 21:28:09 | 1 min 28 sec | `d0fe081b-dee3-41c8-9842-6826e7e43e4c` | `SUCCEEDED` / `PASSED` |

Direct run 1 exit value:

```json
{"gold_table_row_counts":{"dim_date":339,"dim_machine":12,"dim_product":8,"dim_production_line":3,"fact_production_event":540},"order_alignment_diagnostics":{"distinct_event_order_ids":12,"event_order_batch_mismatches":0,"event_order_line_mismatches":360,"event_order_product_mismatches":495,"event_orders_missing_from_orders":0,"events_outside_order_schedule":495,"orders_without_events":348,"planned_metrics_eligible":false},"processing_run_id":"81172b89-abcb-43fa-a6cd-309a43e1fcdf","silver_source_row_counts":{"machines":12,"production_events":540,"production_lines":3,"production_orders":360,"products":8},"status":"SUCCEEDED","total_accepted_quantity":53879,"total_produced_quantity":54949,"total_rejected_quantity":1070,"validation_status":"PASSED"}
```

Direct run 2 exit value:

```json
{"gold_table_row_counts":{"dim_date":339,"dim_machine":12,"dim_product":8,"dim_production_line":3,"fact_production_event":540},"order_alignment_diagnostics":{"distinct_event_order_ids":12,"event_order_batch_mismatches":0,"event_order_line_mismatches":360,"event_order_product_mismatches":495,"event_orders_missing_from_orders":0,"events_outside_order_schedule":495,"orders_without_events":348,"planned_metrics_eligible":false},"processing_run_id":"d0fe081b-dee3-41c8-9842-6826e7e43e4c","silver_source_row_counts":{"machines":12,"production_events":540,"production_lines":3,"production_orders":360,"products":8},"status":"SUCCEEDED","total_accepted_quantity":53879,"total_produced_quantity":54949,"total_rejected_quantity":1070,"validation_status":"PASSED"}
```

## Pipeline evidence

Pipeline validation reported no errors. The successful execution produced:

| Evidence | Observed value |
|---|---|
| Pipeline Run ID | `e6feb7a6-c38c-4e14-bc5c-7c69ea17e1cc` |
| Activity | `nb_transform_silver_to_gold_production` |
| Activity status | `Succeeded` |
| Activity duration | 1 min 51 sec |
| Notebook run ID | `db4ac55a-84f6-47c4-aa9a-e535bc68628c` |
| Notebook execution interval | `2026-09-11T00:48:44.6695522Z` to `2026-09-11T00:50:24.5254596Z` |
| Notebook execution duration | 107 seconds |
| Parameter traceability | `processing_run_id` equals the pipeline Run ID |

Successful pipeline notebook exit value:

```json
{"gold_table_row_counts":{"dim_date":339,"dim_machine":12,"dim_product":8,"dim_production_line":3,"fact_production_event":540},"order_alignment_diagnostics":{"distinct_event_order_ids":12,"event_order_batch_mismatches":0,"event_order_line_mismatches":360,"event_order_product_mismatches":495,"event_orders_missing_from_orders":0,"events_outside_order_schedule":495,"orders_without_events":348,"planned_metrics_eligible":false},"processing_run_id":"e6feb7a6-c38c-4e14-bc5c-7c69ea17e1cc","silver_source_row_counts":{"machines":12,"production_events":540,"production_lines":3,"production_orders":360,"products":8},"status":"SUCCEEDED","total_accepted_quantity":53879,"total_produced_quantity":54949,"total_rejected_quantity":1070,"validation_status":"PASSED"}
```

An earlier attempt, Run ID `028a6c69-b1ed-4c4f-9a12-ef7d90b0582f`, remained queued behind the
interactive Spark session and produced no activity output. It was cancelled after 17 min 38 sec;
the interactive session was released before the successful clean run above. This is operational
capacity evidence, not a Gold validation or transformation failure.

## Accepted final Gold state

| Gold table | Rows |
|---|---:|
| `dim_date` | 339 |
| `dim_product` | 8 |
| `dim_machine` | 12 |
| `dim_production_line` | 3 |
| `fact_production_event` | 540 |

The `lh_gold.dbo` Lakehouse view independently showed exactly these five tables and displayed
`dim_date` with 339 rows after the successful pipeline execution. The notebook's post-write reads
validated all five row counts, source-to-fact reconciliation, unique keys, dimension references,
machine/line agreement, quantity semantics, shift enumeration, and quantity totals.

| Reconciled metric | Value |
|---|---:|
| Produced quantity | 54,949 |
| Rejected quantity | 1,070 |
| Accepted quantity | 53,879 |

The order diagnostics make planned-production analytics ineligible: only 12 distinct event order
IDs were observed, 348 orders had no events, 360 event/order line comparisons mismatched, 495
product comparisons mismatched, and 495 events fell outside the joined order schedule. No event
order IDs were missing from `production_orders`, and no batch mismatches were observed. Planned
quantity, production attainment, and OEE therefore remain excluded.

## Known dashboard boundary

The Gold fact safely supports production, rejection, accepted output, rejection rate, event count,
and comparisons by operational date, product, machine, production line, and shift.

Planned quantity, attainment, and OEE must remain absent from tomorrow's dashboard. Unexpected
machine/line inconsistencies are a hard Gold blocker. Order-alignment diagnostic failures are a
blocker only for future order-plan analytics, not for the approved event-based dashboard.
