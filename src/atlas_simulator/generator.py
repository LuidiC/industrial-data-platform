from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from hashlib import sha256
from random import Random
from zoneinfo import ZoneInfo

from .config import SimulationConfig

GENERATOR_VERSION = "0.2.0"
RULE_EXPECTATIONS = {
    "DQ-PROD-001": ("negative_quantity", "error", "quarantine"),
    "DQ-PROD-002": ("malformed_identifier", "error", "quarantine"),
    "DQ-PROD-003": ("unknown_reference", "error", "quarantine"),
    "DQ-PROD-004": ("unknown_reference", "error", "quarantine"),
    "DQ-PROD-005": ("invalid_status", "error", "quarantine"),
    "DQ-PROD-006": ("duplicate_identifier", "error", "quarantine"),
    "DQ-QUAL-001": ("missing_identifier", "error", "quarantine"),
    "DQ-QUAL-002": ("invalid_status", "error", "quarantine"),
    "DQ-QUAL-003": ("impossible_quantity", "error", "quarantine"),
    "DQ-QUAL-004": ("case_normalization", "warning", "observe"),
    "DQ-QUAL-005": ("duplicate_identifier", "error", "quarantine"),
    "DQ-MAINT-001": ("invalid_timestamp_order", "error", "quarantine"),
    "DQ-MAINT-002": ("unknown_reference", "error", "quarantine"),
    "DQ-MAINT-003": ("negative_duration", "error", "quarantine"),
    "DQ-MAINT-004": ("missing_failure_classification", "error", "quarantine"),
}


def _rng(seed: int, key: str) -> Random:
    digest = sha256(f"{seed}:{key}".encode()).digest()
    return Random(int.from_bytes(digest[:8], "big"))


def _score(seed: int, key: str) -> float:
    return _rng(seed, key).random()


def _timestamp(year: int, month: int, day: int, hour: int, zone: ZoneInfo) -> datetime:
    return datetime(year, month, day, hour, tzinfo=zone)


def shift_for(timestamp: datetime) -> tuple[str, date]:
    if 6 <= timestamp.hour < 14:
        return "SHIFT-A", timestamp.date()
    if 14 <= timestamp.hour < 22:
        return "SHIFT-B", timestamp.date()
    return "SHIFT-C", timestamp.date() if timestamp.hour >= 22 else timestamp.date() - timedelta(
        days=1
    )


def quality_status_rule(value: str) -> str | None:
    if value in {"PASS", "FAIL"}:
        return None
    return "DQ-QUAL-004" if value.upper() in {"PASS", "FAIL"} else "DQ-QUAL-002"


@dataclass
class GeneratedData:
    production_lines: list[dict]
    machines: list[dict]
    products: list[dict]
    production_orders: list[dict]
    production_events: list[dict]
    inspections: list[dict]
    defect_types: list[dict]
    targets: list[dict]
    work_orders: list[dict]
    maintenance_events: list[dict]
    anomaly_manifest: list[dict]

    def source_rows(self) -> dict[str, list[dict]]:
        return {
            "production_lines": self.production_lines,
            "machines": self.machines,
            "products": self.products,
            "production_orders": self.production_orders,
            "production_events": self.production_events,
            "inspections": self.inspections,
            "defect_types": self.defect_types,
            "targets": self.targets,
            "work_orders": self.work_orders,
            "maintenance_events": self.maintenance_events,
        }


def _masters(
    config: SimulationConfig,
) -> tuple[list[dict], list[dict], list[dict], list[dict], list[dict]]:
    lines = [
        {"line_id": f"LINE-{i:02d}", "line_name": f"Assembly Line {i:02d}", "status": "active"}
        for i in range(1, config.line_count + 1)
    ]
    machines = []
    for number, (line, station) in enumerate(
        ((line, station) for line in lines for station in range(1, config.machines_per_line + 1)), 1
    ):
        machines.append(
            {
                "machine_id": f"MCH-{number:03d}",
                "line_id": line["line_id"],
                "machine_name": f"{line['line_id']} Station {station}",
                "machine_type": ("assembly", "press", "inspection", "packaging")[station - 1],
                "status": "active",
            }
        )
    products = [
        {
            "product_id": f"PRD-{i:03d}",
            "product_name": f"Atlas Component {i:03d}",
            "product_family": ("hydraulic", "electrical", "mechanical")[i % 3],
            "nominal_cycle_seconds": 45 + (i % 4) * 15,
        }
        for i in range(1, config.product_count + 1)
    ]
    defect_values = [
        ("Surface scratch", "surface", "low"),
        ("Dimension out of tolerance", "dimension", "high"),
        ("Incomplete assembly", "assembly", "high"),
        ("Loose fastener", "assembly", "medium"),
        ("Seal deformation", "material", "high"),
        ("Label mismatch", "packaging", "low"),
        ("Electrical continuity", "electrical", "high"),
        ("Coating variation", "surface", "medium"),
        ("Foreign material", "material", "medium"),
        ("Weld porosity", "weld", "high"),
        ("Connector damage", "electrical", "medium"),
        ("Packaging damage", "packaging", "low"),
    ]
    defects = [
        {
            "defect_code": f"DEF-{i:03d}",
            "description": name,
            "category": category,
            "severity": severity,
            "active": True,
        }
        for i, (name, category, severity) in enumerate(defect_values, 1)
    ]
    year = config.start_date.year
    targets = [
        {
            "product_id": product["product_id"],
            "target_reject_rate": round(0.012 + index * 0.001, 3),
            "effective_from": date(year, 1, 1).isoformat(),
            "effective_to": date(year, 12, 31).isoformat(),
        }
        for index, product in enumerate(products)
    ]
    return lines, machines, products, defects, targets


def _maintenance(config: SimulationConfig, machines: list[dict]) -> tuple[list[dict], list[dict]]:
    zone = ZoneInfo(config.timezone)
    per_month = 15 if config.profile == "portfolio" else 67
    work_orders: list[dict] = []
    events: list[dict] = []
    for year, month in config.months:
        for local_number in range(1, per_month + 1):
            number = (month - 1) * per_month + local_number
            rng = _rng(config.seed, f"maintenance:{year}:{month}:{local_number}")
            machine = machines[rng.randrange(len(machines))]
            started = _timestamp(year, month, 1 + rng.randrange(25), rng.randrange(24), zone)
            corrective = number % 4 == 0
            status = "cancelled" if number % 12 == 0 else "completed"
            duration = 60 * (2 + rng.randrange(7))
            ended = started + timedelta(minutes=duration)
            closed = ended if status == "completed" else started + timedelta(hours=1)
            work_order = {
                "work_order_id": f"WO-{year}-{number:06d}",
                "machine_id": machine["machine_id"],
                "maintenance_type": "corrective" if corrective else "preventive",
                "priority": "high" if corrective else "normal",
                "status": status,
                "opened_at": (started - timedelta(days=2)).isoformat(),
                "planned_start": started.isoformat(),
                "closed_at": closed.isoformat(),
                "failure_classification": "mechanical" if corrective else None,
            }
            work_orders.append(work_order)
            if status == "completed":
                events.append(
                    {
                        "maintenance_event_id": f"MNT-{year}-{number:06d}",
                        "work_order_id": work_order["work_order_id"],
                        "machine_id": machine["machine_id"],
                        "started_at": started.isoformat(),
                        "ended_at": ended.isoformat(),
                        "downtime_minutes": duration,
                        "maintenance_type": work_order["maintenance_type"],
                        "failure_classification": work_order["failure_classification"],
                        "updated_at": ended.isoformat(),
                    }
                )
    return work_orders, events


def _next_available(
    requested: datetime, machine_id: str, maintenance: list[dict], available: dict[str, datetime]
) -> datetime:
    candidate = max(requested, available.get(machine_id, requested))
    intervals = sorted(
        (datetime.fromisoformat(row["started_at"]), datetime.fromisoformat(row["ended_at"]))
        for row in maintenance
        if row["machine_id"] == machine_id
    )
    changed = True
    while changed:
        changed = False
        for started, ended in intervals:
            if candidate < ended and candidate + timedelta(minutes=30) > started:
                candidate, changed = ended, True
    return candidate


def _orders_and_events(
    config: SimulationConfig,
    lines: list[dict],
    machines: list[dict],
    products: list[dict],
    maintenance: list[dict],
) -> tuple[list[dict], list[dict]]:
    zone = ZoneInfo(config.timezone)
    orders: list[dict] = []
    events: list[dict] = []
    availability: dict[str, datetime] = {}
    for year, month in config.months:
        for offset in range(config.orders_per_month):
            number = (month - 1) * config.orders_per_month + offset + 1
            rng = _rng(config.seed, f"order:{year}:{month}:{offset}")
            line = lines[rng.randrange(len(lines))]
            product = products[rng.randrange(len(products))]
            options = [machine for machine in machines if machine["line_id"] == line["line_id"]]
            machine = options[rng.randrange(len(options))]
            current = _next_available(
                _timestamp(year, month, 1 + rng.randrange(15), 6, zone),
                machine["machine_id"],
                maintenance,
                availability,
            )
            order_events: list[dict] = []
            for event_offset in range(config.events_per_order):
                current = _next_available(current, machine["machine_id"], maintenance, availability)
                end = current + timedelta(minutes=30)
                availability[machine["machine_id"]] = end
                event_number = (number - 1) * config.events_per_order + event_offset + 1
                shift, shift_date = shift_for(current)
                recent_corrective = any(
                    row["machine_id"] == machine["machine_id"]
                    and row["maintenance_type"] == "corrective"
                    and 0
                    <= (current - datetime.fromisoformat(row["ended_at"])).total_seconds()
                    <= 7 * 86400
                    for row in maintenance
                )
                produced = 65 + rng.randrange(75)
                rejected = rng.randrange(1, 4) + (rng.randrange(4) if recent_corrective else 0)
                order_events.append(
                    {
                        "event_id": f"PEV-{year}-{month:02d}-{event_number:06d}",
                        "production_order_id": f"PO-{year}-{number:06d}",
                        "batch_id": f"LOT-{year}-{number:06d}",
                        "product_id": product["product_id"],
                        "line_id": line["line_id"],
                        "machine_id": machine["machine_id"],
                        "event_started_at": current.isoformat(),
                        "event_ended_at": end.isoformat(),
                        "shift": shift,
                        "shift_business_date": shift_date.isoformat(),
                        "quantity_produced": produced,
                        "quantity_rejected": rejected,
                        "status": "completed",
                    }
                )
                current = end
            orders.append(
                {
                    "production_order_id": f"PO-{year}-{number:06d}",
                    "batch_id": f"LOT-{year}-{number:06d}",
                    "product_id": product["product_id"],
                    "line_id": line["line_id"],
                    "planned_quantity": 8000 + rng.randrange(7000),
                    "scheduled_start": order_events[0]["event_started_at"],
                    "scheduled_end": order_events[-1]["event_ended_at"],
                    "status": "completed",
                }
            )
            events.extend(order_events)
    return orders, events


def _inspections(config: SimulationConfig, events: list[dict], defects: list[dict]) -> list[dict]:
    inspections: list[dict] = []
    for event in events:
        event_number = int(event["event_id"].rsplit("-", 1)[1])
        if event_number % 10:
            continue
        rng = _rng(config.seed, f"inspection:{event['event_id']}")
        inspected = min(event["quantity_produced"], 20 + rng.randrange(40))
        defective = min(inspected, event["quantity_rejected"] + rng.randrange(2))
        failed = defective > 2
        inspections.append(
            {
                "inspection_id": f"QIN-{config.start_date.year}-{event_number // 10:06d}",
                "inspection_timestamp": event["event_ended_at"],
                "production_order_id": event["production_order_id"],
                "batch_id": event["batch_id"],
                "product_id": event["product_id"],
                "machine_id": event["machine_id"],
                "inspected_quantity": inspected,
                "defective_quantity": defective,
                "quality_status": "FAIL" if failed else "PASS",
                "defect_code": defects[rng.randrange(len(defects))]["defect_code"]
                if failed
                else None,
            }
        )
    return inspections


def _period(row: dict, dataset: str) -> str:
    return row[
        {
            "production_events": "event_started_at",
            "inspections": "inspection_timestamp",
            "maintenance_events": "started_at",
            "work_orders": "planned_start",
        }[dataset]
    ][:7]


def _record_key(row: dict) -> str:
    return (
        row.get("event_id")
        or row.get("inspection_id")
        or row.get("maintenance_event_id")
        or row.get("work_order_id")
    )


def _entry(dataset: str, row: dict, index: int, rule_id: str, field: str, original: object) -> dict:
    anomaly_type, severity, disposition = RULE_EXPECTATIONS[rule_id]
    return {
        "dataset": dataset,
        "source_system": {
            "production_events": "MES Simulator",
            "inspections": "Quality Department",
            "maintenance_events": "MaintControl",
            "work_orders": "MaintControl",
        }[dataset],
        "effective_period": _period(row, dataset),
        "stable_pre_mutation_locator": _record_key(row),
        "source_row_index": index,
        "affected_field": field,
        "rule_id": rule_id,
        "anomaly_type": anomaly_type,
        "expected_severity": severity,
        "expected_disposition": disposition,
        "original_value": original,
        "injected_value": None,
    }


def _inject(data: GeneratedData, config: SimulationConfig) -> None:
    # Duplicate anomalies must originate from records that remain pristine in the
    # generated source.  Keep this immutable baseline before applying any
    # field-level anomaly, then select only rows untouched by those mutations.
    pristine_duplicate_sources = {
        "production_events": deepcopy(data.production_events),
        "inspections": deepcopy(data.inspections),
    }
    rules = [
        ("production_events", "DQ-PROD-001", "quantity_produced", -1),
        ("production_events", "DQ-PROD-002", "event_id", "bad-event"),
        ("production_events", "DQ-PROD-003", "machine_id", "MCH-999"),
        ("production_events", "DQ-PROD-004", "production_order_id", "PO-2025-999999"),
        ("production_events", "DQ-PROD-005", "status", "unknown"),
        ("inspections", "DQ-QUAL-001", "inspection_id", ""),
        ("inspections", "DQ-QUAL-002", "quality_status", "PENDING"),
        ("inspections", "DQ-QUAL-003", "defective_quantity", 999999),
        ("inspections", "DQ-QUAL-004", "quality_status", "pass"),
        ("maintenance_events", "DQ-MAINT-001", "ended_at", "before_start"),
        ("maintenance_events", "DQ-MAINT-002", "machine_id", "MCH-999"),
        ("maintenance_events", "DQ-MAINT-003", "downtime_minutes", -60),
        ("work_orders", "DQ-MAINT-004", "failure_classification", None),
    ]
    used: set[tuple[str, int]] = set()
    for dataset, rule_id, field, value in rules:
        rows = getattr(data, dataset)
        rate = (
            config.production_anomaly_rate
            if dataset == "production_events"
            else config.quality_anomaly_rate
            if dataset == "inspections"
            else config.maintenance_anomaly_rate
        )
        divisor = sum(1 for candidate in rules if candidate[0] == dataset)
        candidates = [
            (index, row)
            for index, row in enumerate(rows)
            if (dataset, index) not in used
            and (
                rule_id != "DQ-MAINT-004"
                or row["maintenance_type"] == "corrective"
                and row["status"] == "completed"
            )
        ]
        selected = [
            (index, row)
            for index, row in candidates
            if _score(config.seed, f"anomaly:{rule_id}:{_record_key(row)}") < rate / divisor
        ]
        by_period: dict[str, list[tuple[int, dict]]] = {}
        for candidate in candidates:
            by_period.setdefault(_period(candidate[1], dataset), []).append(candidate)
        selected_periods = {_period(row, dataset) for _, row in selected}
        for period, period_candidates in by_period.items():
            if period not in selected_periods:
                selected.append(
                    min(
                        period_candidates,
                        key=lambda candidate: _score(
                            config.seed, f"anomaly:{rule_id}:{_record_key(candidate[1])}"
                        ),
                    )
                )
        for index, row in selected:
            original = row[field]
            entry = _entry(dataset, row, index, rule_id, field, original)
            row[field] = (
                (datetime.fromisoformat(row["started_at"]) - timedelta(hours=1)).isoformat()
                if value == "before_start"
                else value
            )
            entry["injected_value"] = row[field]
            data.anomaly_manifest.append(entry)
            used.add((dataset, index))
    for dataset, rule_id, field in (
        ("production_events", "DQ-PROD-006", "event_id"),
        ("inspections", "DQ-QUAL-005", "inspection_id"),
    ):
        rows = getattr(data, dataset)
        pristine_rows = pristine_duplicate_sources[dataset]
        groups: dict[str, list[tuple[int, dict]]] = {}
        for source_index, row in enumerate(pristine_rows):
            if (dataset, source_index) not in used:
                groups.setdefault(_period(row, dataset), []).append((source_index, row))
        for period, candidates in groups.items():
            source_index, source = min(
                candidates,
                key=lambda candidate: _score(
                    config.seed, f"duplicate:{rule_id}:{_record_key(candidate[1])}"
                ),
            )
            duplicate = deepcopy(source)
            duplicate_index = len(rows)
            rows.append(duplicate)
            source_identifier = _record_key(source)
            source_locator = f"{dataset}:{period}:source:{source_identifier}"
            data.anomaly_manifest.append(
                _entry(dataset, duplicate, duplicate_index, rule_id, field, source[field])
                | {
                    "stable_pre_mutation_locator": source_locator,
                    "source_record_locator": source_locator,
                    "duplicate_record_locator": (
                        f"{dataset}:{period}:duplicate:{source_identifier}"
                    ),
                    "duplicate_of_source_row_index": source_index,
                    "injected_value": duplicate[field],
                }
            )


def generate(config: SimulationConfig, inject_anomalies: bool = True) -> GeneratedData:
    lines, machines, products, defects, targets = _masters(config)
    work_orders, maintenance_events = _maintenance(config, machines)
    orders, events = _orders_and_events(config, lines, machines, products, maintenance_events)
    data = GeneratedData(
        lines,
        machines,
        products,
        orders,
        events,
        _inspections(config, events, defects),
        defects,
        targets,
        work_orders,
        maintenance_events,
        [],
    )
    if inject_anomalies:
        _inject(data, config)
    return data
