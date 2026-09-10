# Phase 3 execution evidence

This file records only results observed in the Fabric tenant or explicitly confirmed during the
accepted execution. Repository artifacts alone are not evidence of a successful Fabric run.

## Acceptance status through 2026-09-10

Phase 3 source-to-Bronze ingestion is accepted. Five child pipelines, the sequential orchestrator,
the batched audit notebook, immutable raw landing, and idempotent reruns were demonstrated. No
Bronze-to-Silver work was introduced.

| Check | Result | Evidence |
|---|---|---|
| SharePoint Online File PoC | Not executable; no pass claimed | No tenant site/library/folder and representative files were supplied |
| OneLake demo staging fallback | Demonstrated | MES, Quality, and Technical Documents used `transport_source=onelake_demo_staging`; this is not described as SharePoint ingestion |
| `ingestion_audit` | Passed | `lh_bronze.dbo.ingestion_audit` is the only Phase 3 Delta table; the current view shows 133 rows and 29 columns |
| File-source integrity | Passed | Preflight hashed the staged source; finalize hashed the immutable destination; accepted XLSX/PDF/CSV copies reconciled byte-for-byte |
| AtlasERP | Passed | Four ordered full extracts through the PostgreSQL on-premises gateway; initial success and identity-based rerun skip |
| MaintControl | Passed for synthetic demo | Local and public bearer-auth checks passed; two raw JSON documents landed, then skipped on identical rerun |
| Orchestrator | Passed | All five child invokes succeeded sequentially and propagated the parent execution ID |

## Fabric items

| Item | Fabric item ID | Accepted state |
|---|---|---|
| `nb_bronze_ingestion_audit` | `a3f33829-2a79-460f-8b45-9cf25a355041` | Published, attached to `lh_bronze`, batched preflight/finalize working |
| `pl_ingest_atlas_erp` | `5746b71f-32dc-4b1b-bfe0-fe2bfef633f6` | Published and accepted |
| `pl_ingest_mes` | `b9645bcc-46ac-42a7-9d91-60d085944a08` | Published and accepted, including conflict and replay scenarios |
| `pl_ingest_quality` | `9ee7b72b-2544-4296-8985-7ec1a7d4e64e` | Published and accepted |
| `pl_ingest_maintcontrol` | `3d68708a-8a58-4311-a716-ff398027c748` | Published and accepted |
| `pl_ingest_technical_documents` | `1cfe1200-0e62-49c9-8d38-f7522be548e9` | Published and accepted |
| `pl_ingest_all_sources` | `559fcda5-e92b-4014-a381-3981fcb0c6fe` | Published and accepted |

Workspace Identity is enabled and has only the Contributor workspace role. Notebook connection
`cn_notebook_workspace_identity` (`d853a481-85b4-489d-bdb4-c44c2128d36c`) uses Workspace Identity;
its isolated activity test succeeded as run `f819ac29-4aed-43f7-8eda-f7b6312c9956`. No service
principal, application registration, client secret, or Key Vault was created.

## Accepted runs

### MES

| Scenario | Fabric run ID | Result |
|---|---|---|
| Initial 12-month load | `cd048f50-036e-49f9-803d-6598b6ab13f4` | 12 `SUCCEEDED`; 12 immutable 2025 CSV copies |
| Identical rerun | `7b99834c-ee13-4e08-84d9-fd1aaf49399b` | 12 `SKIPPED_ALREADY_INGESTED`; zero copies |
| New month 2026-01 | `b9b2ea0e-5f3f-47fe-add3-41a57857d100` | 12 skips and one `SUCCEEDED`; exactly one new batch |
| Controlled conflict, 2025-01 | `642ad6a3-6387-4694-8f73-4a7b4173e673` | Failed as designed; one `CONFLICT_SOURCE_CHANGED`, 12 skips, zero copies |
| Explicit replay, 2025-01 | `abdb6f92-7e90-42d5-90d8-fe62ec8d8b2f` | One `SUCCEEDED_REPLAY`; new immutable batch linked to the original |

The 2026-01 source and destination SHA-256 value is
`547647c0ee80861ed8635d837cb6a9ca87b521504a2c3ce3b14a6108c990370d`. The restored 2025-01 source,
original destination, and replay destination use
`9f415e92befc7b1cd3907da03875f83172235ced18eadef89bfa029f5ccadcd5`. The original batch is
`cd048f50-036e-49f9-803d-6598b6ab13f4-202501`; the replay batch is
`abdb6f92-7e90-42d5-90d8-fe62ec8d8b2f-202501`.

The other 36 `CONFLICT_SOURCE_CHANGED` rows are immutable diagnostic history from runs
`2d18199e-7ed5-4bd0-b267-3f85f4062f4e`, `c4243b24-68dc-4dd9-831b-a684946d6fad`, and
`4cd513e0-cd86-4238-a211-eb9288faf126`. They are not acceptance failures and were not deleted or
rewritten.

### Quality and Technical Documents

| Source | Initial run | Idempotent rerun | Result |
|---|---|---|---|
| Quality XLSX | `aa22e426-0f99-458c-bd50-4cc2c5b6c10d` | `26cbd2e1-cbdf-4173-80f3-33c48463c1e5` | One `SUCCEEDED`, then one skip; one immutable XLSX; required sheets confirmed |
| Six technical PDFs | `c72318b2-046e-4394-b095-0b9560b69318` | `db533917-0bdc-437b-881b-b9d8c3303c02` | Six `SUCCEEDED`, then six skips; six immutable PDFs; no OCR/parsing/transformation |

The Technical Documents rerun was the child invocation later used by the successful orchestrator;
it created no new PDF copies. Source and destination hashes reconciled for the accepted binary
copies; exact values were not separately transcribed into this file.

### AtlasERP

| Scenario | Fabric run ID | Result |
|---|---|---|
| Initial full snapshot | `1517a752-abfa-4074-9ebe-8a56f9b36071` | Four `SUCCEEDED`: `production_lines`, `machines`, `products`, `production_orders` |
| Identical full snapshot rerun | `8aff1231-7a9f-416d-b775-5af25f4a4545` | Four `SKIPPED_ALREADY_INGESTED`; no duplicate batches |

The synthetic PostgreSQL database was held stable. Four independent ordered queries do not claim a
transactional point-in-time snapshot for a mutable production database. The exact unaudited
connectivity-test file under `batch_id=test-production-lines` was deleted on 2026-09-10 after the
official sibling batch was positively distinguished. The empty diagnostic folder remains; no
official immutable batch was changed.

### MaintControl

| Scenario | Fabric run ID | Result |
|---|---|---|
| Initial full demo snapshot | `15864ed6-ab10-4578-8f84-9e1c31c95310` | Two `SUCCEEDED`; raw JSON for work orders and maintenance events |
| Identical rerun | `7d48039d-cf06-4a7d-b43a-379937bdf180` | Two `SKIPPED_ALREADY_INGESTED`; zero copies |
| Orchestrated rerun | `f3168680-cdd6-4049-903e-697aaed3e780` | Two skips with parent execution ID from the orchestrator |

Local and public HTTPS checks returned 200 with the valid synthetic bearer token and 401 for
missing/invalid tokens. The 2025 window contained 179 work orders and 165 maintenance events; the
unfiltered fixture contains 180 work orders. Fabric Copy reported one record/file at the raw JSON
document level. Those Copy metrics are not domain row counts.

The accepted source activity currently selects connection
`cn_rest_maintcontrol_quick_tunnel_tmp 1447551`. Despite the legacy `tmp` suffix, it is a published
pipeline dependency and was therefore retained. It is demo-only: its ephemeral URL must be replaced
for a new tunnel and must never be treated as stable configuration. The bearer token and URL are
not stored in this repository.

### Sequential orchestrator

Run `04585b6c-960b-41af-863d-ec4fea041bc3` succeeded on 2026-09-10. The five activities completed
in this order: AtlasERP, MES, Quality, MaintControl, Technical Documents. All waited for child
completion, and each child received `parent_execution_id=@pipeline().RunId`. The run produced only
expected idempotent skips and no duplicate ingestion.

The operator-created connection was named `cn_fabric_pipeline_invoke`; the current published
activity selector displays `FabricDataPipelines 1447551`. The evidence keeps both observed labels
instead of assuming they are the same connection record. All five published invokes use the same
selected connection and the accepted run succeeded.

## Current audit reconciliation

The current 133 rows reconcile exactly as follows:

| Status | Count | Interpretation |
|---|---:|---|
| `SUCCEEDED` | 26 | 13 MES + 1 Quality + 6 PDFs + 4 AtlasERP + 2 MaintControl |
| `SKIPPED_ALREADY_INGESTED` | 69 | Accepted reruns plus all 26 child attempts in the successful orchestrator |
| `CONFLICT_SOURCE_CHANGED` | 37 | 1 controlled acceptance conflict + 36 earlier MES diagnostics |
| `SUCCEEDED_REPLAY` | 1 | MES explicit replay |
| `STARTED` / `FAILED` | 0 | No unresolved attempt in the accepted final state |

## Repository validation

The final Python 3.13 validation result is recorded in `overnight-handoff.md`. The PostgreSQL
integration test is expected to skip when `ATLAS_ERP_TEST_DSN` is absent; this is reported as a
skip, not a failure.
