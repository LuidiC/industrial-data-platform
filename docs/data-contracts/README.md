# Data contract convention

Data contracts are lightweight, version-controlled YAML documents. They describe the intended
logical interface between a source or producer and platform processing; they do not prescribe a
physical Lakehouse model.

Phase 1 includes a reusable [`contract-template.yaml`](contract-template.yaml) and an illustrative,
non-final [`production_events` example](examples/production-events.v1.yaml). The example documents
the convention but does not freeze the future MES schema.

Every `.yaml` file discovered recursively under `docs/data-contracts/`, except
`contract-template.yaml`, is treated as a concrete Data Contract and must satisfy repository
validation. Keep non-contract YAML metadata outside this directory. This convention automatically
includes future contracts without maintaining a hard-coded test list.

## Required structure

Every contract contains:

- `dataset`: stable snake-case dataset name.
- `version`: semantic version such as `1.0.0`.
- `description`: purpose and boundaries.
- `logical_owner`: accountable business role or domain, never an invented person.
- `fields`: non-empty ordered list of field definitions.

Every field contains:

- `name`, `type`, `required`, `unique`, `description`, and `example`.
- optional `constraints` for logical limits such as allowed values or a minimum.
- optional `related_dq_rules` containing IDs from the data quality catalog.

Examples must always be synthetic and safe for a public repository.

## Versioning policy

Use semantic versioning for the logical contract:

- Patch: clarification that does not change accepted data or consumer behavior.
- Minor: backward-compatible addition, such as a new optional field.
- Major: incompatible removal, rename, type change, newly required field, or stricter constraint.

Contracts are reviewed by their logical owner and technical maintainers before implementation.
Historical contract versions should remain traceable through Git; file retention policy will be
defined when multiple active versions are required.

## Validation

Repository tests parse YAML with `yaml.safe_load`, verify required keys, field-name uniqueness,
semantic versions, DQ identifier syntax, and resolution of referenced rules. These checks validate
the repository convention, not source data or Fabric tables.
