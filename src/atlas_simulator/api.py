from __future__ import annotations

import base64
import binascii
from datetime import datetime

from fastapi import Depends, FastAPI, Header, HTTPException, Query

from .generator import GeneratedData


def _cursor(value: str | None) -> int:
    if not value:
        return 0
    try:
        offset = int(base64.urlsafe_b64decode(value.encode()).decode())
    except (ValueError, UnicodeDecodeError, binascii.Error) as error:
        raise HTTPException(status_code=422, detail="Malformed cursor") from error
    if offset < 0:
        raise HTTPException(status_code=422, detail="Cursor offset must not be negative")
    return offset


def _encode_cursor(value: int) -> str:
    return base64.urlsafe_b64encode(str(value).encode()).decode()


def create_app(data: GeneratedData, api_token: str = "local-development-token") -> FastAPI:
    app = FastAPI(title="MaintControl", version="1.0.0")
    known_machine_ids = {row["machine_id"] for row in data.machines}

    def authenticate(authorization: str | None = Header(default=None)) -> None:
        if authorization != f"Bearer {api_token}":
            raise HTTPException(status_code=401, detail="Invalid API token")

    def response(rows: list[dict], cursor: str | None, page_size: int) -> dict:
        offset = _cursor(cursor)
        page = rows[offset : offset + page_size]
        next_cursor = _encode_cursor(offset + page_size) if offset + page_size < len(rows) else None
        return {
            "data": page,
            "pagination": {
                "page_size": page_size,
                "next_cursor": next_cursor,
                "has_more": next_cursor is not None,
            },
            "generated_at": "2025-12-31T23:59:59-03:00",
        }

    def validate_range(occurred_from: datetime | None, occurred_to: datetime | None) -> None:
        if (occurred_from and occurred_from.tzinfo is None) or (
            occurred_to and occurred_to.tzinfo is None
        ):
            raise HTTPException(status_code=422, detail="Timestamps must include a timezone offset")
        if occurred_from and occurred_to and occurred_from > occurred_to:
            raise HTTPException(
                status_code=422, detail="occurred_from must not be after occurred_to"
            )

    @app.get("/api/v1/work-orders", dependencies=[Depends(authenticate)])
    def work_orders(
        occurred_from: datetime | None = None,
        occurred_to: datetime | None = None,
        machine_id: str | None = Query(default=None, pattern=r"^MCH-\d{3}$"),
        cursor: str | None = None,
        page_size: int = Query(default=100, ge=1, le=500),
    ) -> dict:
        validate_range(occurred_from, occurred_to)
        rows = (
            []
            if machine_id is not None and machine_id not in known_machine_ids
            else [
                row
                for row in data.work_orders
                if machine_id is None or row["machine_id"] == machine_id
                if occurred_from is None
                or datetime.fromisoformat(row["opened_at"]) >= occurred_from
                if occurred_to is None or datetime.fromisoformat(row["opened_at"]) <= occurred_to
            ]
        )
        return response(
            sorted(rows, key=lambda row: (row["opened_at"], row["work_order_id"])),
            cursor,
            page_size,
        )

    @app.get("/api/v1/maintenance-events", dependencies=[Depends(authenticate)])
    def maintenance_events(
        occurred_from: datetime | None = None,
        occurred_to: datetime | None = None,
        machine_id: str | None = Query(default=None, pattern=r"^MCH-\d{3}$"),
        cursor: str | None = None,
        page_size: int = Query(default=100, ge=1, le=500),
    ) -> dict:
        validate_range(occurred_from, occurred_to)
        if machine_id is not None and machine_id not in known_machine_ids:
            return response([], cursor, page_size)
        rows = []
        for row in data.maintenance_events:
            started = datetime.fromisoformat(row["started_at"])
            if (
                (occurred_from is None or started >= occurred_from)
                and (occurred_to is None or started <= occurred_to)
                and (machine_id is None or row["machine_id"] == machine_id)
            ):
                rows.append(row)
        return response(
            sorted(rows, key=lambda row: (row["started_at"], row["maintenance_event_id"])),
            cursor,
            page_size,
        )

    return app
