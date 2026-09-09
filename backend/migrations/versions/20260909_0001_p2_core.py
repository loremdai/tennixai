"""P2 core schema: identity, canonical state, points, statistics, momentum, raw events.

Revision ID: 0001
Revises:
Create Date: 2026-09-09

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "players",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("country_code", sa.String(length=8), nullable=True),
        sa.Column("ranking", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_table(
        "tournaments",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("tour", sa.String(length=32), nullable=True),
        sa.Column("circuit", sa.String(length=16), nullable=False),
        sa.Column("gender", sa.String(length=16), nullable=False),
        sa.Column("discipline", sa.String(length=16), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_table(
        "matches",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("status", sa.String(length=16), nullable=True),
        sa.Column("player1_id", sa.String(length=64), sa.ForeignKey("players.id"), nullable=True),
        sa.Column("player2_id", sa.String(length=64), sa.ForeignKey("players.id"), nullable=True),
        sa.Column("tournament_id", sa.String(length=64), sa.ForeignKey("tournaments.id"), nullable=True),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("round", sa.Text(), nullable=True),
        sa.Column("surface", sa.String(length=32), nullable=True),
        sa.Column("indoor", sa.Boolean(), nullable=True),
        sa.Column("format", sa.String(length=16), nullable=True),
        sa.Column("winner_player_id", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_table(
        "player_external_ids",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("internal_id", sa.String(length=64), sa.ForeignKey("players.id"), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("external_id", sa.String(length=191), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("provider", "external_id"),
        sa.UniqueConstraint("internal_id", "provider"),
    )
    op.create_index(
        "ix_player_external_ids_internal_id", "player_external_ids", ["internal_id"]
    )
    op.create_table(
        "tournament_external_ids",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("internal_id", sa.String(length=64), sa.ForeignKey("tournaments.id"), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("external_id", sa.String(length=191), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("provider", "external_id"),
        sa.UniqueConstraint("internal_id", "provider"),
    )
    op.create_index(
        "ix_tournament_external_ids_internal_id",
        "tournament_external_ids",
        ["internal_id"],
    )
    op.create_table(
        "match_external_ids",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("internal_id", sa.String(length=64), sa.ForeignKey("matches.id"), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("external_id", sa.String(length=191), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("provider", "external_id"),
        sa.UniqueConstraint("internal_id", "provider"),
    )
    op.create_index(
        "ix_match_external_ids_internal_id", "match_external_ids", ["internal_id"]
    )
    op.create_table(
        "match_state_snapshots",
        sa.Column("match_id", sa.String(length=64), sa.ForeignKey("matches.id"), primary_key=True),
        sa.Column("state", JSONB(), nullable=False),
        sa.Column("state_version", sa.Integer(), nullable=False),
        sa.Column(
            "connection_status", sa.String(length=16), nullable=False
        ),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_table(
        "point_events",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("match_id", sa.String(length=64), sa.ForeignKey("matches.id"), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("set_number", sa.Integer(), nullable=False),
        sa.Column("game_number", sa.Integer(), nullable=False),
        sa.Column("point_number", sa.Integer(), nullable=False),
        sa.Column("server_player_id", sa.String(length=64), nullable=True),
        sa.Column("winner_player_id", sa.String(length=64), nullable=True),
        sa.Column("score_before", JSONB(), nullable=True),
        sa.Column("score_after", JSONB(), nullable=False),
        sa.Column("is_break_point", sa.Boolean(), nullable=False),
        sa.Column("is_set_point", sa.Boolean(), nullable=False),
        sa.Column("is_match_point", sa.Boolean(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("source_fingerprint", sa.String(length=128), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("quality", JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("match_id", "sequence"),
    )
    op.create_index("ix_point_events_match_id", "point_events", ["match_id"])
    op.create_table(
        "point_event_revisions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("point_event_id", sa.String(length=64), sa.ForeignKey("point_events.id"), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("before_state", JSONB(), nullable=False),
        sa.Column("after_state", JSONB(), nullable=False),
        sa.Column("revised_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.String(length=64), nullable=True),
        sa.UniqueConstraint("point_event_id", "revision"),
    )
    op.create_index(
        "ix_point_event_revisions_point_event_id",
        "point_event_revisions",
        ["point_event_id"],
    )
    op.create_table(
        "match_statistics",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("match_id", sa.String(length=64), sa.ForeignKey("matches.id"), nullable=False),
        sa.Column("name", sa.String(length=48), nullable=False),
        sa.Column("period", sa.String(length=24), nullable=False),
        sa.Column("player1_value", sa.Float(), nullable=True),
        sa.Column("player2_value", sa.Float(), nullable=True),
        sa.Column("unit", sa.String(length=24), nullable=True),
        sa.Column("provenance", sa.String(length=24), nullable=False),
        sa.Column("availability", sa.String(length=16), nullable=False),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("match_id", "name", "period"),
    )
    op.create_index("ix_match_statistics_match_id", "match_statistics", ["match_id"])
    op.create_table(
        "statistic_observations",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("match_id", sa.String(length=64), sa.ForeignKey("matches.id"), nullable=False),
        sa.Column("name", sa.String(length=48), nullable=False),
        sa.Column("period", sa.String(length=24), nullable=False),
        sa.Column("player1_value", sa.Float(), nullable=True),
        sa.Column("player2_value", sa.Float(), nullable=True),
        sa.Column("availability", sa.String(length=16), nullable=False),
        sa.Column("state_version", sa.Integer(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_statistic_observations_match_id", "statistic_observations", ["match_id"]
    )
    op.create_table(
        "momentum_observations",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("match_id", sa.String(length=64), sa.ForeignKey("matches.id"), nullable=False),
        sa.Column("point_sequence", sa.Integer(), nullable=False),
        sa.Column("state_version", sa.Integer(), nullable=False),
        sa.Column("algorithm_version", sa.String(length=48), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("leader_player_id", sa.String(length=64), nullable=True),
        sa.Column("is_provisional", sa.Boolean(), nullable=False),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("input_summary", sa.Text(), nullable=False),
        sa.UniqueConstraint("match_id", "algorithm_version", "point_sequence"),
    )
    op.create_index(
        "ix_momentum_observations_match_id", "momentum_observations", ["match_id"]
    )
    op.create_table(
        "raw_provider_events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("match_id", sa.String(length=64), nullable=True),
        sa.Column("external_match_id", sa.String(length=191), nullable=True),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("channel", sa.String(length=16), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("payload", JSONB(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_raw_provider_events_observed_at", "raw_provider_events", ["observed_at"]
    )
    op.create_index(
        "ix_raw_provider_events_external_match_id",
        "raw_provider_events",
        ["external_match_id"],
    )


def downgrade() -> None:
    op.drop_table("raw_provider_events")
    op.drop_table("momentum_observations")
    op.drop_table("statistic_observations")
    op.drop_table("match_statistics")
    op.drop_table("point_event_revisions")
    op.drop_table("point_events")
    op.drop_table("match_state_snapshots")
    op.drop_table("match_external_ids")
    op.drop_table("tournament_external_ids")
    op.drop_table("player_external_ids")
    op.drop_table("matches")
    op.drop_table("tournaments")
    op.drop_table("players")
