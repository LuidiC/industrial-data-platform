# Data quality and quarantine strategy

## Objectives

Data quality controls turn deliberate synthetic anomalies into observable, repeatable test cases.
Anomalies are not arbitrary noise: every generated issue must map to a documented rule in
[`rules.yaml`](rules.yaml).

Phase 1 defines conventions and three illustrative rules only. It does not generate data or execute
validations.

## Rule identifiers

Rules use `DQ-<DOMAIN>-NNN`:

- `DQ` identifies the control as a data quality rule.
- `<DOMAIN>` is an uppercase, stable domain abbreviation such as `PROD`, `QUAL`, or `MAINT`.
- `NNN` is a zero-padded sequence unique within that domain.

Rule IDs are immutable after use. A materially different rule receives a new ID instead of silently
changing the meaning of historical results.

## Rule catalog

Each catalog entry includes:

- `id`: stable rule identifier.
- `domain`: business domain.
- `description`: testable condition in plain language.
- `severity`: `error` or `warning`.
- `disposition`: `quarantine` or `observe`.

`error` represents data that cannot safely enter the conformed dataset. `warning` preserves the
record while surfacing a non-blocking issue. `quarantine` isolates a rejected record; `observe`
retains it in the valid flow while recording the result.

## Validation flow

1. Bronze preserves the source representation and ingestion metadata.
2. Silver validation evaluates type, required value, identifier, reference, domain, temporal,
   quantity, and duplicate rules.
3. Passing records continue to conformance and integration.
4. Critical failures are written to quarantine with enough context to diagnose and replay them.
5. Counts of valid, rejected, and warning records contribute to execution observability.

Invalid business values are never silently corrected in Bronze and critical failures never silently
disappear in Silver.

## Quarantine record context

A future quarantine representation must retain, either directly or through a durable reference:

- rejected source record or payload reference;
- violated `rule_id`;
- source system and source object;
- source file when applicable;
- ingestion `batch_id`;
- human-readable rejection reason;
- validation timestamp;
- pipeline or validation execution identifier.

The physical table design, serialization of rejected payloads, replay workflow, and retention policy
remain deferred until Silver processing is designed.

## Planned anomaly coverage

Future synthetic datasets may include controlled duplicates, missing required values, invalid
references, inconsistent casing, malformed identifiers, invalid statuses, impossible timestamps,
and negative quantities. Each injected case must declare its expected rule and disposition so tests
can distinguish an intentional defect from generator failure.

## Phase 2 anomaly manifest

The Phase 2 simulator writes a separate JSON anomaly manifest containing the generator version,
configuration seed, period, source row counts, affected record identifier, field, injected value,
and expected DQ rule. It is test metadata rather than a source dataset and must remain outside the
source folders selected by future ingestion. The manifest does not authorize correcting source
records before Bronze preservation.
