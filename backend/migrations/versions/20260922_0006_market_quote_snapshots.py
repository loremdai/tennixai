"""Add the durable latest-quote projection.

Creates only `market_quote_snapshots` (one row per market) for the P4.3
coverage lane: canonical two-outcome levels plus display statistics with an
explicit state, source and timestamp. It stores no provider identity, raw
payload, model or paper state. Downgrade drops only this table; every
P2/P3 table is untouched.

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-22

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TZ = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "market_quote_snapshots",
        sa.Column("market_id", sa.String(length=64), primary_key=True),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("quote_state", sa.String(length=16), nullable=False),
        sa.Column("book_hash", sa.String(length=128), nullable=True),
        sa.Column("as_of", TZ, nullable=False),
        sa.Column("expires_at", TZ, nullable=False),
        sa.Column("outcome_a_bid", sa.String(length=32), nullable=True),
        sa.Column("outcome_a_ask", sa.String(length=32), nullable=True),
        sa.Column("outcome_b_bid", sa.String(length=32), nullable=True),
        sa.Column("outcome_b_ask", sa.String(length=32), nullable=True),
        sa.Column("spread", sa.String(length=32), nullable=True),
        sa.Column("depth_usd", sa.String(length=32), nullable=True),
        sa.Column("payload", JSONB(), nullable=True),
        sa.Column("updated_at", TZ, nullable=False),
        sa.ForeignKeyConstraint(["market_id"], ["markets.id"]),
    )


def downgrade() -> None:
    op.drop_table("market_quote_snapshots")