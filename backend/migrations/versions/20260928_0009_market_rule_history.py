"""Preserve chronological market rule changes, including A→B→A.

Revision ID: 0009
Revises: 0008
Create Date: 2026-09-28
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint(
        "market_rules_market_id_rules_hash_key", "market_rules", type_="unique"
    )
    op.alter_column(
        "market_rules",
        "resolution_source",
        existing_type=sa.String(64),
        type_=sa.Text(),
    )


def downgrade() -> None:
    connection = op.get_bind()
    repeated_hashes = connection.execute(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM market_rules "
            "GROUP BY market_id, rules_hash HAVING count(*) > 1)"
        )
    ).scalar_one()
    long_sources = connection.execute(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM market_rules WHERE length(resolution_source) > 64)"
        )
    ).scalar_one()
    if repeated_hashes or long_sources:
        raise RuntimeError(
            "Cannot downgrade 0009 while repeated rule hashes or long resolution sources exist"
        )
    op.alter_column(
        "market_rules",
        "resolution_source",
        existing_type=sa.Text(),
        type_=sa.String(64),
    )
    op.create_unique_constraint(
        "market_rules_market_id_rules_hash_key",
        "market_rules",
        ["market_id", "rules_hash"],
    )
