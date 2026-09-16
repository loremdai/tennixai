"""Add the P3 market and paper ledger schema.

Creates the twelve P3 tables: market identity/private external mapping,
immutable rules evidence, exact match links, decision-relevant observations,
versioned prediction/decision evidence, the one-shot paper ledger
(intents/fills/positions/track results) and provider resolutions.
Downgrade drops only the new tables; P2 tables are untouched.

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-16

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


NUMERIC = sa.Numeric(precision=20, scale=8)
TZ = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "markets",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("question", sa.Text(), nullable=True),
        sa.Column("outcome_a_player_id", sa.String(length=64), nullable=True),
        sa.Column("outcome_a_name", sa.Text(), nullable=True),
        sa.Column("outcome_b_player_id", sa.String(length=64), nullable=True),
        sa.Column("outcome_b_name", sa.Text(), nullable=True),
        sa.Column(
            "status", sa.String(length=16), nullable=False, server_default="unknown"
        ),
        sa.Column("rules_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("match_id", sa.String(length=64), nullable=True),
        sa.Column("event_start", TZ, nullable=True),
        sa.Column("event_end", TZ, nullable=True),
        sa.Column(
            "provider",
            sa.String(length=32),
            nullable=False,
            server_default="polymarket",
        ),
        sa.Column("observed_at", TZ, nullable=True),
        sa.Column("created_at", TZ, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TZ, server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "market_external_ids",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "market_id",
            sa.String(length=64),
            sa.ForeignKey("markets.id"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("provider_event_id", sa.String(length=191), nullable=False),
        sa.Column("condition_id", sa.String(length=191), nullable=False),
        sa.Column("token_a_id", sa.String(length=191), nullable=False),
        sa.Column("token_b_id", sa.String(length=191), nullable=False),
        sa.Column("created_at", TZ, server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("market_id"),
        sa.UniqueConstraint("provider", "condition_id"),
    )
    op.create_index(
        "ix_market_external_ids_market_id", "market_external_ids", ["market_id"]
    )

    op.create_table(
        "market_rules",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "market_id",
            sa.String(length=64),
            sa.ForeignKey("markets.id"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("rules_text", sa.Text(), nullable=False),
        sa.Column("rules_hash", sa.String(length=128), nullable=False),
        sa.Column("resolution_source", sa.String(length=64), nullable=False),
        sa.Column("edge_case_semantics", sa.Text(), nullable=True),
        sa.Column("fetched_at", TZ, nullable=False),
        sa.UniqueConstraint("market_id", "version"),
        sa.UniqueConstraint("market_id", "rules_hash"),
    )
    op.create_index("ix_market_rules_market_id", "market_rules", ["market_id"])

    op.create_table(
        "market_match_links",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "market_id",
            sa.String(length=64),
            sa.ForeignKey("markets.id"),
            nullable=False,
        ),
        sa.Column("match_id", sa.String(length=64), nullable=False),
        sa.Column(
            "status", sa.String(length=16), nullable=False, server_default="active"
        ),
        sa.Column("evidence", JSONB(), nullable=False),
        sa.Column("linked_at", TZ, nullable=False),
        sa.UniqueConstraint("market_id"),
    )
    op.create_index(
        "ix_market_match_links_active_match",
        "market_match_links",
        ["match_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )
    op.create_index(
        "ix_market_match_links_market_id", "market_match_links", ["market_id"]
    )

    op.create_table(
        "market_observations",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "market_id",
            sa.String(length=64),
            sa.ForeignKey("markets.id"),
            nullable=False,
        ),
        sa.Column("match_id", sa.String(length=64), nullable=True),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("payload", JSONB(), nullable=False),
        sa.Column("observed_at", TZ, nullable=False),
        sa.Column("created_at", TZ, server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "ix_market_observations_market_id", "market_observations", ["market_id"]
    )
    op.create_index(
        "ix_market_observations_match_id", "market_observations", ["match_id"]
    )
    op.create_index(
        "ix_market_observations_observed_at", "market_observations", ["observed_at"]
    )

    op.create_table(
        "prediction_snapshots",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "match_id",
            sa.String(length=64),
            sa.ForeignKey("matches.id"),
            nullable=False,
        ),
        sa.Column("model_version", sa.String(length=64), nullable=False),
        sa.Column("calibration_version", sa.String(length=64), nullable=False),
        sa.Column("data_version", sa.String(length=64), nullable=False),
        sa.Column("input_state_version", sa.Integer(), nullable=False),
        sa.Column("availability", sa.String(length=16), nullable=False),
        sa.Column("abstain_reason", sa.String(length=64), nullable=True),
        sa.Column("payload", JSONB(), nullable=False),
        sa.Column("as_of", TZ, nullable=False),
        sa.UniqueConstraint("match_id", "model_version", "input_state_version"),
    )
    op.create_index(
        "ix_prediction_snapshots_match_id", "prediction_snapshots", ["match_id"]
    )

    op.create_table(
        "decision_observations",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "match_id",
            sa.String(length=64),
            sa.ForeignKey("matches.id"),
            nullable=False,
        ),
        sa.Column(
            "market_id",
            sa.String(length=64),
            sa.ForeignKey("markets.id"),
            nullable=False,
        ),
        sa.Column("observation_version", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=16), nullable=False),
        sa.Column(
            "is_stale", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column(
            "has_gap", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column("payload", JSONB(), nullable=False),
        sa.Column("as_of", TZ, nullable=False),
        sa.UniqueConstraint("match_id", "observation_version"),
    )
    op.create_index(
        "ix_decision_observations_match_id", "decision_observations", ["match_id"]
    )
    op.create_index(
        "ix_decision_observations_market_id", "decision_observations", ["market_id"]
    )
    op.create_index(
        "ix_decision_observations_as_of", "decision_observations", ["as_of"]
    )

    op.create_table(
        "paper_order_intents",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column(
            "match_id",
            sa.String(length=64),
            sa.ForeignKey("matches.id"),
            nullable=False,
        ),
        sa.Column(
            "market_id",
            sa.String(length=64),
            sa.ForeignKey("markets.id"),
            nullable=False,
        ),
        sa.Column("side", sa.String(length=8), nullable=False),
        sa.Column(
            "status", sa.String(length=16), nullable=False, server_default="pending"
        ),
        sa.Column("idempotency_key", sa.String(length=191), nullable=False),
        sa.Column("outcome_player_id", sa.String(length=64), nullable=False),
        sa.Column("stake", NUMERIC, nullable=False),
        sa.Column("delay_seconds", sa.Integer(), nullable=False),
        sa.Column("model_version", sa.String(length=64), nullable=False),
        sa.Column("policy_version", sa.String(length=64), nullable=False),
        sa.Column("rules_hash", sa.String(length=128), nullable=False),
        sa.Column("quote", JSONB(), nullable=False),
        sa.Column("created_at", TZ, nullable=False),
        sa.Column("expires_at", TZ, nullable=False),
        sa.Column("no_fill_reason", sa.String(length=64), nullable=True),
        sa.UniqueConstraint("idempotency_key"),
        sa.UniqueConstraint("match_id", "side"),
    )
    op.create_index(
        "ix_paper_order_intents_match_id", "paper_order_intents", ["match_id"]
    )
    op.create_index(
        "ix_paper_order_intents_market_id", "paper_order_intents", ["market_id"]
    )

    op.create_table(
        "paper_fills",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "intent_id",
            sa.String(length=64),
            sa.ForeignKey("paper_order_intents.id"),
            nullable=False,
        ),
        sa.Column("filled", sa.Boolean(), nullable=False),
        sa.Column("shares", NUMERIC, nullable=True),
        sa.Column("average_price", NUMERIC, nullable=True),
        sa.Column("fee", NUMERIC, nullable=True),
        sa.Column("reason", sa.String(length=64), nullable=True),
        sa.Column("executed_book_hash", sa.String(length=128), nullable=False),
        sa.Column("executed_at", TZ, nullable=False),
        sa.UniqueConstraint("intent_id"),
    )
    op.create_index("ix_paper_fills_intent_id", "paper_fills", ["intent_id"])

    op.create_table(
        "paper_positions",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column(
            "match_id",
            sa.String(length=64),
            sa.ForeignKey("matches.id"),
            nullable=False,
        ),
        sa.Column(
            "market_id",
            sa.String(length=64),
            sa.ForeignKey("markets.id"),
            nullable=False,
        ),
        sa.Column("outcome_player_id", sa.String(length=64), nullable=False),
        sa.Column("entry_cost", NUMERIC, nullable=False),
        sa.Column("shares", NUMERIC, nullable=False),
        sa.Column(
            "status", sa.String(length=16), nullable=False, server_default="open"
        ),
        sa.Column("opened_at", TZ, nullable=False),
        sa.Column("updated_at", TZ, nullable=False),
        sa.UniqueConstraint("match_id"),
    )
    op.create_index("ix_paper_positions_match_id", "paper_positions", ["match_id"])
    op.create_index("ix_paper_positions_market_id", "paper_positions", ["market_id"])

    op.create_table(
        "paper_track_results",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "match_id",
            sa.String(length=64),
            sa.ForeignKey("matches.id"),
            nullable=False,
        ),
        sa.Column(
            "position_id",
            sa.String(length=64),
            sa.ForeignKey("paper_positions.id"),
            nullable=False,
        ),
        sa.Column("track", sa.String(length=24), nullable=False),
        sa.Column("exit_kind", sa.String(length=24), nullable=False),
        sa.Column("shares", NUMERIC, nullable=False),
        sa.Column("exit_average_price", NUMERIC, nullable=True),
        sa.Column("payout_per_share", NUMERIC, nullable=False),
        sa.Column("gross_payout", NUMERIC, nullable=False),
        sa.Column("net_pnl", NUMERIC, nullable=False),
        sa.Column("settled_at", TZ, nullable=False),
        sa.UniqueConstraint("position_id", "track"),
    )
    op.create_index(
        "ix_paper_track_results_match_id", "paper_track_results", ["match_id"]
    )
    op.create_index(
        "ix_paper_track_results_position_id", "paper_track_results", ["position_id"]
    )

    op.create_table(
        "market_resolutions",
        sa.Column(
            "market_id",
            sa.String(length=64),
            sa.ForeignKey("markets.id"),
            primary_key=True,
        ),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("rules_version", sa.Integer(), nullable=False),
        sa.Column(
            "payouts", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")
        ),
        sa.Column("confirmed_at", TZ, nullable=True),
        sa.Column("updated_at", TZ, server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("market_resolutions")
    op.drop_index(
        "ix_paper_track_results_position_id", table_name="paper_track_results"
    )
    op.drop_index("ix_paper_track_results_match_id", table_name="paper_track_results")
    op.drop_table("paper_track_results")
    op.drop_index("ix_paper_positions_market_id", table_name="paper_positions")
    op.drop_index("ix_paper_positions_match_id", table_name="paper_positions")
    op.drop_table("paper_positions")
    op.drop_index("ix_paper_fills_intent_id", table_name="paper_fills")
    op.drop_table("paper_fills")
    op.drop_index("ix_paper_order_intents_market_id", table_name="paper_order_intents")
    op.drop_index("ix_paper_order_intents_match_id", table_name="paper_order_intents")
    op.drop_table("paper_order_intents")
    op.drop_index("ix_decision_observations_as_of", table_name="decision_observations")
    op.drop_index(
        "ix_decision_observations_market_id", table_name="decision_observations"
    )
    op.drop_index(
        "ix_decision_observations_match_id", table_name="decision_observations"
    )
    op.drop_table("decision_observations")
    op.drop_index("ix_prediction_snapshots_match_id", table_name="prediction_snapshots")
    op.drop_table("prediction_snapshots")
    op.drop_index(
        "ix_market_observations_observed_at", table_name="market_observations"
    )
    op.drop_index("ix_market_observations_match_id", table_name="market_observations")
    op.drop_index("ix_market_observations_market_id", table_name="market_observations")
    op.drop_table("market_observations")
    op.drop_index("ix_market_match_links_market_id", table_name="market_match_links")
    op.drop_index("ix_market_match_links_active_match", table_name="market_match_links")
    op.drop_table("market_match_links")
    op.drop_index("ix_market_rules_market_id", table_name="market_rules")
    op.drop_table("market_rules")
    op.drop_index("ix_market_external_ids_market_id", table_name="market_external_ids")
    op.drop_table("market_external_ids")
    op.drop_table("markets")
