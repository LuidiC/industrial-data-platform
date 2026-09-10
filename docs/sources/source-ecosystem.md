# Phase 2 source ecosystem

## Purpose and boundaries

Phase 2 implements deterministic, synthetic operational sources for Atlas Industrial Manufacturing.
Phase 3 consumes them without changing their Phase 2 source behavior. Silver, Gold, Power BI, and
business transformation remain out of scope. All generated values and documents are fictional and
public-safe.

## Sources and interfaces

| Source | Interface | Grain | Output |
|---|---|---|---|
| AtlasERP | PostgreSQL | master entity or production order/lot | `atlas_erp` schema |
| MES Simulator | CSV | completed 30-minute machine production interval | one monthly CSV per period |
| Quality Department | XLSX | one inspection sample | one workbook with `Inspections`, `DefectTypes`, and `Targets` |
| MaintControl | REST/JSON | work order or effective maintenance event | paginated read-only endpoints |
| Technical Documents | PDF | one synthetic departmental document | six small unstructured files |

Production orders own one `batch_id`. Production events and inspections must reference existing
orders, batches, products, lines, and machines. Maintenance events refer to the same ERP machines.
The clean baseline avoids production during an effective maintenance interval.

## Time and identifiers

The default source history is calendar year 2025 in `America/Sao_Paulo`. `SHIFT-A` runs from
06:00 to 14:00, `SHIFT-B` from 14:00 to 22:00, and `SHIFT-C` from 22:00 to 06:00. For the
overnight shift, `shift_business_date` is the date on which that shift began.

Business identifiers are stable and synthetic: `LINE-01`, `MCH-001`, `PRD-001`,
`PO-2025-000001`, `LOT-2025-000001`, `PEV-2025-01-000001`, `QIN-2025-000001`,
`WO-2025-000001`, and `MNT-2025-000001`.

## Reproduction and incremental output

The committed TOML configuration is the source of truth. Run `atlas-sim generate` after installing
the project to create outputs under `data/local/atlas-2025`. A fixed seed, configuration, and
period produce equivalent business data on repeat runs. A monthly configuration independently
generates only that month and is semantically equivalent to the matching annual month. CSV/JSON
values and business identifiers are stable. XLSX reproducibility is semantic rather than byte-level:
the same seed/configuration yields identical workbook structure and business cell values even if ZIP
metadata differs. MES files are generated monthly; orders
are intentionally contained within one month so a monthly source drop remains self-contained.

Run `atlas-sim load-erp` with `ATLAS_ERP_DSN` to create/load the AtlasERP schema. Run
`atlas-sim --host 127.0.0.1 --port 8001 serve-api` with `MAINTCONTROL_API_TOKEN` to expose the
local MaintControl API. The host defaults to loopback; only select another bind address for a
deliberate local-network test. Both
`GET /api/v1/work-orders` and `GET /api/v1/maintenance-events` require a bearer token, use stable
cursor pagination, and have no write operations. Invalid cursors, offsets, filters, timestamp
offsets, date ranges, and page sizes produce controlled 4xx responses without exposing exceptions.
A syntactically valid `machine_id` that is not present in the clean AtlasERP machine catalogue
(for example, `MCH-999`) is a valid empty filter: both endpoints return HTTP 200 with `data: []`.
The same anomalous value remains visible in an unfiltered MaintControl source payload, preserving
source fidelity for the documented DQ scenario.

## Data quality and observability handoff

The generated source data intentionally includes documented anomalies. The separate
`metadata/anomaly_manifest.json` is a test artifact and must not be ingested as an analytical
source. Its root records generator/configuration version, seed, and effective period. Every entry
uses a pre-mutation locator plus physical file, worksheet or JSON pointer, serialized row location,
affected field, rule, anomaly type, severity, and disposition. Bronze must preserve source-invalid
values faithfully. Future Silver work will use the DQ catalog to validate and quarantine critical
records.

Duplicate-ID anomalies are copied from a separate pristine baseline record, never from a row that
already carries another injected anomaly. Their manifest entries include a non-empty immutable
source locator, a distinct duplicate locator, and the original source-row index so the exact
source/duplicate relationship remains auditable even when the duplicated business ID occurs twice.
Automated contract tests validate all ten clean output datasets for field order, declared types,
requiredness, uniqueness, enumerations, resolvable DQ references, and the clean baseline's DQ
semantics. PDF tests validate each Q1–Q3 input subset and its count directly from the lightweight
document input model; they intentionally do not add a PDF parser, OCR, or extraction dependency.

## Future Fabric accessibility

AtlasERP remains local, binds only to loopback, and provides a separate `atlas_fabric_reader` role
with only schema usage and table select privileges for a gateway. Bootstrap runs through the local
admin role; the reader owns neither schema nor tables. The committed reader password is a local
development default and must be rotated before a Fabric connection is created.

MaintControl remains local by default. For the accepted Phase 3 demo, a separately authorized
Cloudflare Quick Tunnel exposed it through authenticated HTTPS while the API stayed bound to
`127.0.0.1` and the tunnel forwarded to `http://127.0.0.1:8001`. This ephemeral route is not a
production hosting recommendation. CSV, XLSX, and PDF prefer SharePoint Online File only when the
tenant PoC passes; otherwise the runbook uses and explicitly labels the OneLake demo staging
fallback.

## Public artifact policy

Commit code, DDL, configuration, contracts, documentation, small representative samples, and a
sample anomaly manifest. Do not commit full generated output, Docker volumes, tokens, DSNs with
real passwords, operational logs, or database dumps. Git LFS is not required.

## Explicit non-goals

OEE is not calculated or claimed. It requires validated planned production time, an availability
calendar, complete loss classification, ideal rates, and overlap policy beyond this source scope.
PDFs use exactly two simple templates (maintenance report and quality bulletin), six files total,
and have no charts, OCR, extraction logic, or analytic role beyond future Bronze preservation.
