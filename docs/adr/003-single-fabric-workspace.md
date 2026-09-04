# ADR-003: Single Fabric Workspace for the Portfolio Environment

- Status: Accepted

## Context

The portfolio needs credible boundaries without the provisioning and administration burden of a
large enterprise environment. Its three Lakehouses already exist in one manually created workspace.

## Decision

Keep `lh_bronze`, `lh_silver`, and `lh_gold` in the Fabric workspace
`Industrial Data Platform - Lakehouse Analytics` for the portfolio environment.

## Alternatives Considered

- One workspace per Medallion layer.
- Separate workspaces for development, test, and production immediately.

## Consequences

The project remains understandable and economical while preserving layer separation at the
Lakehouse level. Workspace-level isolation is weaker than in a larger deployment. Production use
must reassess workspace boundaries based on environments, ownership, teams, governance, and
security.
