# ADR-006: Gold as a General Serving Layer

- Status: Accepted

## Context

The platform may serve Power BI, SQL users, controlled exports, APIs, and an optional web
application. Coupling Gold exclusively to one visualization tool would constrain reuse and mix
semantic modeling with storage responsibilities.

## Decision

Treat Gold as a governed, business-oriented serving layer that is independent of Power BI. Design
its facts and dimensions only after business questions and grains are explicitly defined.

## Alternatives Considered

- Shape Gold exclusively around Power BI semantic models.
- Expose Silver directly to every analytical consumer.
- Define the complete dimensional model during repository setup.

## Consequences

Multiple governed consumers can reuse Gold and Power BI remains an optional serving experience.
The eventual Gold model needs explicit consumer requirements, ownership, refresh behavior, and fact
grain decisions before implementation.
