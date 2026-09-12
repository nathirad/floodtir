"""p5_ledger_data_class — G9: data_class label on every ledger entry

Revision ID: f7a8b9c0d1e2
Revises: e6f7a8b9c0d1
Create Date: 2026-06-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f7a8b9c0d1e2"
down_revision: str | Sequence[str] | None = "e6f7a8b9c0d1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # G9: accountability board must show labeled facts, not inferred labels.
    # DEFAULT 'SIMULATED-by-design' covers all rows written in P1–P4.
    op.add_column(
        "ledger_entry",
        sa.Column(
            "data_class",
            sa.String(30),
            nullable=False,
            server_default=sa.text("'SIMULATED-by-design'"),
        ),
    )


def downgrade() -> None:
    op.drop_column("ledger_entry", "data_class")
