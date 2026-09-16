"""Versionable data license/coverage/leakage audit (T61).

Runs before any training. The report contains aggregate facts only — never
raw rows or player identifiers — and is serialized alongside benchmark
artifacts so every model card can prove its data provenance.
"""

import json
from collections import Counter
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import date

from app.prediction.data import (
    FORBIDDEN_COLUMN_PATTERNS,
    DataGateError,
    HistoricalMatch,
    HistoricalMatchSource,
)


@dataclass(frozen=True)
class AuditReport:
    source_id: str
    license_id: str | None
    passed: bool
    reasons: tuple[str, ...]
    total_matches: int = 0
    date_range: tuple[str, str] | None = None
    tour_counts: dict[str, int] | None = None
    surface_counts: dict[str, int] | None = None
    format_counts: dict[str, int] | None = None
    player_cold_start_ratio: float = 0.0
    duplicate_match_keys: int = 0
    future_dated_rows: int = 0
    forbidden_columns: tuple[str, ...] = ()
    missing_field_counts: dict[str, int] | None = None

    def to_json(self) -> str:
        return json.dumps(asdict(self), default=str, sort_keys=True)


def _forbidden_columns(columns: Sequence[str]) -> tuple[str, ...]:
    found = []
    for column in columns:
        lowered = column.lower()
        for pattern in FORBIDDEN_COLUMN_PATTERNS:
            if pattern in lowered:
                found.append(column)
                break
    return tuple(found)


def _cold_start_ratio(matches: Sequence[HistoricalMatch]) -> float:
    """Share of players whose first appearance falls inside the earliest
    quartile of the dataset — a proxy for cold-start coverage."""
    if not matches:
        return 0.0
    ordered = sorted(matches, key=lambda match: match.date)
    boundary_index = max(1, len(ordered) // 4)
    boundary = ordered[boundary_index - 1].date
    first_seen: dict[str, date] = {}
    for match in ordered:
        for player in (match.player_a, match.player_b):
            first_seen.setdefault(player, match.date)
    if not first_seen:
        return 0.0
    cold = sum(1 for seen in first_seen.values() if seen <= boundary)
    return cold / len(first_seen)


def audit_source(
    source: HistoricalMatchSource, *, today: date | None = None
) -> AuditReport:
    today = today or date.today()
    reasons: list[str] = []
    metadata = source.metadata
    if not metadata.source_id:
        reasons.append("source identifier missing")
    if not metadata.license_id:
        reasons.append("license identifier missing; training not permitted")

    try:
        forbidden = _forbidden_columns(source.raw_columns)
    except DataGateError:
        forbidden = ()  # the load failure below records the gate reason
    if forbidden:
        reasons.append(f"forbidden market-derived columns: {list(forbidden)}")

    matches: tuple[HistoricalMatch, ...] = ()
    try:
        matches = source.load()
    except DataGateError as exc:
        reasons.append(f"data gate: {exc}")

    duplicates = 0
    future_rows = 0
    if matches:
        keys = Counter(match.match_key for match in matches)
        duplicates = sum(count - 1 for count in keys.values() if count > 1)
        future_rows = sum(1 for match in matches if match.date > today)
        if duplicates:
            reasons.append(f"{duplicates} duplicate match keys")
        if future_rows:
            reasons.append(f"{future_rows} future-dated rows")
    elif not any(reason.startswith("data gate") for reason in reasons):
        reasons.append("empty dataset")

    missing_fields = {
        "rank_a": sum(1 for match in matches if match.rank_a is None),
        "rank_b": sum(1 for match in matches if match.rank_b is None),
        "surface": sum(1 for match in matches if match.surface == "unknown"),
        "format": sum(1 for match in matches if match.format == "unknown"),
    }

    date_range = None
    if matches:
        date_range = (
            min(match.date for match in matches).isoformat(),
            max(match.date for match in matches).isoformat(),
        )

    return AuditReport(
        source_id=metadata.source_id,
        license_id=metadata.license_id,
        passed=not reasons,
        reasons=tuple(reasons),
        total_matches=len(matches),
        date_range=date_range,
        tour_counts=dict(Counter(match.tour for match in matches)),
        surface_counts=dict(Counter(match.surface for match in matches)),
        format_counts=dict(Counter(match.format for match in matches)),
        player_cold_start_ratio=_cold_start_ratio(matches),
        duplicate_match_keys=duplicates,
        future_dated_rows=future_rows,
        forbidden_columns=forbidden,
        missing_field_counts=missing_fields,
    )
