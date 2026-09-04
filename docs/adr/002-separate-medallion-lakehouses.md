# ADR-002: Separate Bronze, Silver, and Gold Lakehouses

- Status: Accepted

## Context

Medallion responsibilities need visible technical boundaries. Keeping every stage in one Lakehouse
would rely heavily on naming conventions and make access boundaries less clear.

## Decision

Use three Microsoft Fabric Lakehouses: `lh_bronze`, `lh_silver`, and `lh_gold`.

## Alternatives Considered

- One Lakehouse with schemas or naming conventions for all layers.
- More granular Lakehouses split by source or industrial domain.

## Consequences

Storage purpose, access intent, and lineage transitions are easier to communicate and govern. Cross-
Lakehouse processing requires explicit connections and may add operational overhead. Domain-level
separation remains available if real organizational boundaries later justify it.
