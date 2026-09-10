from __future__ import annotations

import argparse
import os
from collections.abc import Sequence
from dataclasses import replace
from datetime import date
from pathlib import Path

import uvicorn

from .api import create_app
from .config import load_config
from .generator import generate
from .postgres import initialize_and_load
from .writers import write_all


def _arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="atlas-sim")
    parser.add_argument("command", choices=("generate", "load-erp", "serve-api"))
    parser.add_argument("--config", type=Path, default=Path("config/simulator.default.toml"))
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--period", help="Optional monthly source slice in YYYY-MM format.")
    parser.add_argument("--dsn", default=os.getenv("ATLAS_ERP_DSN"))
    parser.add_argument(
        "--token", default=os.getenv("MAINTCONTROL_API_TOKEN", "local-development-token")
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host interface for serve-api (default: 127.0.0.1).",
    )
    parser.add_argument("--port", type=int, default=8000)
    return parser.parse_args(argv)


def main() -> None:
    args = _arguments()
    config = load_config(args.config, args.output_root)
    if args.period:
        try:
            year, month = (int(value) for value in args.period.split("-"))
            start = date(year, month, 1)
            end = date(year + (month == 12), month % 12 + 1, 1) - date.resolution
        except ValueError as error:
            raise SystemExit("--period must use YYYY-MM.") from error
        config = replace(config, start_date=start, end_date=end)
    data = generate(config)
    if args.command == "generate":
        paths = write_all(data, config)
        print(f"Generated {len(paths)} source artifacts in {config.output_root}")
    elif args.command == "load-erp":
        if not args.dsn:
            raise SystemExit("Set ATLAS_ERP_DSN or pass --dsn to load AtlasERP.")
        initialize_and_load(args.dsn, data)
        print("AtlasERP schema initialized and loaded.")
    else:
        uvicorn.run(create_app(data, args.token), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
