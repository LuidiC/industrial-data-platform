# Phase 3 execution evidence

This file records what was actually demonstrated in the Fabric tenant. It must not infer live
success from repository artifacts or planned configuration.

## Tenant execution status through 2026-09-09

| Check | Result | Evidence |
|---|---|---|
| SharePoint Online File PoC | Not executable; no pass claimed | No tenant site, library, folder, or representative source objects were supplied |
| OneLake demo staging fallback | Demonstrated for MES | `transport_source=onelake_demo_staging`; 2025-01 through 2026-01 source files were read from `Files/_demo_source_staging/mes` and copied byte-for-byte to immutable Bronze batches |
| `ingestion_audit` Delta table | Passed initialization | Notebook `a3f33829-2a79-460f-8b45-9cf25a355041` attached to `lh_bronze`; output `{"status":"READY","table":"ingestion_audit"}` at 2026-09-04 19:40:18 UTC |
| Six pipeline items | Created | MES, Quality, Technical Documents, and AtlasERP were subsequently accepted; MaintControl and the orchestrator remain |
| MES initial/rerun/new-month/conflict/replay | Passed in Fabric | Live run IDs and immutable Bronze/audit evidence are recorded below |
| Quality XLSX | Accepted in Fabric; run IDs still need capture here | Operator confirmed initial success and idempotent rerun; local structure/hash evidence remains below |
| Six technical PDFs | Accepted in Fabric; run IDs still need capture here | Operator confirmed initial success and idempotent rerun; no OCR or parsing was introduced |
| AtlasERP four-table snapshot | Accepted in Fabric; run IDs still need capture here | Operator confirmed 4 `SUCCEEDED` then 4 `SKIPPED_ALREADY_INGESTED`; source used PostgreSQL on host port 55433 through the installed gateway |
| MaintControl contract/fixtures | Local readiness passed; live snapshot pending | API contract includes bearer auth, pagination and inclusive occurrence-window filters; fixture counts are 180 work orders and 165 maintenance events |
| MaintControl local/API boundary | Passed locally on 2026-09-09 | Loopback API on port 8001 returned HTTP 200 for both endpoints and HTTP 401 for missing/invalid bearer tokens |
| MaintControl Quick Tunnel | Tool verified; public test blocked | Official `cloudflared` 2026.8.3 binary passed its published SHA-256 check in ignored `tmp/tools`; the execution environment blocked opening a public tunnel, so no HTTPS/Fabric success is claimed |

## Created Fabric items

| Item | Fabric item ID | State |
|---|---|---|
| `nb_bronze_ingestion_audit` | `a3f33829-2a79-460f-8b45-9cf25a355041` | Code loaded, parameter cell marked, Lakehouse attached, initialization passed |
| `pl_ingest_atlas_erp` | `5746b71f-32dc-4b1b-bfe0-fe2bfef633f6` | Implemented and accepted; run IDs pending capture in this file |
| `pl_ingest_mes` | `b9645bcc-46ac-42a7-9d91-60d085944a08` | Implemented, validated, and live acceptance-tested with OneLake demo staging |
| `pl_ingest_quality` | `9ee7b72b-2544-4296-8985-7ec1a7d4e64e` | Implemented and accepted; run IDs pending capture in this file |
| `pl_ingest_maintcontrol` | `3d68708a-8a58-4311-a716-ff398027c748` | Empty shell; not runnable |
| `pl_ingest_technical_documents` | `1cfe1200-0e62-49c9-8d38-f7522be548e9` | Implemented and accepted; run IDs pending capture in this file |
| `pl_ingest_all_sources` | `559fcda5-e92b-4014-a381-3981fcb0c6fe` | Empty shell; not runnable |

The workspace identity was enabled and granted only the Contributor workspace role. Notebook
connection `cn_notebook_workspace_identity` (`d853a481-85b4-489d-bdb4-c44c2128d36c`) uses
Workspace Identity authentication. Its isolated activity test succeeded as run
`f819ac29-4aed-43f7-8eda-f7b6312c9956`. No service principal, application registration, client
secret, or Key Vault was created.

Local fixture checks remain reproducible validation evidence rather than substitutes for Fabric
runs. MES has the complete live evidence below. Quality, Technical Documents, and AtlasERP are
recorded as operator-confirmed acceptance until their exact Fabric run IDs are recovered; this file
does not invent them. MaintControl still has no successful source-pipeline Bronze landing.

## MES live acceptance on 2026-09-07

| Scenario | Fabric run ID | Result and evidence |
|---|---|---|
| Initial 12-month load | `cd048f50-036e-49f9-803d-6598b6ab13f4` | Succeeded; 12 copies and 12 `SUCCEEDED` rows for 2025-01 through 2025-12 |
| Identical rerun | `7b99834c-ee13-4e08-84d9-fd1aaf49399b` | Succeeded; 12 `SKIPPED_ALREADY_INGESTED`, zero copies |
| New month 2026-01 | `b9b2ea0e-5f3f-47fe-add3-41a57857d100` | Succeeded; 13 candidates, 12 skips, exactly one new `SUCCEEDED` batch `b9b2ea0e-5f3f-47fe-add3-41a57857d100-202601`; source and destination SHA-256 `547647c0ee80861ed8635d837cb6a9ca87b521504a2c3ce3b14a6108c990370d` |
| Controlled conflict, 2025-01 | `642ad6a3-6387-4694-8f73-4a7b4173e673` | Failed as designed; one `CONFLICT_SOURCE_CHANGED`, 12 skips, zero copies. The staged file was restored to 8,401 bytes and SHA-256 `9f415e92befc7b1cd3907da03875f83172235ced18eadef89bfa029f5ccadcd5` |
| Explicit replay, 2025-01 | `abdb6f92-7e90-42d5-90d8-fe62ec8d8b2f` | Succeeded; one `SUCCEEDED_REPLAY` batch `abdb6f92-7e90-42d5-90d8-fe62ec8d8b2f-202501`, linked to original batch `cd048f50-036e-49f9-803d-6598b6ab13f4-202501`; both files have SHA-256 `9f415e92befc7b1cd3907da03875f83172235ced18eadef89bfa029f5ccadcd5` |

After acceptance, MES Bronze contains 14 CSV files: 12 original 2025 batches, one normal 2026-01
batch, and one replay batch. The staging folder contains 13 canonical source files.

The audit status totals after these runs are 13 `SUCCEEDED`, 36
`SKIPPED_ALREADY_INGESTED`, 37 `CONFLICT_SOURCE_CHANGED`, and one `SUCCEEDED_REPLAY`. Of the 37
conflicts, exactly one is the controlled acceptance test above. The other 36 belong to diagnostic
runs `2d18199e-7ed5-4bd0-b267-3f85f4062f4e`,
`c4243b24-68dc-4dd9-831b-a684946d6fad`, and
`4cd513e0-cd86-4238-a211-eb9288faf126`, performed while aligning the published notebook's hash
behavior. They remain immutable historical evidence and must not be deleted, rewritten, or counted
as the controlled conflict test.

Update this table immediately after each portal run with UTC run time, Fabric run ID, counts, hashes,
selected `transport_source`, and any sanitized error code. Do not store credentials or tokens.
