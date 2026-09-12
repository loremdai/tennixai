"""Add the player directory: aliases, bounded ranking snapshots, profile columns.

Identity tables (`players`, `player_external_ids`) are extended in place and
never replaced; downgrade drops only the new tables and new columns.

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-12

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("players", sa.Column("localized_name", sa.Text(), nullable=True))
    op.add_column(
        "players",
        sa.Column("gender", sa.String(length=16), nullable=False, server_default="unknown"),
    )
    op.add_column("players", sa.Column("birth_date", sa.Date(), nullable=True))
    op.add_column("players", sa.Column("image_url", sa.Text(), nullable=True))
    op.add_column(
        "players", sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "players", sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True)
    )
    # Backfill discovery timestamps from the existing audit columns before
    # tightening nullability; rows keep their original discovery moment.
    op.execute(
        "UPDATE players SET first_seen_at = created_at WHERE first_seen_at IS NULL"
    )
    op.execute(
        "UPDATE players SET last_seen_at = updated_at WHERE last_seen_at IS NULL"
    )
    op.alter_column(
        "players",
        "first_seen_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
    )
    op.alter_column(
        "players",
        "last_seen_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
    )

    op.create_table(
        "player_aliases",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "player_id",
            sa.String(length=64),
            sa.ForeignKey("players.id"),
            nullable=False,
        ),
        sa.Column("locale", sa.String(length=16), nullable=False),
        sa.Column("alias", sa.Text(), nullable=False),
        sa.Column("normalized_alias", sa.Text(), nullable=False),
        sa.Column("kind", sa.String(length=24), nullable=False),
        sa.Column("source", sa.String(length=24), nullable=False),
        sa.Column("source_ref", sa.String(length=191), nullable=True),
        sa.Column("model", sa.String(length=64), nullable=True),
        sa.Column("prompt_version", sa.String(length=64), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
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
        sa.UniqueConstraint("player_id", "locale", "normalized_alias", "kind"),
    )
    op.create_index(
        "ix_player_aliases_normalized_alias",
        "player_aliases",
        ["normalized_alias"],
    )
    op.create_index("ix_player_aliases_player_id", "player_aliases", ["player_id"])

    op.create_table(
        "player_rankings",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "player_id",
            sa.String(length=64),
            sa.ForeignKey("players.id"),
            nullable=False,
        ),
        sa.Column("tour", sa.String(length=8), nullable=False),
        sa.Column("ranking_date", sa.Date(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("points", sa.Integer(), nullable=False),
        sa.Column("movement", sa.String(length=16), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tour", "ranking_date", "rank"),
        sa.UniqueConstraint("tour", "ranking_date", "player_id"),
    )
    op.create_index(
        "ix_player_rankings_lookup",
        "player_rankings",
        ["tour", "ranking_date", "rank"],
    )
    op.create_index("ix_player_rankings_player", "player_rankings", ["player_id"])


def downgrade() -> None:
    op.drop_index("ix_player_rankings_player", table_name="player_rankings")
    op.drop_index("ix_player_rankings_lookup", table_name="player_rankings")
    op.drop_table("player_rankings")
    op.drop_index("ix_player_aliases_player_id", table_name="player_aliases")
    op.drop_index("ix_player_aliases_normalized_alias", table_name="player_aliases")
    op.drop_table("player_aliases")
    op.drop_column("players", "last_seen_at")
    op.drop_column("players", "first_seen_at")
    op.drop_column("players", "image_url")
    op.drop_column("players", "birth_date")
    op.drop_column("players", "gender")
    op.drop_column("players", "localized_name")
