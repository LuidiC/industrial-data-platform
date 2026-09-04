# ADR-004: Quarantine Invalid Records

- Status: Accepted

## Context

Silver validation will encounter deliberately invalid synthetic records. Silently dropping them
would prevent reconciliation, diagnosis, and replay, while allowing them into conformed outputs
would undermine trust.

## Decision

Send records that fail critical data quality rules to quarantine. Preserve the rejected record or a
durable reference together with the rule, source, batch, reason, and validation timestamp.

## Alternatives Considered

- Drop invalid records after logging aggregate counts.
- Fail every batch on any invalid record.
- Retain invalid records in conformed tables with a validity flag.

## Consequences

Rejected data remains explainable and reconcilable without contaminating valid Silver outputs.
Future implementations must govern quarantine access, retention, replay, and payload storage, and
must monitor quarantine volume.
