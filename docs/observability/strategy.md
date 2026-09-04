# Observability strategy

## Purpose

Observability must connect a processing outcome to its source, batch, validation results, and target.
Phase 1 documents the intended model only; it does not create an audit table, dashboard, alert, or
pipeline.

## Conceptual execution record

A future entity similar to `ingestion_audit` may record:

- `pipeline_name`
- `batch_id`
- `source_system`
- `started_at`
- `finished_at`
- `records_read`
- `records_written`
- `records_rejected`
- `status`
- `error_message`

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

Definitions, thresholds, alert routes, service objectives, storage model, and retention remain
deferred until executable pipelines exist. A data quality score must not be published until its
formula, population, weighting, and treatment of warnings are documented.

## Failure behavior

Failures should preserve their diagnostic context without exposing secrets or full sensitive
payloads in logs. Retries must remain distinguishable from new batches, and partial writes must be
detectable. Silent success with missing or rejected records is not acceptable.
