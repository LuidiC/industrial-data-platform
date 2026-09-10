# Architecture Decision Records

ADRs capture durable decisions that affect the platform structure or engineering constraints. They
are concise, immutable records: a changed decision is documented by a new ADR that supersedes the
old one.

## Status values

- `Proposed`: under review and not authoritative.
- `Accepted`: approved and currently authoritative.
- `Superseded`: replaced by a newer ADR.
- `Deprecated`: no longer recommended, without a direct replacement.

## Required structure

```markdown
# ADR-NNN: Decision title

- Status: Proposed | Accepted | Superseded | Deprecated

## Context
## Decision
## Alternatives Considered
## Consequences
```

## Index

| ADR | Status | Decision |
|---|---|---|
| [ADR-001](001-medallion-architecture.md) | Accepted | Use Medallion Architecture |
| [ADR-002](002-separate-medallion-lakehouses.md) | Accepted | Separate Bronze, Silver, and Gold Lakehouses |
| [ADR-003](003-single-fabric-workspace.md) | Accepted | Use one Fabric workspace for the portfolio environment |
| [ADR-004](004-quarantine-invalid-records.md) | Accepted | Quarantine critical invalid records |
| [ADR-005](005-synthetic-data-only.md) | Accepted | Use synthetic data only |
| [ADR-006](006-gold-general-serving-layer.md) | Accepted | Keep Gold consumer-agnostic |
| [ADR-007](007-file-first-immutable-bronze.md) | Accepted | Use file-first immutable Bronze ingestion |
