# Phase 3 Bronze ingestion runbook

## Scope and status language

This runbook covers ingestion into `lh_bronze` only. It does not authorize transformation,
quarantine processing, Gold modeling, Power BI, OCR, CDC, mirroring, or production tunneling
software. The temporary Cloudflare Quick Tunnel described below is authorized only for the
synthetic MaintControl demonstration and is not a production architecture. A resource is called
*demonstrated* only when its Fabric run evidence is recorded in
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
5. Create `pl_ingest_all_sources` with the five child invocations in their accepted sequential order.
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

For `postgresql_gateway` and `maintcontrol_https`, a null source content hash selects
snapshot-identity idempotency: a successful prior row for the same identity is skipped. This is not
source content fingerprinting or source-change detection. The accepted Phase 3 notebook does not
support replay for these non-file transports because their current candidate hash is null while the
prior destination hash is populated. Keep `force_reprocess=false` and `replay_of_batch_id` empty for
AtlasERP and MaintControl; reassess non-file replay in a later phase rather than claiming support.

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

The approved demo transport is a temporary Cloudflare Quick Tunnel. It exposes the loopback-bound
synthetic API through an ephemeral HTTPS URL; it is not a production deployment pattern. Start the
two foreground processes from separate PowerShell sessions without putting the token on a command
line:

```powershell
$env:MAINTCONTROL_API_TOKEN = Read-Host "MaintControl demo token"
.\scripts\start-maintcontrol-api.ps1
```

```powershell
.\scripts\start-maintcontrol-quick-tunnel.ps1
```

Copy the displayed `https://*.trycloudflare.com` URL into the Fabric connection or secure pipeline
parameter for the current session only. It expires or changes whenever the Quick Tunnel restarts.
Keep the API bound to `127.0.0.1`; the tunnel forwards to `http://127.0.0.1:8001`. Verify locally or
through the ephemeral URL with:

```powershell
$env:MAINTCONTROL_API_TOKEN = Read-Host "MaintControl demo token"
.\scripts\test-maintcontrol-endpoints.ps1 -BaseUrl "https://current-url.trycloudflare.com"
```

The provider must expose:

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

Do not retry the on-premises gateway/private-IP REST route. Fabric rejected both
`http://127.0.0.1:8001` and the host's private IPv4 address with connector error 23360 because a
REST resource at a private address was denied for that connection/network classification. The
temporary public HTTPS transport was selected specifically for this synthetic demonstration; it
does not change the production architecture recommendation.

Bearer authentication remains mandatory even though the URL is temporary. Never commit the token,
URL, request headers, tunnel logs, or a generated credential. For production, replace Quick Tunnel
with a governed endpoint, stable DNS/certificate lifecycle, managed secrets, network controls,
monitoring, and availability ownership.

The public tunnel is a TLS-terminating intermediary for this demo. Starting it and validating the
authenticated endpoints necessarily sends the synthetic runtime bearer header through Cloudflare.
Use a short-lived demo-only token, keep it out of command history and logs, and rotate it after the
session. If the execution environment requires a separate confirmation for that disclosure, obtain
it before starting the tunnel; do not weaken authentication or broaden permissions as a workaround.

The accepted published pipeline uses the connection displayed as
`cn_rest_maintcontrol_quick_tunnel_tmp 1447551`. The legacy suffix does not mean it is currently
disposable: `copy_maintcontrol_object` depends on it. Update its base URL for a new demo tunnel; do
not store that URL or the token in Git. The accepted activity graph is:

```text
append_candidate_work_orders
  -> append_candidate_maintenance_events
  -> nb_preflight_maintcontrol
  -> filter_blocking_maintcontrol
  -> filter_ingest_maintcontrol
  -> copy_ingest_maintcontrol
  -> nb_finalize_maintcontrol
  -> if_fail_maintcontrol
```

The sequential ForEach contains `copy_maintcontrol_object`; success appends to `copy_results`, while
failure appends a sanitized failure result and sets `copy_failed=true`. The final condition fails
when the blocking plan is nonempty or `copy_failed` is true. Preflight and finalize remain batched,
one notebook invocation each.

`pl_ingest_all_sources` invokes AtlasERP, MES, Quality, MaintControl, and Technical Documents in
that order. Each Invoke Pipeline waits for completion and passes
`parent_execution_id=@pipeline().RunId`; a failed child prevents the dependent next activity from
running. MaintControl additionally receives the runtime URL, token, window, and page size. The
orchestrator does not contain Copy, notebook, or Silver activities.

## Failure and recovery

- A copy failure is finalized as `FAILED` with a sanitized error code/message; never log secrets.
- A notebook-finalize failure deliberately leaves `STARTED`; wait for the two-hour stale threshold
  or correct the row through the notebook recovery path, never by deleting audit history.
- A conflict requires source-owner review. Do not overwrite, rename, or silently accept the changed
  object.
- A partially written batch is immutable evidence. Retry to a new batch and retain the failed audit
  context.

## Deferred operational actions

Rotate/discard the synthetic bearer token after the demo. Before a later MaintControl run, start a
new authorized endpoint and update the demo-only connection URL. The old diagnostic REST gateway
connections remain pending owner review because their obsolescence was not proven. Fabric Git
Integration, production snapshot design, retention/SLOs, production API hosting, and all
Bronze-to-Silver work are later decisions. Quick Tunnel remains authorized only for this synthetic
demonstration.
