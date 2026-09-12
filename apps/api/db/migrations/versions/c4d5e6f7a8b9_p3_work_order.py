"""p3_work_order — work order table for dispatch spine

Revision ID: c4d5e6f7a8b9
Revises: b3c4d5e6f7a8
Create Date: 2026-06-24

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c4d5e6f7a8b9"
down_revision: str | Sequence[str] | None = "b3c4d5e6f7a8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "work_order",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("flood_node_id", sa.Integer(), nullable=False),
        # state machine: pending → confirmed → dispatched → done
        sa.Column(
            "status",
            sa.String(length=20),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column("action_type", sa.String(length=50), nullable=False),
        # SIMULATED-by-design: unit names are synthetic until real unit registry is wired
        sa.Column("assigned_unit", sa.String(length=200), nullable=False),
        # stores [SIMULATED LINE DISPATCH] log on dispatch; free text for operator notes
        sa.Column("notes", sa.Text(), nullable=True),
        # operator handle; nullable until confirmed; future: FK → user.id
        sa.Column("confirmed_by", sa.String(length=100), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["flood_node_id"], ["flood_node.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_work_order_status", "work_order", ["status"])
    op.create_index("ix_work_order_flood_node_id", "work_order", ["flood_node_id"])

    op.execute("CREATE SEQUENCE IF NOT EXISTS work_order_id_seq")
    op.execute(
        "ALTER TABLE work_order ALTER COLUMN id SET DEFAULT nextval('work_order_id_seq')"
    )
    op.execute("ALTER SEQUENCE work_order_id_seq OWNED BY work_order.id")


def downgrade() -> None:
    op.drop_index("ix_work_order_flood_node_id", table_name="work_order")
    op.drop_index("ix_work_order_status", table_name="work_order")
    op.drop_table("work_order")
