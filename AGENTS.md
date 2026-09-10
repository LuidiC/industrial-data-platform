# AGENTS.md

## Purpose

This repository is a public portfolio foundation for the fictional Atlas Industrial Manufacturing
data platform. Microsoft Fabric is the target platform.

Treat the repository and accepted ADRs as the source of truth.

## Current phase

Phase 1 foundations and Phase 2 synthetic sources are implemented. Phase 3 authorizes only
file-first immutable Bronze ingestion, its `ingestion_audit` Delta table, six Fabric pipelines, and
the supporting notebook, runbooks, fixtures, and tests.

Do not describe a Fabric resource or ingestion scenario as demonstrated without tenant execution
evidence. Do not add Bronze-to-Silver, Silver-to-Gold, Power BI, OCR, CDC, mirroring, tunneling
software, or later-phase work unless a new active task explicitly authorizes it.

## Repository map

- `README.md` is the primary Portuguese entry point.
- `README.en.md` is its semantic English equivalent.
- `docs/architecture/` defines the platform boundaries and data flow.
- `docs/adr/` contains authoritative architecture decisions.
- `docs/governance/` defines access, security, and accountability principles.
- `docs/data-contracts/` contains the YAML convention, template, and limited examples.
- `docs/data-quality/` defines rule IDs, quarantine, and the illustrative catalog.
- `docs/observability/` defines the future execution and health model.
- `docs/ingestion/` defines Phase 3 operations and records tenant execution evidence.
- `fabric/` contains source-controlled notebook code and exact live-item build specifications; it
  must not contain invented pipeline-export JSON.
- `tests/repository/` validates repository conventions rather than business processing.

Create new directories only when they contain an artifact required by the authorized phase.

## Non-negotiable constraints

- Use synthetic data only; never use real company or personal data.
- Never commit passwords, tokens, API keys, credentials, private keys, or real connection strings.
- Keep `.env` local and commit only safe placeholders in `.env.example`.
- Preserve Bronze source fidelity; do not silently correct business-invalid source values there.
- Quarantine critical Silver failures; do not silently delete rejected records.
- Keep Gold consumer-agnostic and document every future fact table's grain.
- Do not invent undecided technologies or physical models.

## Conventions

- ADRs use Status, Context, Decision, Alternatives Considered, and Consequences.
- Data contracts are YAML and use semantic versions.
- Data Quality IDs use `DQ-<DOMAIN>-NNN` and remain stable after adoption.
- Contract DQ references must resolve to `docs/data-quality/rules.yaml`.
- Documentation must distinguish Implemented, Planned, and Stretch Goal.
- Update both READMEs when shared project facts or status change.

## Development commands

Use Python 3.13.

```powershell
python -m pip install --upgrade pip
python -m pip install --group dev
ruff check .
ruff format --check .
pytest
git diff --check
```

Run all applicable checks before handing work back. Do not claim unavailable checks passed.

## Change discipline

Prefer the smallest change that satisfies the active phase. Preserve unrelated user changes.
Explain new dependencies and architectural decisions. Add an ADR only for a durable architectural
choice, not for routine tooling or implementation detail.

Do not commit or push unless the user explicitly requests it.
