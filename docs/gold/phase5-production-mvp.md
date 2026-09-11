# Phase 5 Gold production MVP

## Status and boundary

Phase 5 is implemented in source-controlled repository artifacts. It has not yet been published or
executed in the Microsoft Fabric tenant. A repository notebook or pipeline recipe is not tenant
execution evidence.

The MVP serves production-output analysis only. Quality, Maintenance, Technical Documents,
quarantine analytics, OEE, planned quantity, and production attainment remain excluded.

## Dimensional model

| Gold table | Grain | Silver source |
|---|---|---|
| `dim_date` | One continuous operational business date | Range of `production_events.shift_business_date` |
| `dim_product` | One current product | `products` |
| `dim_machine` | One current machine | `machines` |
| `dim_production_line` | One current production line | `production_lines` |
| `fact_production_event` | One accepted completed production event | `production_events` |

The fact business key is `event_id`. Source business identifiers remain the relationship keys for
product, machine, and line; `date_key` is the deterministic integer representation `yyyyMMdd`.
Sequential surrogate keys and slowly changing dimensions are deliberately absent from this MVP.

`shift_code` is a degenerate dimension in the fact. Three stable codes with no independent source
attributes do not justify `dim_shift`.

## Gold columns

### `dim_date`

`date_key`, `calendar_date`, `year_number`, `quarter_number`, `quarter_label`, `month_number`,
`month_name`, `month_short_name`, `year_month`, `day_of_month`, `day_of_week_number`,
`day_of_week_name`, and `is_weekend`.

The dimension contains every date from the minimum through maximum accepted
`shift_business_date`. Dashboard production dates therefore follow the operational shift date,
including the documented overnight-shift convention.

### `dim_product`

`product_id`, `product_name`, `product_family`, and `nominal_cycle_seconds`.

`nominal_cycle_seconds` is a descriptive product attribute. It does not by itself support OEE.

### `dim_machine`

`machine_id`, `machine_name`, `machine_type`, `machine_status`, and `owning_line_id`.

### `dim_production_line`

`production_line_id`, `production_line_name`, and `production_line_status`.

### `fact_production_event`

`event_id`, `production_order_id`, `batch_id`, `date_key`, `production_date`, `product_id`,
`machine_id`, `production_line_id`, `shift_code`, `event_started_at_utc`,
`event_ended_at_utc`, `produced_quantity`, `rejected_quantity`, and `accepted_quantity`.

`accepted_quantity` is the additive row-level result:

```text
produced_quantity - rejected_quantity
```

The order and batch identifiers are degenerate drill-through attributes. No order dimension or
order fact is created.

## Metric semantics

| Metric | Definition | Layer |
|---|---|---|
| Produced quantity | Sum of units reported as produced, including rejected units | Power BI measure over physical fact quantity |
| Rejected quantity | Sum of rejected units | Power BI measure over physical fact quantity |
| Accepted quantity | Sum of produced minus rejected units | Physical row quantity plus Power BI sum measure |
| Rejection rate | Rejected quantity divided by produced quantity | Power BI measure |
| Event count | Count of fact rows | Power BI measure |
| Average produced per event | Produced quantity divided by event count | Power BI measure |

Rates, averages, and event counters are not physically stored. Rejection rate must be calculated as
a ratio of sums, not as an average of row-level rates.

## Power BI relationships

Create active one-to-many, single-direction relationships from each dimension to the fact:

| Dimension key | Fact key |
|---|---|
| `dim_date.date_key` | `fact_production_event.date_key` |
| `dim_product.product_id` | `fact_production_event.product_id` |
| `dim_machine.machine_id` | `fact_production_event.machine_id` |
| `dim_production_line.production_line_id` | `fact_production_event.production_line_id` |

Mark `dim_date.calendar_date` as the model date column. Sort month names by `month_number`. Do not
relate line to machine, enable bidirectional filters, or create a relationship for `shift_code`.

Recommended measures are sums of the three physical quantities, `COUNTROWS` for event count, and
`DIVIDE` for rejection rate and average produced per event.

## Validation and rebuild behavior

`fabric/notebooks/nb_silver_to_gold_production.py` validates required source structures, business
key uniqueness, fact reconciliation, referential integrity, machine/line consistency, quantity
semantics, shift enumeration, and aggregate totals before publishing.

The notebook rebuilds all five small Delta tables using full overwrite, dimensions first and fact
last. Repeated execution against unchanged Silver creates new Delta versions but must preserve
logical rows, keys, totals, and diagnostic results.

## Production-order diagnostics and limitation

`production_orders` is read only to report event-order coverage, attribute mismatches, and schedule
alignment. These diagnostics do not block valid event-based analytics and are not written to Gold.

The current accepted input has 360 orders and 540 accepted events, and the repository's ERP and
MES fixtures use different generation volumes. Existence of an order reference therefore does not
prove safe planned-versus-actual alignment. Planned quantity and attainment stay excluded until a
separate tenant validation proves order coverage and batch, product, line, and schedule agreement.

OEE also stays excluded because complete planned production time, availability, loss
classification, ideal-rate policy, and overlap rules are not present in the accepted Silver slice.
