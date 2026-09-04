# ADR-005: Synthetic Data Only

- Status: Accepted

## Context

This is a public portfolio project. Real industrial or personal data could expose confidential
information and create legal, ethical, and security obligations unrelated to the learning goals.

## Decision

Use only fictional, programmatically generated or manually authored synthetic data. Do not derive
examples from real company records or include real credentials, identifiers, or documents.

## Alternatives Considered

- Anonymized real-world data, which can retain re-identification and licensing risk.
- Public third-party datasets, which may not fit the fictional domain and add provenance duties.

## Consequences

The repository can remain public and deliberately model documented quality failures. Synthetic data
cannot prove behavior against every characteristic of a real industrial workload, and future
generators must document their assumptions and anomaly design.
