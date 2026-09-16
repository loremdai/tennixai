"""Replaceable historical match source with leakage gates (T61).

Historical training data is read from a local path through this replaceable
source; the repository only ever commits the sanitized minimal fixture. Any
column that smells like market/odds/price/book/resolution data is rejected
before a single row is parsed, future-dated rows and duplicate matches fail
closed, and chronological splitting never places one match in two splits.
"""

import csv
import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Protocol

FORBIDDEN_COLUMN_PATTERNS = (
    "market",
    "odds",
    "price",
    "book",
    "resolution",
    "implied",
    "probability",
    "payout",
    "spread",
    "line",
)

REQUIRED_COLUMNS = (
    "match_key",
    "date",
    "tour",
    "surface",
    "format",
    "player_a",
    "player_b",
    "winner",
)


class DataGateError(Exception):
    """A data/license/leakage gate refused the source."""


@dataclass(frozen=True)
class HistoricalMatch:
    match_key: str
    date: date
    tour: str
    surface: str
    format: str
    player_a: str
    player_b: str
    winner: str  # "a" or "b"
    rank_a: int | None = None
    rank_b: int | None = None


@dataclass(frozen=True)
class DataSourceMetadata:
    source_id: str
    license_id: str | None
    description: str = ""


@dataclass(frozen=True)
class SplitSets:
    train: tuple[HistoricalMatch, ...]
    validation: tuple[HistoricalMatch, ...]
    test: tuple[HistoricalMatch, ...]


class HistoricalMatchSource(Protocol):
    @property
    def metadata(self) -> DataSourceMetadata: ...

    @property
    def raw_columns(self) -> tuple[str, ...]: ...

    def load(self) -> tuple[HistoricalMatch, ...]: ...


def _check_forbidden_columns(columns: Sequence[str]) -> None:
    for column in columns:
        lowered = column.lower()
        for pattern in FORBIDDEN_COLUMN_PATTERNS:
            if pattern in lowered:
                raise DataGateError(
                    f"forbidden market-derived column rejected: {column!r} "
                    f"(pattern {pattern!r})"
                )


def _validate_rows(rows: Sequence[HistoricalMatch], *, today: date | None) -> None:
    if not rows:
        raise DataGateError("empty dataset")
    seen: set[str] = set()
    for row in rows:
        if row.match_key in seen:
            raise DataGateError(f"duplicate match_key: {row.match_key}")
        seen.add(row.match_key)
        if row.winner not in ("a", "b"):
            raise DataGateError(f"invalid winner label for {row.match_key}")
        if today is not None and row.date > today:
            raise DataGateError(f"future-dated row rejected: {row.match_key}")


class CsvHistoricalMatchSource:
    """Directory-based source: `historical_matches.csv` + `source_meta.json`.

    Fails closed when the data file, the metadata file or the license
    identifier is missing.
    """

    def __init__(self, directory: Path | str, *, today: date | None = None) -> None:
        self._directory = Path(directory)
        self._today = today
        self._columns: tuple[str, ...] = ()
        self._metadata: DataSourceMetadata | None = None

    @property
    def csv_path(self) -> Path:
        return self._directory / "historical_matches.csv"

    @property
    def metadata(self) -> DataSourceMetadata:
        if self._metadata is not None:
            return self._metadata
        meta_path = self._directory / "source_meta.json"
        if not meta_path.is_file():
            raise DataGateError(
                "source metadata missing; a licensed source identifier is required"
            )
        try:
            payload = json.loads(meta_path.read_text(encoding="utf-8"))
        except ValueError as exc:
            raise DataGateError("source metadata is not valid JSON") from exc
        source_id = str(payload.get("source_id") or "").strip()
        license_id = payload.get("license_id")
        license_id = str(license_id).strip() if license_id else None
        self._metadata = DataSourceMetadata(
            source_id=source_id,
            license_id=license_id,
            description=str(payload.get("description") or ""),
        )
        return self._metadata

    @property
    def raw_columns(self) -> tuple[str, ...]:
        if not self._columns:
            self.load()
        return self._columns

    def load(self) -> tuple[HistoricalMatch, ...]:
        metadata = self.metadata
        if not metadata.source_id or not metadata.license_id:
            raise DataGateError(
                "source/license identifier missing; refusing to train on "
                "unlicensed data"
            )
        if not self.csv_path.is_file():
            raise DataGateError(f"historical data file missing in {self._directory}")
        with self.csv_path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            columns = tuple(reader.fieldnames or ())
            self._columns = columns
            _check_forbidden_columns(columns)
            missing = [name for name in REQUIRED_COLUMNS if name not in columns]
            if missing:
                raise DataGateError(f"missing required columns: {missing}")
            rows: list[HistoricalMatch] = []
            today = self._today or date.today()
            for raw in reader:
                try:
                    rows.append(
                        HistoricalMatch(
                            match_key=raw["match_key"],
                            date=date.fromisoformat(raw["date"]),
                            tour=(raw.get("tour") or "unknown").strip().lower(),
                            surface=(raw.get("surface") or "unknown").strip().lower(),
                            format=(raw.get("format") or "unknown").strip().lower(),
                            player_a=raw["player_a"],
                            player_b=raw["player_b"],
                            winner=(raw["winner"] or "").strip().lower(),
                            rank_a=_optional_int(raw.get("rank_a")),
                            rank_b=_optional_int(raw.get("rank_b")),
                        )
                    )
                except (KeyError, ValueError) as exc:
                    raise DataGateError(f"malformed historical row: {exc}") from exc
            _validate_rows(rows, today=today)
        rows.sort(key=lambda match: (match.date, match.match_key))
        return tuple(rows)


def _optional_int(value: str | None) -> int | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return int(value)
    except ValueError:
        return None


class InMemoryHistoricalMatchSource:
    """Deterministic in-memory source for tests and replayable experiments."""

    def __init__(
        self,
        matches: Sequence[HistoricalMatch],
        *,
        source_id: str,
        license_id: str | None,
        description: str = "in-memory",
    ) -> None:
        self._matches = tuple(matches)
        self._metadata = DataSourceMetadata(
            source_id=source_id, license_id=license_id, description=description
        )

    @property
    def metadata(self) -> DataSourceMetadata:
        return self._metadata

    @property
    def raw_columns(self) -> tuple[str, ...]:
        return REQUIRED_COLUMNS

    def load(self) -> tuple[HistoricalMatch, ...]:
        _validate_rows(self._matches, today=None)
        return tuple(
            sorted(self._matches, key=lambda match: (match.date, match.match_key))
        )


def chronological_split(
    matches: Sequence[HistoricalMatch],
    *,
    train: float = 0.6,
    validation: float = 0.2,
    test: float = 0.2,
) -> SplitSets:
    """Date-ordered split. Every row of one match stays in one split."""
    keys = [match.match_key for match in matches]
    if len(set(keys)) != len(keys):
        raise DataGateError(
            "a match appears more than once; chronological splitting refuses "
            "duplicate matches across splits"
        )
    ordered = sorted(matches, key=lambda match: (match.date, match.match_key))
    total = len(ordered)
    train_end = int(total * train)
    validation_end = int(total * (train + validation))
    return SplitSets(
        train=tuple(ordered[:train_end]),
        validation=tuple(ordered[train_end:validation_end]),
        test=tuple(ordered[validation_end:]),
    )
