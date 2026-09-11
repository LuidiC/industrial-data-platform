# Phase 6 production dashboard

## Scope and implementation state

Phase 6 implements and validates the production analytics serving layer in the Microsoft Fabric
tenant. It connects Power BI directly to the accepted Phase 5 Gold model; it does not extend the
underlying Bronze, Silver, or Gold processing logic.

The live items in workspace `Industrial Data Platform - Lakehouse Analytics` are:

- semantic model `sm_atlas_production`;
- report `rpt_atlas_production_overview`;
- presentation-facing page `Visão Geral da Produção`.

The report is a concise, one-page Portuguese portfolio demonstration for production volume,
rejection, and operational contribution. The current Power BI scope is implemented and validated
in Fabric, while the repository records its design and observed evidence rather than a fabricated
export of the live items.

## Direct Lake semantic model

`sm_atlas_production` uses Direct Lake over exactly five accepted Gold tables:

| Semantic table      | Physical Gold source                |
| ------------------- | ----------------------------------- |
| `Date`              | `lh_gold.dbo.dim_date`              |
| `Product`           | `lh_gold.dbo.dim_product`           |
| `Machine`           | `lh_gold.dbo.dim_machine`           |
| `Production Line`   | `lh_gold.dbo.dim_production_line`   |
| `Production Events` | `lh_gold.dbo.fact_production_event` |

Four active one-to-many, single-direction relationships filter `Production Events` from the
dimensions: `Date`, `Product`, `Machine`, and `Production Line`. No bidirectional or
dimension-to-dimension relationship was introduced.

## Measures and baseline validation

The following six measures are grouped under `Production KPIs`:

- `Produced Quantity`;
- `Accepted Quantity`;
- `Rejected Quantity`;
- `Rejection Rate`;
- `Event Count`;
- `Average Produced per Event`.

| Measure                    |             Validated value |
| -------------------------- | --------------------------: |
| Produced Quantity          |                      54,949 |
| Accepted Quantity          |                      53,879 |
| Rejected Quantity          |                       1,070 |
| Event Count                |                         540 |
| Average Produced per Event |      approximately 101.7574 |
| Rejection Rate             | approximately 1.9472601867% |
| Displayed Rejection Rate   |                       1.95% |

The reconciliation `Produced Quantity - Rejected Quantity = Accepted Quantity` was also
validated: `54,949 - 1,070 = 53,879`.

## Report composition

The page title is `Visão Geral da Produção`, with subtitle
`Produção, rejeição e desempenho operacional por linha, máquina, produto e turno`.

The five slicers are Data, Linha de Produção, Produto, Máquina, and Turno.

The four KPI cards are:

- Quantidade Produzida;
- Quantidade Aprovada;
- Quantidade Rejeitada;
- Taxa de Rejeição.

The analytical visuals are:

1. `Produção Mensal e Taxa de Rejeição`;
2. `Máquinas com Maior Taxa de Rejeição`;
3. `Produção por Linha`;
4. `Desempenho por Produto`.

Portuguese labels and friendly month, machine, and production-line descriptions keep the page
presentation-ready. The one-page layout favors an immediately readable executive overview.

A separate shift chart is intentionally omitted: shift analysis remains available through the
`Turno` slicer without crowding the page.

## Validation evidence

Tenant validation confirmed:

- Direct Lake access to the accepted `lh_gold` tables;
- exactly five semantic-model tables;
- exactly four active single-direction relationships;
- all six production measures;
- the unfiltered production baseline;
- the quantity reconciliation;
- the saved one-page report composition;
- interactive filtering through the report slicers.

The live semantic model identifier is:

`f1e5049e-888c-43f8-a265-fdc6be6990e4`

The live report identifier is:

`949adbd2-8e4f-4142-8acd-e84b6705e92a`

No repository-ready screenshot files were available during the automated reconciliation.
Therefore screenshots were not fabricated or added to the repository.

## Known limitations and explicit exclusions

- The report covers production analytics only.
- Planned quantity, production attainment, OEE, and planned-versus-actual analysis are excluded.
- Quality, Maintenance, and quarantine metrics are excluded from this semantic model and report.
- Quality, MaintControl, and Technical Document processing remain deferred.
- Production-grade deployment automation, Fabric Git Integration, multi-environment promotion,
  and automated semantic-model/report provisioning are not demonstrated.
- The live Fabric items are not exported into this repository; the tenant remains authoritative
  for their physical configuration.

## Repository status and presentation readiness

The project now demonstrates the production path:

`Sources → Bronze → Silver → Gold → Power BI`

with tenant-validated processing through each implemented layer.

Phase 6 is ready to present as a focused portfolio MVP within the exclusions above.

Any later dashboard, metric family, deployment automation, or additional domain requires a
separately scoped project increment.
