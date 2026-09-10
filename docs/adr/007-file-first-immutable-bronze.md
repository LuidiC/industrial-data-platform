# ADR-007: Use file-first immutable Bronze ingestion

- Status: Accepted

## Context

Phase 3 must demonstrate heterogeneous Fabric ingestion while preserving source fidelity,
supporting deterministic reruns and replay, and avoiding premature Bronze-to-Silver processing.
Approximately 25 initial source objects/files make one notebook invocation per object unnecessarily
expensive. SharePoint Online File is a Preview connector and the tenant behavior must be proven
before it can become a delivery dependency.

## Decision

Land every Phase 3 source as an immutable file under batch-specific paths in `lh_bronze`. The only
Phase 3 Delta table is `ingestion_audit`, at one source object/file attempt per row. A single
technical notebook is invoked in batched preflight and finalize modes around Copy/ForEach activity.

SharePoint Online File is the preferred CSV/XLSX/PDF transport only after an immediate tenant PoC.
If it is unavailable or unreliable, use the explicitly named OneLake demo staging source and record
`transport_source=onelake_demo_staging`; never label that path SharePoint.

MES monthly files are the primary incremental and replay demonstration. AtlasERP and MaintControl
are full snapshots. Their synthetic sources are held stable during extraction; independent queries
or API requests do not claim a transactional point-in-time snapshot for a mutable enterprise
system.

Native Fabric Git Integration is desirable only after core ingestion works and is not a Phase 3
blocker. No hand-written pipeline export JSON substitutes for live Fabric items.

## Alternatives Considered

- Bronze Delta tables per source, rejected because Phase 3 requires source-file fidelity and limits
  Delta to the audit table.
- A notebook per file, rejected because repeated Spark startup adds cost without changing audit
  grain.
- Blocking delivery on SharePoint Preview behavior, rejected because the demo staging fallback is
  explicit and testable.
- CDC, database locks, exported snapshots, or transaction orchestration, rejected as unjustified for
  stable synthetic sources.

## Consequences

Replay and conflict behavior are explicit, raw files remain immutable, and transport provenance is
auditable. The portfolio must state which file transport was actually demonstrated. Production
adoption must reassess snapshot consistency, source concurrency, connection hardening, retention,
and operational objectives.
