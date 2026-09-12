"""P2 persistence schema and typed settings (unit level, no database required).

Behavior against a real PostgreSQL runs in tests/integration under the
`infrastructure` marker.
"""

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError
from sqlalchemy import UniqueConstraint

from app.config import Settings
from app.persistence.models import (
    MatchExternalIdRow,
    MatchStateSnapshotRow,
    PlayerExternalIdRow,
    PlayerRow,
    PointEventRevisionRow,
    PointEventRow,
    RawProviderEventRow,
    TournamentExternalIdRow,
)

FIXED_NOW = datetime(2026, 9, 9, 10, 0, tzinfo=timezone.utc)


def _unique_column_sets(table) -> set[tuple[str, ...]]:
    return {
        tuple(sorted(column.name for column in constraint.columns))
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }


def _index_column_sets(table) -> set[tuple[str, ...]]:
    return {
        tuple(sorted(column.name for column in index.columns))
        for index in table.indexes
    }


@pytest.mark.parametrize(
    "row_model",
    [PlayerExternalIdRow, TournamentExternalIdRow, MatchExternalIdRow],
)
def test_external_id_tables_are_unique_per_provider_and_external_id(row_model) -> None:
    uniques = _unique_column_sets(row_model.__table__)
    assert ("external_id", "provider") in uniques


def test_point_events_declare_match_sequence_identity() -> None:
    uniques = _unique_column_sets(PointEventRow.__table__)
    assert ("match_id", "sequence") in uniques


def test_point_revisions_are_append_identifiable() -> None:
    uniques = _unique_column_sets(PointEventRevisionRow.__table__)
    assert ("point_event_id", "revision") in uniques
    columns = {column.name for column in PointEventRevisionRow.__table__.columns}
    assert {"before_state", "after_state", "revised_at"} <= columns


def test_match_state_snapshots_keep_one_current_row_per_match() -> None:
    table = MatchStateSnapshotRow.__table__
    primary_key = {column.name for column in table.primary_key.columns}
    assert primary_key == {"match_id"}
    columns = {column.name for column in table.columns}
    assert {"state", "state_version", "connection_status", "as_of"} <= columns


def test_raw_events_index_observed_at_for_retention_cutoff() -> None:
    table = RawProviderEventRow.__table__
    assert ("observed_at",) in _index_column_sets(table)
    columns = {column.name for column in table.columns}
    assert {"provider", "channel", "kind", "payload", "observed_at"} <= columns


def test_settings_have_safe_local_defaults() -> None:
    settings = Settings(_env_file=None)

    assert (
        settings.database_url
        == "postgresql+asyncpg://tennix:tennix@127.0.0.1:5432/tennix"
    )
    assert settings.redis_url == "redis://127.0.0.1:6379/0"
    assert settings.raw_payload_retention_days == 14
    assert settings.max_live_subscriptions == 8
    assert settings.viewer_lease_seconds == 45
    assert settings.subscription_grace_seconds == 60


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        ("raw_payload_retention_days", 0),
        ("raw_payload_retention_days", 91),
        ("max_live_subscriptions", 0),
        ("max_live_subscriptions", 101),
        ("viewer_lease_seconds", 29),
        ("viewer_lease_seconds", 121),
        ("subscription_grace_seconds", -1),
        ("subscription_grace_seconds", 301),
    ],
)
def test_settings_reject_out_of_range_operational_bounds(
    field_name: str, invalid_value: int
) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **{field_name: invalid_value})


def test_raw_retention_cutoff_is_exclusive_and_bounded() -> None:
    from app.persistence.repositories import raw_retention_cutoff

    cutoff = raw_retention_cutoff(FIXED_NOW, retention_days=14)
    assert cutoff == FIXED_NOW - timedelta(days=14)

    with pytest.raises(ValueError):
        raw_retention_cutoff(FIXED_NOW, retention_days=0)


def test_player_aliases_are_unique_per_player_locale_normalized_kind() -> None:
    from app.persistence.models import PlayerAliasRow

    uniques = _unique_column_sets(PlayerAliasRow.__table__)
    assert ("kind", "locale", "normalized_alias", "player_id") in uniques
    indexes = _index_column_sets(PlayerAliasRow.__table__)
    assert ("normalized_alias",) in indexes


def test_player_rankings_are_unique_per_tour_date_rank_and_player() -> None:
    from app.persistence.models import PlayerRankingRow

    uniques = _unique_column_sets(PlayerRankingRow.__table__)
    assert ("rank", "ranking_date", "tour") in uniques
    assert ("player_id", "ranking_date", "tour") in uniques
    indexes = _index_column_sets(PlayerRankingRow.__table__)
    assert ("rank", "ranking_date", "tour") in indexes
    assert ("player_id",) in indexes


def test_players_carry_directory_columns() -> None:
    columns = PlayerRow.__table__.columns
    for name in (
        "localized_name",
        "gender",
        "birth_date",
        "image_url",
        "first_seen_at",
        "last_seen_at",
    ):
        assert name in columns
