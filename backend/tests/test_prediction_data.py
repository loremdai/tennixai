"""P3 prediction data source and leakage-gate tests (T61)."""

from datetime import date, timedelta
from pathlib import Path

import pytest

from app.prediction.data import (
    CsvHistoricalMatchSource,
    DataGateError,
    HistoricalMatch,
    InMemoryHistoricalMatchSource,
    chronological_split,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "prediction"


def make_match(
    key: str,
    day: date,
    *,
    player_a: str = "PLR_001",
    player_b: str = "PLR_002",
    winner: str = "a",
) -> HistoricalMatch:
    return HistoricalMatch(
        match_key=key,
        date=day,
        tour="atp",
        surface="hard",
        format="best_of_3",
        player_a=player_a,
        player_b=player_b,
        winner=winner,
        rank_a=10,
        rank_b=20,
    )


def test_csv_source_loads_fixture_rows_chronologically():
    source = CsvHistoricalMatchSource(FIXTURE_DIR)
    matches = source.load()

    assert len(matches) == 200
    dates = [match.date for match in matches]
    assert dates == sorted(dates)
    first = matches[0]
    assert first.match_key == "synth_0000"
    assert first.tour in ("atp", "wta")
    assert first.winner in ("a", "b")
    assert source.metadata.source_id == "tennix-synth-fixture-v1"
    assert source.metadata.license_id == "CC0-1.0-synthetic"


def test_missing_license_metadata_fails_closed(tmp_path):
    (tmp_path / "historical_matches.csv").write_text(
        (FIXTURE_DIR / "historical_matches.csv").read_text(), encoding="utf-8"
    )
    source = CsvHistoricalMatchSource(tmp_path)
    with pytest.raises(DataGateError):
        source.load()


def test_missing_data_file_fails_closed(tmp_path):
    (tmp_path / "source_meta.json").write_text(
        (FIXTURE_DIR / "source_meta.json").read_text(), encoding="utf-8"
    )
    with pytest.raises(DataGateError):
        CsvHistoricalMatchSource(tmp_path).load()


def test_market_or_odds_columns_are_rejected(tmp_path):
    (tmp_path / "historical_matches.csv").write_text(
        "match_key,date,tour,surface,format,player_a,player_b,winner,market_odds\n"
        "m1,2024-01-01,atp,hard,best_of_3,A,B,a,1.5\n",
        encoding="utf-8",
    )
    (tmp_path / "source_meta.json").write_text(
        '{"source_id": "s", "license_id": "l", "description": "d"}', encoding="utf-8"
    )
    with pytest.raises(DataGateError) as error:
        CsvHistoricalMatchSource(tmp_path).load()
    assert "market" in str(error.value).lower()


def test_future_dated_rows_are_rejected(tmp_path):
    future = (date.today() + timedelta(days=3)).isoformat()
    (tmp_path / "historical_matches.csv").write_text(
        "match_key,date,tour,surface,format,player_a,player_b,winner\n"
        f"m1,{future},atp,hard,best_of_3,A,B,a\n",
        encoding="utf-8",
    )
    (tmp_path / "source_meta.json").write_text(
        '{"source_id": "s", "license_id": "l", "description": "d"}', encoding="utf-8"
    )
    with pytest.raises(DataGateError):
        CsvHistoricalMatchSource(tmp_path).load()


def test_duplicate_match_keys_are_rejected():
    day = date(2024, 1, 1)
    source = InMemoryHistoricalMatchSource(
        (make_match("m1", day), make_match("m1", day + timedelta(days=1))),
        source_id="s",
        license_id="l",
    )
    with pytest.raises(DataGateError):
        source.load()


def test_chronological_split_is_ordered_and_disjoint():
    source = CsvHistoricalMatchSource(FIXTURE_DIR)
    matches = source.load()

    splits = chronological_split(matches, train=0.6, validation=0.2, test=0.2)

    assert len(splits.train) == 120
    assert len(splits.validation) == 40
    assert len(splits.test) == 40
    train_keys = {match.match_key for match in splits.train}
    val_keys = {match.match_key for match in splits.validation}
    test_keys = {match.match_key for match in splits.test}
    assert not (train_keys & val_keys)
    assert not (val_keys & test_keys)
    assert not (train_keys & test_keys)
    assert max(m.date for m in splits.train) <= min(m.date for m in splits.validation)
    assert max(m.date for m in splits.validation) <= min(m.date for m in splits.test)


def test_split_rejects_a_match_appearing_in_two_splits():
    day = date(2024, 1, 1)
    matches = tuple(make_match(f"m{i}", day + timedelta(days=i)) for i in range(10))
    duplicated = matches + (
        HistoricalMatch(
            match_key="m0",
            date=day + timedelta(days=20),
            tour="atp",
            surface="hard",
            format="best_of_3",
            player_a="PLR_001",
            player_b="PLR_002",
            winner="b",
            rank_a=10,
            rank_b=20,
        ),
    )
    with pytest.raises(DataGateError):
        chronological_split(duplicated, train=0.6, validation=0.2, test=0.2)
