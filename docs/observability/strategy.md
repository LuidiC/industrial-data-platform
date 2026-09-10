# Observability strategy

## Purpose

Observability must connect a processing outcome to its source, batch, validation results, and target.
Phase 3 implements the source-controlled schema and notebook behavior for `ingestion_audit`.
Dashboards, alerts, SLOs, retention, and later-layer observability remain deferred. Live tenant
creation and run evidence are tracked separately from repository implementation.

## Implemented ingestion execution record

`ingestion_audit` has one row per source object/file attempt. It records identity, execution and
parent execution, pipeline/source/transport, immutable destination, UTC start/finish, counts, source
metadata, SHA-256, sanitized errors, extraction window, force/replay linkage, and JSON technical
details. Its allowed statuses are `STARTED`, `SUCCEEDED`, `FAILED`,
`SKIPPED_ALREADY_INGESTED`, `CONFLICT_SOURCE_CHANGED`, and `SUCCEEDED_REPLAY`.

Execution records must use a batch ID that can also be found in Bronze metadata and quarantine
records. Counts should reconcile or explicitly explain filtered technical records, retries, and
deduplication.

## Health indicators

Future operational views may expose:

- successful and failed pipeline runs;
- rows read and written;
- quarantined record count and rate;
- freshness against source-specific expectations;
- data quality score based on documented rules.

Definitions, thresholds, alert routes, service objectives, and retention remain deferred. A data
quality score must not be published until its
formula, population, weighting, and treatment of warnings are documented.

## Failure behavior

Failures should preserve their diagnostic context without exposing secrets or full sensitive
payloads in logs. Retries must remain distinguishable from new batches, and partial writes must be
detectable. Silent success with missing or rejected records is not acceptable.
