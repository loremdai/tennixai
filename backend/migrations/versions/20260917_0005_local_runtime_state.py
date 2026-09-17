"""Add the local runtime state table.

Creates only `runtime_state` (key/payload/updated_at) for the P4.1 local
runtime init marker and health summary. The table stores canonical payloads
only — never provider identifiers or raw provider JSON. Downgrade drops only
`runtime_state`; every P2/P3 table is untouched.

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-17

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TZ = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "runtime_state",
        sa.Column("key", sa.String(length=64), primary_key=True),
        sa.Column("payload", JSONB(), nullable=False),
        sa.Column("updated_at", TZ, nullable=False),
    )


def downgrade() -> None:
    op.drop_table("runtime_state")
