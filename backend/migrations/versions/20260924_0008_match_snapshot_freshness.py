"""Persist canonical match freshness without replacing provider provenance.

Revision ID: 0008
Revises: 0007
Create Date: 2026-09-24
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "match_state_snapshots",
        sa.Column("freshness", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    populated_rows = op.get_bind().execute(
        sa.text(
            "SELECT count(*) FROM match_state_snapshots "
            "WHERE freshness IS NOT NULL"
        )
    ).scalar_one()
    if populated_rows:
        raise RuntimeError(
            "Cannot downgrade 0008 while persisted freshness data exists; "
            "export or explicitly remove it before retrying"
        )
    op.drop_column("match_state_snapshots", "freshness")
