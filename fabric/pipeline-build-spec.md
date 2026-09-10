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
`parent_execution_id`. Dynamic inventory accepts only `quality_department_2025.xlsx` from
`Files/_demo_source_staging/quality`. The candidate passes `source_path`; the notebook calculates
source size and SHA-256 for `onelake_demo_staging`. A technical check requires worksheets
`Inspections`, `DefectTypes`, and `Targets`; it does not apply business validation or rewrite cells.
Copy uses binary mode with binary consistency verification into:

```text
Files/raw/quality/quality_department/source_period=<YYYY>/batch_id=<batch-id>/<file-name>
```

## `pl_ingest_technical_documents`

Parameters: `transport_source`, `source_root`, `document_type` (optional), and
`parent_execution_id`. Inventory includes only `.pdf`; each source file is one audit attempt. Copy
uses binary mode with binary consistency verification into:

```text
Files/raw/technical_documents/<document-type>/source_period=<YYYY-QN>/batch_id=<batch-id>/<file-name>
```

Dynamic discovery accepts `maintenance_report_YYYY_qN.pdf` and
`quality_bulletin_YYYY_qN.pdf`, with `N` from 1 through 4. It derives document type and
`source_period=YYYY-QN`, passes the staging `source_path`, and uses the notebook-computed source
hash/size. No OCR, text extraction, parsing, or business interpretation is performed.

## `pl_ingest_atlas_erp`

Parameters: `extract_date` (UTC date by default), `parent_execution_id`, and optional
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
Files/raw/atlas_erp/<table>/extract_date=<YYYY-MM-DD>/batch_id=<batch-id>/<table>.parquet
```

The synthetic database must be held stable for the whole demonstration extraction. Four independent
queries are not represented as a transactional point-in-time snapshot for a mutable enterprise
database. Production reassessment may select CDC, a database-exported snapshot, or transactional
orchestration; none is added for this stable synthetic demonstration.

## `pl_ingest_maintcontrol`

Parameters: `base_url`, `bearer_token`, `transport_source` (default `maintcontrol_https`),
`extract_date`, `occurred_from`, `occurred_to`, `page_size` (default `500`),
`force_reprocess` (default `false`), `replay_of_batch_id` (optional), and
`parent_execution_id`. Mark `base_url` and `bearer_token` secure;
populate them from externally managed values, never source or logs. For the authorized demo, the
base URL is the current ephemeral Cloudflare Quick Tunnel URL and the truthful transport value is
`maintcontrol_https`. Neither value is committed.

The accepted published Copy selects `cn_rest_maintcontrol_quick_tunnel_tmp 1447551`, with the
current HTTPS base URL, no gateway, and Anonymous connector authentication. Despite its legacy
suffix, this connection is a live dependency. Update it for each new Quick Tunnel session.
Authentication of the source itself is the pipeline's bearer header. Mark the Copy activity
`secureInput=true` and `secureOutput=true`; do not place the header in audit details or pipeline
annotations. The `base_url` parameter records which ephemeral origin a run targeted, while the
Fabric connection must be kept in sync with it.

Use these parameters and variables:

| Name | Type/default | Purpose |
|---|---|---|
| `base_url` | String, no committed default | Current `https://*.trycloudflare.com` URL |
| `bearer_token` | String, no default | Runtime-only token; treat as secure |
| `transport_source` | String, `maintcontrol_https` | Truthful transport recorded in audit |
| `extract_date` | String, current UTC date supplied at invocation | Stable snapshot identity for a run/rerun pair |
| `occurred_from` | String, `2025-01-01T00:00:00-03:00` | Inclusive demo window start |
| `occurred_to` | String, `2025-12-31T23:59:59-03:00` | Inclusive demo window end |
| `page_size` | String, `500` | Maximum supported API page size; the REST URL expression consumes it as text |
| `force_reprocess` | Boolean, `false` | Must remain false for Phase 3 MaintControl acceptance |
| `replay_of_batch_id` | String, empty | Reserved; non-file replay is not accepted in Phase 3 |
| `parent_execution_id` | String, empty | Parent pipeline run ID when orchestrated |
| `maintcontrol_candidates` | Array | Two preflight candidates |
| `copy_results` | Array | Batched finalize input |
| `copy_failed` | Boolean, `false` | Final failure marker |

The exact accepted top-level graph is:

```text
append_candidate_work_orders
  -> append_candidate_maintenance_events
  -> nb_preflight_maintcontrol
  -> filter_blocking_maintcontrol
  -> filter_ingest_maintcontrol
  -> copy_ingest_maintcontrol (sequential ForEach)
  -> nb_finalize_maintcontrol
  -> if_fail_maintcontrol
```

The two Append Variable activities add one object each to `maintcontrol_candidates`. Fabric's
expression editor/runtime rejected the earlier single Set Variable plus `createArray` approach, so
it is not the accepted implementation. For `work_orders`, append:

```json
{
  "execution_id": "@pipeline().RunId",
  "parent_execution_id": "@if(empty(pipeline().parameters.parent_execution_id),null,pipeline().parameters.parent_execution_id)",
  "pipeline_name": "pl_ingest_maintcontrol",
  "source_system": "maintcontrol",
  "source_object": "work_orders",
  "source_identity_key": "maintcontrol|work_orders|<extract_date>",
  "source_file": "work_orders_<extract_date>.json",
  "source_period": "<extract_date>",
  "transport_source": "@pipeline().parameters.transport_source",
  "batch_id": "<pipeline-run-id>-work-orders",
  "destination_path": "Files/raw/maintcontrol/work_orders/extract_date=<extract_date>/batch_id=<batch-id>/work_orders_<extract_date>.json",
  "force_reprocess": "@pipeline().parameters.force_reprocess",
  "replay_of_batch_id": null,
  "extract_window_start": "<occurred_from>",
  "extract_window_end": "<occurred_to>",
  "details": {"endpoint":"work-orders","snapshot_identity_model":"stable_demo_window"}
}
```

The `maintenance_events` object uses the same fields with `maintenance_events`, endpoint
`maintenance-events`, and batch suffix `maintenance-events`. Do not supply `content_sha256` or
`source_size_bytes`: this transport uses snapshot-identity idempotency, not source-content change
detection. For Phase 3 acceptance, reject or fail validation when `force_reprocess=true` or
`replay_of_batch_id` is nonempty: replay for this non-file transport is not supported or claimed.
The notebook mappings are:

| Activity | `mode` | `payload_json` | `copy_results_json` | `stale_after_hours` |
|---|---|---|---|---|
| `nb_preflight_maintcontrol` | `preflight` | `@string(variables('maintcontrol_candidates'))` | `[]` | `2` |
| `nb_finalize_maintcontrol` | `finalize` | `[]` | `@string(variables('copy_results'))` | `2` |

Both notebook activities use `nb_bronze_ingestion_audit`, the default `lh_bronze`, and
`cn_notebook_workspace_identity`. Parse the preflight plan from
`@json(activity('nb_preflight_maintcontrol').output.result.exitValue).plan`. Filter INGEST with
`@equals(item().action,'INGEST')`; filter blocking decisions with
`@or(equals(item().action,'CONFLICT'),equals(item().action,'BLOCK'))`.

`copy_ingest_maintcontrol` iterates sequentially over the INGEST filter. Its REST Copy uses the
accepted demo connection, GET, a relative URL based on `item().details.endpoint`, the two encoded
occurrence-window query parameters, and `page_size`. Supply the runtime header as
`Authorization = @concat('Bearer ',pipeline().parameters.bearer_token)`. Configure pagination rule
`QueryParameters.cursor = $.pagination.next_cursor`; the connector stops when that JSONPath is
null. Use a JSON sink in `lh_bronze` at the exact `item().destination_path`, with no schema mapping,
business transformation, or Silver table.

The synthetic acceptance data contains 180 work orders and 165 maintenance events, so
`page_size=500` produces one complete source envelope per object. Before accepting a different or
mutable source, verify how Fabric serializes multiple REST response envelopes. Use the documented
notebook pagination fallback only if live evidence shows that Copy cannot preserve the required raw
representation.

Inside the ForEach, `copy_maintcontrol_object` routes success to `append_copy_success` and failure
to `append_copy_failure`, then `set_copy_failed`. The appended result contains `audit_id`,
`destination_path`, status, available document/file metrics, null or sanitized error fields, and
sanitized details. Finalize once after the ForEach completes. `if_fail_maintcontrol` contains a Fail
activity in its true branch and evaluates the logical OR of `copy_failed` and a nonempty blocking
filter; its false branch is empty.

For each endpoint, Copy performs HTTPS `GET`, sends `Authorization: Bearer <token>`, and uses
`cursor` pagination until `pagination.next_cursor` is null. Both endpoints send
`occurred_from`/`occurred_to`; the inclusive window applies to `opened_at` for work orders and
`started_at` for maintenance events. Each complete endpoint response is preserved as JSON under:

```text
Files/raw/maintcontrol/<endpoint>/extract_date=<YYYY-MM-DD>/batch_id=<batch-id>/
```

The synthetic API must be held stable during each full extraction. This does not claim a
transactional snapshot for a mutable production API. If the first authorized live test shows that
the connector does not preserve the required paginated envelopes, implement the documented batched
notebook-loop fallback only then; do not assume it before evidence exists.

## `pl_ingest_all_sources`

The accepted orchestrator has five String parameters:
`maintcontrol_base_url`, `maintcontrol_bearer_token`, `maintcontrol_occurred_from`,
`maintcontrol_occurred_to`, and `maintcontrol_page_size`. It contains five direct Invoke Pipeline
activities, chained on success in this order:

```text
invoke_atlas_erp
  -> invoke_mes
  -> invoke_quality
  -> invoke_maintcontrol
  -> invoke_technical_documents
```

Every activity uses the same selected Fabric pipeline connection, waits for child completion, and
passes `parent_execution_id=@pipeline().RunId`. MaintControl additionally receives the five matching
orchestrator parameters; accepted child defaults remain unchanged otherwise. A child failure breaks
the succeeded-dependency chain, so later sources do not run. The orchestrator contains no notebook,
Copy, condition, or Silver activity.

The connection was created by the operator as `cn_fabric_pipeline_invoke`; the current published
activity selector displays `FabricDataPipelines 1447551`. Preserve the selected connection ID used
by the accepted run rather than replacing it based only on either label.

## Connections

| Name | Connector | Authentication and purpose |
|---|---|---|
| `cn_spo_phase3_files` | SharePoint Online File (Preview) | Organizational/workspace identity; preferred CSV/XLSX/PDF source, only after PoC |
| `cn_notebook_workspace_identity` | Notebook | Workspace Identity; same-workspace audit notebook activities |
| `cn_pg_atlas_erp_gateway` | PostgreSQL | On-premises gateway; rotated read-only `atlas_fabric_reader` credential |
| `cn_rest_maintcontrol_quick_tunnel_tmp` | REST | Accepted demo-only HTTPS connection; ephemeral URL must be updated for each authorized tunnel |
| `cn_fabric_pipeline_invoke` / selected `FabricDataPipelines 1447551` | Fabric data pipelines | Organizational account; accepted same-workspace child invocation selection |

The `lh_bronze` workspace item is selected directly as the Copy sink and notebook default
Lakehouse. No connection secret belongs in Git. Native Fabric Git Integration is a should-have
follow-up and is not a Phase 3 completion dependency.
