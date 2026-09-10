# Phase 3 Bronze ingestion runbook

## Scope and status language

This runbook covers ingestion into `lh_bronze` only. It does not authorize transformation,
quarantine processing, Gold modeling, Power BI, OCR, CDC, mirroring, or tunneling software. A
resource is called *demonstrated* only when its Fabric run evidence is recorded in
`execution-evidence.md`; repository code or a portal item alone is not a successful ingestion run.

## File transport decision gate

Run the SharePoint Online File PoC before building CSV/XLSX/PDF production paths. The PoC passes
only when the current tenant can authenticate, Get Metadata, copy one representative CSV, XLSX,
and PDF without conversion, preserve name and size, return source metadata, and rerun reliably.

If any condition fails, stop the PoC and select the non-blocking fallback:

```text
lh_bronze/Files/_demo_source_staging/mes
lh_bronze/Files/_demo_source_staging/quality
lh_bronze/Files/_demo_source_staging/technical_documents
```

The source is then Lakehouse Files, `transport_source` is `onelake_demo_staging`, and the evidence
record must say that OneLake staging—not SharePoint—was demonstrated. Never ingest
`metadata/anomaly_manifest.json`.

For the 2026-09-04 execution, no tenant SharePoint site, library, folder, or representative source
objects were supplied, so the PoC could not establish a passing route. The non-blocking selection
is therefore `onelake_demo_staging`. That selection must not be described as a failed connector
test. It was subsequently demonstrated for MES by the live acceptance runs recorded on 2026-09-07
in `execution-evidence.md`; no SharePoint ingestion is claimed. Re-run the PoC if the missing
SharePoint coordinates are later provided.

## Deployment order

1. Confirm `lh_bronze` exists and its Files area is writable.
2. Create/import `nb_bronze_ingestion_audit`, attach `lh_bronze`, mark its parameter cell, and run
   `mode=initialize`. Confirm the only new Delta table is `ingestion_audit`.
3. Run the SharePoint PoC and record pass/fail plus selected transport.
4. Create the five child pipelines from `fabric/pipeline-build-spec.md`; validate each independently.
5. Create `pl_ingest_all_sources` with MaintControl disabled by default.
6. Run and record the scenarios below. Never run the same source pipeline concurrently.

## Audit operations

`ingestion_audit` uses UTC timestamps and one row per source file/object attempt. Allowed statuses
are `STARTED`, `SUCCEEDED`, `FAILED`, `SKIPPED_ALREADY_INGESTED`,
`CONFLICT_SOURCE_CHANGED`, and `SUCCEEDED_REPLAY`. The full schema is implemented in the notebook.

Preflight runs once per child pipeline. It checks identity and SHA-256, expires `STARTED` attempts
at least two hours old as `FAILED`/`STALE_STARTED`, blocks a fresh duplicate as
`FAILED`/`CONCURRENT_RUN`, and records terminal skip/conflict rows. Finalize runs once after all
copies, hashes destinations, and updates every planned attempt. If finalize fails, leave `STARTED`
unchanged so the next run can recover it visibly.

For file candidates whose `transport_source` is `onelake_demo_staging`, pass a `source_path` below
`Files/_demo_source_staging` using POSIX separators. Preflight resolves it relative to
`/lakehouse/default`, verifies it is an in-Lakehouse file, and calculates the source content
SHA-256 and byte size. These calculated values override any supplied hash or size. Missing files,
directories, absolute paths, backslash paths, traversal, and resolved paths outside the attached
Lakehouse fail preflight. Other transports may continue supplying their source hash and size.

For a single destination file, finalize calculates the same content-only SHA-256 from the Bronze
copy. It never substitutes destination hashing for the preflight source check.

Do not delete or overwrite raw batches. A replay writes a new batch, links
`replay_of_batch_id`, and succeeds as `SUCCEEDED_REPLAY` only when the requested historical file,
period, and hash match.

## Required demonstrations

- MES initial: 12 monthly files succeed with one audit row each.
- MES rerun: the same 12 identities/hashes skip and create no duplicate raw batch.
- MES new month: one new `YYYY-MM` file succeeds.
- MES conflict: changed bytes under an existing file/period identity produce
  `CONFLICT_SOURCE_CHANGED` and no raw write.
- MES replay: explicit force plus the original successful batch produces a new immutable batch and
  `SUCCEEDED_REPLAY`.
- Quality: the original XLSX binary lands unchanged; sheets `Inspections`, `DefectTypes`, and
  `Targets` are present; no business correction is performed.
- PDFs: all six original binaries land unchanged, with one audit record per file and no OCR.
- AtlasERP: four ordered full extracts land as Parquet, with source held stable across the run.

Validate counts, file sizes, SHA-256 values, paths, statuses, batch linkage, and absence of any
additional Phase 3 Delta table.

Record deliberate acceptance conflicts by their Fabric run ID. Keep diagnostic conflict runs
separately identified in `execution-evidence.md`; never delete or rewrite either category to simplify
status totals, and never count diagnostics as the controlled acceptance test.

## AtlasERP consistency and security

Use an on-premises data gateway and a rotated password for `atlas_fabric_reader`; do not reuse the
committed local-development default. Hold the synthetic database stable until all four Copy
activities finish. The four independent PostgreSQL queries are not a transactional point-in-time
snapshot of a mutable enterprise database. Reassess this limitation for production; do not add CDC,
locks, exported snapshots, or transaction orchestration to this demo.

## MaintControl operational interface

Live execution is pending separate tunnel-provider authorization. Do not install or invoke
Cloudflare Quick Tunnel, ngrok, devtunnel, or another tunnel. When authorized, the provider must
expose:

- an HTTPS base URL with a valid certificate;
- `GET /api/v1/work-orders` and `GET /api/v1/maintenance-events`;
- bearer authentication;
- `cursor` and `page_size` pagination (`1..500`);
- `occurred_from` and `occurred_to` behavior for the extraction window.

For `work-orders`, the occurrence window is applied to `opened_at`; for `maintenance-events`, it is
applied to `started_at`. Both boundaries are inclusive. `MAINTCONTROL_TUNNEL_BASE_URL` and
`MAINTCONTROL_API_TOKEN` remain external values. Mark token input
and activity output secure and never echo request headers. The local API is treated as stable during
each full extraction. Production consistency and pagination behavior must be reassessed against a
mutable API.

The connection and live pipeline test remain pending until a tunnel provider is explicitly
approved.

## Failure and recovery

- A copy failure is finalized as `FAILED` with a sanitized error code/message; never log secrets.
- A notebook-finalize failure deliberately leaves `STARTED`; wait for the two-hour stale threshold
  or correct the row through the notebook recovery path, never by deleting audit history.
- A conflict requires source-owner review. Do not overwrite, rename, or silently accept the changed
  object.
- A partially written batch is immutable evidence. Retry to a new batch and retain the failed audit
  context.

## Deferred operational actions

MaintControl tunnel/provider authorization and live connection, Fabric Git Integration, production
snapshot design, retention/SLOs, and all Bronze-to-Silver work remain separate approvals.
