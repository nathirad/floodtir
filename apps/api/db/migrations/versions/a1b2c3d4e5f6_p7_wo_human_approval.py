"""p7_wo_human_approval — add approved_by, line_dispatched, line_dispatched_at to work_order

Revision ID: a1b2c3d4e5f6
Revises: f7a8b9c0d1e2
Create Date: 2026-06-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: str | Sequence[str] | None = "f7a8b9c0d1e2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # coordinator who approved the plan before WO was created
    op.add_column(
        "work_order",
        sa.Column("approved_by", sa.String(100), nullable=True),
    )
    # track whether LINE OA notification was sent for this WO
    op.add_column(
        "work_order",
        sa.Column(
            "line_dispatched",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("FALSE"),
        ),
    )
    op.add_column(
        "work_order",
        sa.Column("line_dispatched_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("work_order", "line_dispatched_at")
    op.drop_column("work_order", "line_dispatched")
    op.drop_column("work_order", "approved_by")
