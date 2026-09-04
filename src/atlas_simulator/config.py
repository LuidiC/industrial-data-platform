from __future__ import annotations

import tomllib
from dataclasses import dataclass
from datetime import date
from pathlib import Path


@dataclass(frozen=True)
class SimulationConfig:
    seed: int
    start_date: date
    end_date: date
    timezone: str
    output_root: Path
    profile: str
    line_count: int
    machines_per_line: int
    product_count: int
    orders_per_month: int
    events_per_order: int
    production_anomaly_rate: float
    quality_anomaly_rate: float
    maintenance_anomaly_rate: float

    @property
    def months(self) -> list[tuple[int, int]]:
        months: list[tuple[int, int]] = []
        cursor = date(self.start_date.year, self.start_date.month, 1)
        while cursor <= self.end_date:
            months.append((cursor.year, cursor.month))
            cursor = date(cursor.year + (cursor.month == 12), cursor.month % 12 + 1, 1)
        return months


def load_config(path: Path, output_root: Path | None = None) -> SimulationConfig:
    with path.open("rb") as stream:
        value = tomllib.load(stream)
    simulation = value["simulation"]
    topology = value["topology"]
    anomalies = value["anomalies"]
    config = SimulationConfig(
        seed=int(simulation["seed"]),
        start_date=date.fromisoformat(simulation["start_date"]),
        end_date=date.fromisoformat(simulation["end_date"]),
        timezone=str(simulation["timezone"]),
        output_root=output_root or Path(simulation["output_root"]),
        profile=str(simulation["profile"]),
        line_count=int(topology["line_count"]),
        machines_per_line=int(topology["machines_per_line"]),
        product_count=int(topology["product_count"]),
        orders_per_month=int(topology["orders_per_month"]),
        events_per_order=int(topology["events_per_order"]),
        production_anomaly_rate=float(anomalies["production"]),
        quality_anomaly_rate=float(anomalies["quality"]),
        maintenance_anomaly_rate=float(anomalies["maintenance"]),
    )
    if config.start_date.year != config.end_date.year:
        raise ValueError("The portfolio configuration must stay within one calendar year.")
    if config.line_count < 1 or config.machines_per_line < 1 or config.product_count < 1:
        raise ValueError("Topology counts must be positive.")
    return config
