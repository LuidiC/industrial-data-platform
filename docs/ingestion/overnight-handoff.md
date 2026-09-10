# Phase 3 final handoff

## Decision

**Phase 3 — source to immutable Bronze: COMPLETE.**

All five child ingestion pipelines, `pl_ingest_all_sources`, the batched audit notebook,
`ingestion_audit`, immutable raw landing, and accepted idempotent reruns functioned in Fabric. The
repository now describes the published tenant state and its limitations. No correctness defect
blocks the synthetic demonstration.

The exact recommended next phase is **Phase 4 — Bronze → Silver**. It was not started here.

## Timestamp and repository state

- Reconciled at 2026-09-10 14:13:34 -03:00 (`America/Sao_Paulo`).
- Branch: `feat/phase-3-bronze-ingestion`.
- Existing local commits before final reconciliation:
  - `6658390 feat: checkpoint Phase 3 Bronze ingestion foundation`
  - `f7d129b chore: add MaintControl tunnel demo workflow`
  - `bad064a docs: clarify MaintControl demo tunnel status`
- A local final-reconciliation checkpoint is authorized; its hash is reported in the final task
  response because a commit cannot contain its own hash.
- No push, PR, merge, history rewrite, or Fabric Git Integration occurred.
- `.fabric-import-pl_ingest_quality.zip` remains untracked and untouched. It is the old unsupported
  package that Fabric rejected as a template; it was preserved as user work.
- `.env` remains ignored and was not staged.

## Fabric items confirmed

| Item | ID |
|---|---|
| `nb_bronze_ingestion_audit` | `a3f33829-2a79-460f-8b45-9cf25a355041` |
| `pl_ingest_atlas_erp` | `5746b71f-32dc-4b1b-bfe0-fe2bfef633f6` |
| `pl_ingest_mes` | `b9645bcc-46ac-42a7-9d91-60d085944a08` |
| `pl_ingest_quality` | `9ee7b72b-2544-4296-8985-7ec1a7d4e64e` |
| `pl_ingest_maintcontrol` | `3d68708a-8a58-4311-a716-ff398027c748` |
| `pl_ingest_technical_documents` | `1cfe1200-0e62-49c9-8d38-f7522be548e9` |
| `pl_ingest_all_sources` | `559fcda5-e92b-4014-a381-3981fcb0c6fe` |

The published MaintControl graph uses two Append Variable activities, batched preflight/finalize,
a sequential Copy ForEach with success/failure result collection, and a final fail condition. The
published orchestrator invokes AtlasERP, MES, Quality, MaintControl, and Technical Documents
sequentially, waits for each child, and propagates `parent_execution_id`.

## Accepted run evidence

- MES: initial `cd048f50-036e-49f9-803d-6598b6ab13f4`; identical rerun
  `7b99834c-ee13-4e08-84d9-fd1aaf49399b`; new month
  `b9b2ea0e-5f3f-47fe-add3-41a57857d100`; controlled conflict
  `642ad6a3-6387-4694-8f73-4a7b4173e673`; replay
  `abdb6f92-7e90-42d5-90d8-fe62ec8d8b2f`.
- Quality: initial `aa22e426-0f99-458c-bd50-4cc2c5b6c10d`; rerun
  `26cbd2e1-cbdf-4173-80f3-33c48463c1e5`.
- Technical Documents: initial `c72318b2-046e-4394-b095-0b9560b69318`; idempotent child rerun
  `db533917-0bdc-437b-881b-b9d8c3303c02`.
- AtlasERP: initial `1517a752-abfa-4074-9ebe-8a56f9b36071`; rerun
  `8aff1231-7a9f-416d-b775-5af25f4a4545`.
- MaintControl: initial `15864ed6-ab10-4578-8f84-9e1c31c95310`; rerun
  `7d48039d-cf06-4a7d-b43a-379937bdf180`; orchestrated child
  `f3168680-cdd6-4049-903e-697aaed3e780`.
- Orchestrator: `04585b6c-960b-41af-863d-ec4fea041bc3`; all five invokes succeeded.

The current audit view contains 133 rows and 29 columns: 26 `SUCCEEDED`, 69
`SKIPPED_ALREADY_INGESTED`, 37 `CONFLICT_SOURCE_CHANGED`, and 1 `SUCCEEDED_REPLAY`. Exactly one
conflict is the controlled acceptance case; the other 36 are preserved MES diagnostic history.
No `STARTED` or `FAILED` row remains in the accepted reconciliation.

Detailed object counts, file/hash evidence, and the distinction between raw JSON document metrics
and MaintControl domain counts are in `execution-evidence.md`.

## Cleanup completed

- Stopped the orphaned `cloudflared` process; port 8001 was not listening.
- Removed only ignored local `tmp/cloudflared.stderr.log`, `tmp/cloudflared.stdout.log`, and
  `tmp/tools/cloudflared.exe`; no tunnel binary/log remains under `tmp`.
- Positively separated the official AtlasERP production-lines batch from the diagnostic batch, then
  deleted only
  `Files/raw/atlas_erp/production_lines/extract_date=2026-09-09/batch_id=test-production-lines/production_lines.parquet`.
  The empty diagnostic folder remains; official immutable batches were not changed.
- Discarded only a harmless unsaved visual displacement introduced while inspecting the published
  MaintControl Copy activity. Save/Discard returned disabled; the published definition was not
  changed.

## Cleanup still manual or intentionally deferred

- Rotate/discard the short-lived synthetic MaintControl bearer token after the demonstration.
- Retain `cn_rest_maintcontrol_quick_tunnel_tmp 1447551` while the accepted pipeline needs its
  current connection record. Despite its legacy name, it is the published Copy dependency. Update
  its URL for a later authorized tunnel; do not treat it as stable production configuration.
- `cn_rest_maintcontrol_gateway` and `cn_rest_maintcontrol_gateway (2)` may be obsolete diagnostics,
  but ownership/obsolescence was not proven, so neither was deleted.
- Connection management contains both `cn_fabric_pipeline_invoke` and
  `FabricDataPipelines 1447551`. The published Invoke activities display the latter selection;
  owner review may later consolidate names, but no functioning connection was changed.
- The empty AtlasERP `batch_id=test-production-lines` folder may be removed manually if desired;
  it contains no data after the exact diagnostic file cleanup.

## Security status

- No bearer token, Authorization header, real credential, exact Quick Tunnel URL, or tunnel log is
  tracked.
- `.env` remains ignored; only safe placeholders are committed.
- The Fabric MaintControl parameters have no committed/default token or URL.
- Cloudflare is documented as a TLS-terminating intermediary for a synthetic demo only.
- Production guidance requires a stable governed HTTPS API or managed/private networking, managed
  secrets, certificate/DNS lifecycle, monitoring, and availability ownership. Quick Tunnel is not
  the production recommendation.
- `compose.yaml` keeps the AtlasERP host port parameterized as
  `127.0.0.1:${ATLAS_ERP_PORT:-5432}:5432`; no machine-specific 55433 hard-code was reintroduced.

## Known non-blocking limitations

- SharePoint Online File remains preferred only after a tenant PoC. The PoC was not executable
  because tenant coordinates/files were not supplied; the demonstrated path was explicitly
  `onelake_demo_staging` for MES, Quality, and PDFs.
- File candidates have authoritative source SHA-256 and size calculated from staging, so content
  changes conflict correctly.
- PostgreSQL and MaintControl use snapshot-identity idempotency when source content hash is null.
  This is not source fingerprinting or source-change detection.
- Non-file replay is not accepted: the current notebook can compare a null current source hash with
  a populated historical destination hash. Keep force/replay disabled for AtlasERP and MaintControl.
- AtlasERP's four queries and MaintControl's API requests were run against stable synthetic sources;
  they do not claim transactional snapshots for mutable production systems.
- Fabric Git Integration remains a should-have follow-up, not a Phase 3 acceptance dependency.

## Final validation

Validation used Python 3.13.3 from the ignored repository-local environment:

- `python --version`: `Python 3.13.3`;
- `python -m compileall -q src fabric tests`: passed;
- `ruff check .`: passed;
- `ruff format --check .`: passed, 38 files already formatted;
- `pytest -p no:cacheprovider --basetemp tmp/pytest-final-20260910-c`: 57 passed, 1 skipped,
  0 failed, 1 warning in 61.54 seconds;
- skipped: PostgreSQL integration because `ATLAS_ERP_TEST_DSN` was not supplied;
- warning: existing Starlette/AnyIO `BlockingPortal` deprecation;
- `git diff --check`: passed.

The first post-reconciliation pytest run correctly exposed one stale repository assertion that
still expected the OneLake demo and public MaintControl path to be unproved. The test was updated to
match the observed accepted state, and the complete unchanged suite then passed as recorded above.
