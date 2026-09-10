# Phase 3 Fabric pipeline build specification

## Shared orchestration pattern

Every source pipeline uses at most two invocations of `nb_bronze_ingestion_audit`:

1. `Preflight audit` receives one JSON array for all source files/objects in the run. It atomically
   records `STARTED` attempts and terminal skip/conflict decisions.
2. A sequential `ForEach` runs the required Copy activities only for plan entries whose action is
   `INGEST`. Copy outputs are accumulated as a compact JSON result array.
3. `Finalize audit` hashes the landed artifacts and finalizes all `STARTED` rows in one notebook
   invocation. Its failure path leaves `STARTED`; a later preflight changes attempts at least two
   hours old to `FAILED`/`STALE_STARTED` before planning new work.
4. An `If Condition` fails the pipeline after finalization when any copy failed or a conflict/block
   was returned. Pipelines for the same source are not run concurrently.

This preserves an audit grain of one source file/object attempt without one Spark startup per
object.

## `pl_ingest_mes`

Parameters: `transport_source`, `source_root`, `period` (optional), `source_file` (optional),
`force_reprocess` (default `false`), `replay_of_batch_id` (optional), and
`parent_execution_id` (optional).

For `transport_source=onelake_demo_staging`, every candidate also supplies `source_path` as a
Lakehouse-relative POSIX path below `Files/_demo_source_staging`, for example
`Files/_demo_source_staging/mes/production_events_2025_01.csv`. The audit notebook resolves and
validates this path below `/lakehouse/default`, rejects traversal, missing paths, and non-files,
then calculates the source file's content-only SHA-256 and size before making the idempotency
decision. Pipeline-provided `content_sha256` and `source_size_bytes` are ignored for this transport.
Other transports remain responsible for supplying those two metadata values externally.

Inventory only files matching `production_events_YYYY_MM.csv` (or the accepted hyphenated period
variant); never select
`metadata/anomaly_manifest.json`. The identity is
`mes|production_events|<YYYY-MM>|<file-name>`. The target is:

```text
Files/raw/mes/production_events/source_period=<YYYY-MM>/batch_id=<batch-id>/<file-name>
```

A same-name/same-period/same-hash rerun is skipped. A changed hash for that identity conflicts. A
new period loads. A replay requires `force_reprocess=true`, the exact file and period, and the
successful source `batch_id`; it writes a new batch and finishes as `SUCCEEDED_REPLAY`.

The MES candidate payload sent to batched preflight is:

```json
{
  "execution_id": "<pipeline-run-id>",
  "parent_execution_id": null,
  "pipeline_name": "pl_ingest_mes",
  "source_system": "mes",
  "source_object": "production_events",
  "source_identity_key": "mes|production_events|2025-01|production_events_2025_01.csv",
  "source_file": "production_events_2025_01.csv",
  "source_period": "2025-01",
  "source_path": "Files/_demo_source_staging/mes/production_events_2025_01.csv",
  "transport_source": "onelake_demo_staging",
  "destination_path": "Files/raw/mes/production_events/source_period=2025-01/batch_id=<batch-id>/production_events_2025_01.csv",
  "batch_id": "<batch-id>",
  "force_reprocess": false,
  "replay_of_batch_id": null,
  "details": {}
}
```

Do not populate `content_sha256` or `source_size_bytes` for this transport; preflight calculates
both authoritatively. Finalize independently hashes the successfully copied Bronze destination.

## `pl_ingest_quality`

Parameters: `transport_source`, `source_root`, `source_file`, `source_period`, and
`parent_execution_id`. Preflight requires extension `.xlsx`, exact workbook name, size, modified
time, and source hash. A metadata/structure check requires worksheets `Inspections`, `DefectTypes`,
and `Targets`; it does not apply business validation or rewrite cells. Copy uses binary mode with
binary consistency verification into:

```text
Files/raw/quality/quality_department/source_period=<YYYY>/batch_id=<batch-id>/<file-name>
```

## `pl_ingest_technical_documents`

Parameters: `transport_source`, `source_root`, `document_type` (optional), and
`parent_execution_id`. Inventory includes only `.pdf`; each source file is one audit attempt. Copy
uses binary mode with binary consistency verification into:

```text
Files/raw/technical_documents/<document-type>/batch_id=<batch-id>/<file-name>
```

No OCR, text extraction, parsing, or business interpretation is performed.

## `pl_ingest_atlas_erp`

Parameters: `snapshot_date` (UTC date by default), `parent_execution_id`, and optional
`table_filter`. A sequential `ForEach` executes four ordered full-extraction queries through the
on-premises data gateway using a read-only PostgreSQL account:

```sql
SELECT * FROM atlas_erp.production_lines ORDER BY line_id;
SELECT * FROM atlas_erp.machines ORDER BY machine_id;
SELECT * FROM atlas_erp.products ORDER BY product_id;
SELECT * FROM atlas_erp.production_orders ORDER BY production_order_id;
```

Each table is a separate audit attempt and lands Parquet at:

```text
Files/raw/atlas_erp/<table>/snapshot_date=<YYYY-MM-DD>/batch_id=<batch-id>/<table>.parquet
```

The synthetic database must be held stable for the whole demonstration extraction. Four independent
queries are not represented as a transactional point-in-time snapshot for a mutable enterprise
database. Production reassessment may select CDC, a database-exported snapshot, or transactional
orchestration; none is added for this stable synthetic demonstration.

## `pl_ingest_maintcontrol`

Parameters: `base_url`, `bearer_token`, `extraction_date`, `occurred_from`, `occurred_to`,
`page_size` (default `500`), and `parent_execution_id`. Mark `base_url` and `bearer_token` secure;
populate them from externally managed values, never source or logs. The pipeline is build-ready but
live execution and connection creation remain pending tunnel-provider authorization.

For each endpoint, Copy performs HTTPS `GET`, sends `Authorization: Bearer <token>`, and uses
`cursor` pagination until `pagination.next_cursor` is null. Both endpoints send
`occurred_from`/`occurred_to`; the inclusive window applies to `opened_at` for work orders and
`started_at` for maintenance events. Each complete endpoint response is preserved as JSON under:

```text
Files/raw/maintcontrol/<endpoint>/extraction_date=<YYYY-MM-DD>/batch_id=<batch-id>/
```

The synthetic API must be held stable during each full extraction. This does not claim a
transactional snapshot for a mutable production API. If the first authorized live test shows that
the connector does not preserve the required paginated envelopes, implement the documented batched
notebook-loop fallback only then; do not assume it before evidence exists.

## `pl_ingest_all_sources`

Parameters: `run_atlas_erp`, `run_mes`, `run_quality`, `run_maintcontrol`,
`run_technical_documents`, and shared child parameters. Execute child pipelines in this order:
AtlasERP, MES, Quality, MaintControl, technical documents. MaintControl defaults to disabled while
its live connection is pending. The parent passes its pipeline run ID as `parent_execution_id` and
does not invoke the notebook itself.

## Connections

| Name | Connector | Authentication and purpose |
|---|---|---|
| `cn_spo_phase3_files` | SharePoint Online File (Preview) | Organizational/workspace identity; preferred CSV/XLSX/PDF source, only after PoC |
| `cn_pg_atlas_erp_gateway` | PostgreSQL | On-premises gateway; rotated read-only `atlas_fabric_reader` credential |
| `cn_rest_maintcontrol` | REST | HTTPS plus externally managed bearer token; create only after tunnel authorization |

The `lh_bronze` workspace item is selected directly as the Copy sink and notebook default
Lakehouse. No connection secret belongs in Git. Native Fabric Git Integration is a should-have
follow-up and is not a Phase 3 completion dependency.
