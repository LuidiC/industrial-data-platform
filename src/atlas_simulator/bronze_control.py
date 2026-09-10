from __future__ import annotations

import hashlib
import re
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path, PurePosixPath

STALE_STARTED_AFTER = timedelta(hours=2)
MES_FILE_PATTERN = re.compile(r"^production_events_(?P<year>\d{4})[-_](?P<month>\d{2})\.csv$")


class AuditStatus(StrEnum):
    STARTED = "STARTED"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    SKIPPED_ALREADY_INGESTED = "SKIPPED_ALREADY_INGESTED"
    CONFLICT_SOURCE_CHANGED = "CONFLICT_SOURCE_CHANGED"
    SUCCEEDED_REPLAY = "SUCCEEDED_REPLAY"


class PlanAction(StrEnum):
    INGEST = "INGEST"
    SKIP = "SKIP"
    CONFLICT = "CONFLICT"
    BLOCK = "BLOCK"


@dataclass(frozen=True)
class SourceCandidate:
    source_system: str
    source_object: str
    source_identity_key: str
    source_file: str
    source_period: str | None
    transport_source: str
    destination_path: str
    content_sha256: str
    source_size_bytes: int


@dataclass(frozen=True)
class AuditRecord:
    audit_id: str
    batch_id: str
    source_identity_key: str
    content_sha256: str
    status: AuditStatus
    ingestion_started_at: datetime
    source_file: str
    source_period: str | None = None


@dataclass(frozen=True)
class PlanDecision:
    action: PlanAction
    terminal_status: AuditStatus | None
    error_code: str | None
    replay_of_batch_id: str | None
    stale_audit_ids: tuple[str, ...] = ()


def utc_now() -> datetime:
    return datetime.now(UTC)


def new_batch_id(now: datetime | None = None) -> str:
    timestamp = (now or utc_now()).astimezone(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    return f"{timestamp}-{uuid.uuid4().hex[:12]}"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def source_identity(source_system: str, source_object: str, period: str, name: str) -> str:
    return "|".join((source_system, source_object, period, name))


def bronze_file_path(
    *,
    source_system: str,
    source_object: str,
    batch_id: str,
    file_name: str,
    source_period: str | None = None,
    snapshot_date: str | None = None,
    extraction_date: str | None = None,
) -> str:
    root = PurePosixPath("Files/raw") / source_system / source_object
    if source_system == "atlas_erp":
        if snapshot_date is None:
            raise ValueError("AtlasERP paths require snapshot_date.")
        root /= f"snapshot_date={snapshot_date}"
    elif source_system in {"mes", "quality"}:
        if source_period is None:
            raise ValueError(f"{source_system} paths require source_period.")
        root /= f"source_period={source_period}"
    elif source_system == "maintcontrol":
        if extraction_date is None:
            raise ValueError("MaintControl paths require extraction_date.")
        root /= f"extraction_date={extraction_date}"
    return str(root / f"batch_id={batch_id}" / file_name)


def candidate_from_file(
    path: Path,
    *,
    source_system: str,
    source_object: str,
    source_period: str,
    transport_source: str,
    batch_id: str,
) -> SourceCandidate:
    if not path.is_file():
        raise FileNotFoundError(path)
    return SourceCandidate(
        source_system=source_system,
        source_object=source_object,
        source_identity_key=source_identity(source_system, source_object, source_period, path.name),
        source_file=path.name,
        source_period=source_period,
        transport_source=transport_source,
        destination_path=bronze_file_path(
            source_system=source_system,
            source_object=source_object,
            batch_id=batch_id,
            file_name=path.name,
            source_period=source_period,
        ),
        content_sha256=sha256_file(path),
        source_size_bytes=path.stat().st_size,
    )


def inventory_mes(root: Path, *, transport_source: str, batch_id: str) -> list[SourceCandidate]:
    candidates: list[SourceCandidate] = []
    for path in sorted(root.glob("production_events_*.csv")):
        match = MES_FILE_PATTERN.fullmatch(path.name)
        if match is None:
            continue
        period = f"{match.group('year')}-{match.group('month')}"
        candidates.append(
            candidate_from_file(
                path,
                source_system="mes",
                source_object="production_events",
                source_period=period,
                transport_source=transport_source,
                batch_id=batch_id,
            )
        )
    return candidates


def decide_attempt(
    candidate: SourceCandidate,
    existing: Iterable[AuditRecord],
    *,
    now: datetime,
    force_reprocess: bool = False,
    replay_of_batch_id: str | None = None,
) -> PlanDecision:
    relevant = [
        record for record in existing if record.source_identity_key == candidate.source_identity_key
    ]
    fresh_started = [
        record
        for record in relevant
        if record.status == AuditStatus.STARTED
        and now - record.ingestion_started_at < STALE_STARTED_AFTER
    ]
    if fresh_started:
        return PlanDecision(PlanAction.BLOCK, AuditStatus.FAILED, "CONCURRENT_RUN", None)

    stale_ids = tuple(
        record.audit_id
        for record in relevant
        if record.status == AuditStatus.STARTED
        and now - record.ingestion_started_at >= STALE_STARTED_AFTER
    )
    successful = [
        record
        for record in relevant
        if record.status in {AuditStatus.SUCCEEDED, AuditStatus.SUCCEEDED_REPLAY}
    ]
    successful.sort(key=lambda record: record.ingestion_started_at, reverse=True)

    if force_reprocess:
        replay = next(
            (record for record in successful if record.batch_id == replay_of_batch_id), None
        )
        if replay is None:
            return PlanDecision(
                PlanAction.CONFLICT,
                AuditStatus.CONFLICT_SOURCE_CHANGED,
                "INVALID_REPLAY_REFERENCE",
                replay_of_batch_id,
                stale_ids,
            )
        if (
            replay.content_sha256 != candidate.content_sha256
            or replay.source_file != candidate.source_file
            or replay.source_period != candidate.source_period
        ):
            return PlanDecision(
                PlanAction.CONFLICT,
                AuditStatus.CONFLICT_SOURCE_CHANGED,
                "REPLAY_SOURCE_MISMATCH",
                replay_of_batch_id,
                stale_ids,
            )
        return PlanDecision(
            PlanAction.INGEST, None, None, replay_of_batch_id, stale_audit_ids=stale_ids
        )

    if successful:
        latest = successful[0]
        if latest.content_sha256 == candidate.content_sha256:
            return PlanDecision(
                PlanAction.SKIP,
                AuditStatus.SKIPPED_ALREADY_INGESTED,
                "ALREADY_INGESTED",
                None,
                stale_ids,
            )
        return PlanDecision(
            PlanAction.CONFLICT,
            AuditStatus.CONFLICT_SOURCE_CHANGED,
            "SOURCE_IDENTITY_HASH_CHANGED",
            None,
            stale_ids,
        )

    return PlanDecision(PlanAction.INGEST, None, None, None, stale_audit_ids=stale_ids)
