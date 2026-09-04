# ADR-001: Medallion Architecture

- Status: Accepted

## Context

Atlas Industrial Manufacturing will combine structured, semi-structured, and unstructured source
data with different quality and change characteristics. The platform needs clear processing stages,
traceability, and the ability to reprocess source data.

## Decision

Organize the analytical data flow into Bronze, Silver, and Gold responsibilities. Bronze preserves
source data, Silver validates and conforms it, and Gold exposes business-oriented data products.

## Alternatives Considered

- A single mutable analytical layer, which reduces initial objects but mixes raw, conformed, and
  serving concerns.
- Source-specific end-to-end pipelines, which isolate sources but duplicate quality and serving
  patterns.

## Consequences

Layer responsibilities and data maturity are explicit, and raw inputs remain available for replay.
The design introduces additional storage and processing transitions that future pipelines must
operate and observe.
