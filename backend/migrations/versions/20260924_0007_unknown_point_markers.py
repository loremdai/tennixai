"""Preserve undocumented provider key-point markers as unknown.

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-24
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_MARKER_COLUMNS = ("is_break_point", "is_set_point", "is_match_point")


def upgrade() -> None:
    for column in _MARKER_COLUMNS:
        op.alter_column(
            "point_events",
            column,
            existing_type=sa.Boolean(),
            nullable=True,
        )
    for column in _MARKER_COLUMNS:
        op.execute(
            sa.text(
                f"UPDATE point_events SET {column} = NULL "
                "WHERE provider = 'api_tennis'"
            )
        )


def downgrade() -> None:
    unknown_rows = op.get_bind().execute(
        sa.text(
            "SELECT count(*) FROM point_events "
            "WHERE is_break_point IS NULL "
            "OR is_set_point IS NULL "
            "OR is_match_point IS NULL"
        )
    ).scalar_one()
    if unknown_rows:
        raise RuntimeError(
            "Cannot downgrade 0007 while unknown point markers exist; "
            "mapping them to false would lose information"
        )

    for column in _MARKER_COLUMNS:
        op.alter_column(
            "point_events",
            column,
            existing_type=sa.Boolean(),
            nullable=False,
        )
