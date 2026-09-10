# Governance and security

## Scope

This document defines a production-reference governance model for the fictional Atlas Industrial
Manufacturing platform. It does not create real identities, grant permissions, or provision Azure
infrastructure.

All repository data must be synthetic and suitable for public disclosure. Real corporate data,
personal data, passwords, tokens, API keys, Fabric credentials, and real connection strings are
prohibited.

## Reference RBAC matrix

| Role | Bronze | Silver | Gold | Power BI |
|---|---|---|---|---|
| Platform Admin | Read/Write | Read/Write | Read/Write | Admin |
| Data Engineer | Read/Write | Read/Write | Read/Write | Build |
| BI Developer | No access | Read | Read | Build |
| Data Analyst | No access | No access | Read | View/Build as required |
| Executive | No access | No access | No direct access | View |

This matrix is a conceptual target. Actual Fabric and Power BI permissions must be configured and
verified in the appropriate environment during a later phase.

## Governance principles

### Least privilege and separation of duties

Access starts denied and is granted only for a role's documented responsibility. Administrative
access is distinct from engineering, modeling, analysis, and consumption responsibilities. Direct
Bronze access is limited because raw data may have the weakest validation and broadest source
detail.

### Ownership and accountability

Each data contract identifies a logical owner. Future operational implementations must separately
record a technical owner and escalation route. Owners approve semantic or compatibility changes;
engineers remain accountable for controlled implementation and evidence from validation.

### Lineage and auditability

Phase 3 ingestion retains source identities, immutable batch IDs, UTC timestamps, SHA-256 values,
transport provenance, replay linkage, and output destinations in `ingestion_audit`. Future
Bronze-to-Silver and Silver-to-Gold transformations must remain traceable through Fabric lineage
where available and repository history for version-controlled artifacts.

### Serving-layer access

Consumers use Gold or governed semantic products by default. Direct Silver access is limited to
approved engineering or BI use cases. Bronze is not an end-user serving layer.

### Environment isolation

This portfolio uses one existing workspace and does not claim production-grade environment
separation. A production deployment should isolate development, test, and production identities,
secrets, deployment paths, and data. Separate workspaces should be evaluated when organizational or
security boundaries justify them.

## Secrets management

- Commit `.env.example` only with fictional placeholders; keep `.env` and local variants ignored.
- Never place secrets in notebooks, pipeline definitions, logs, screenshots, sample data, or Git
  history.
- Use least-privileged service identities instead of personal credentials for automation.
- Prefer Managed Identity and Azure Key Vault for future Azure-hosted workloads.
- Evaluate private connectivity when actual network boundaries and threat models are known.
- Enable GitHub secret scanning and push protection for the public repository where available.

The Phase 1 CI workflow requires only read access to repository contents and uses no project
secrets.

## Data classification and retention

Phase 1 classifies all project examples as `synthetic/public`. Synthetic generation must not derive
from real company records. Retention, deletion, recovery, and legal-hold policies are deferred until
runtime datasets and environments exist; they must be defined before presenting the design as a
production deployment.

## Change control

Architectural decisions are recorded in ADRs. Data contract changes follow semantic versioning and
owner review. Data quality rules have stable identifiers so implementation, quarantine, metrics,
and documentation can refer to the same control.
