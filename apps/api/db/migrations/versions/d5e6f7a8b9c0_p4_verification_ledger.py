"""p4_verification_ledger — verification outcome + append-only ledger hash-chain

Revision ID: d5e6f7a8b9c0
Revises: c4d5e6f7a8b9
Create Date: 2026-06-24

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d5e6f7a8b9c0"
down_revision: str | Sequence[str] | None = "c4d5e6f7a8b9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- verification ---
    op.create_table(
        "verification",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("work_order_id", sa.Integer(), nullable=False),
        # VERIFIED | MISMATCH
        sa.Column("outcome", sa.String(length=10), nullable=False),
        # PENDING-WIRE: store actual path/URL when citizen app + VLM wired
        sa.Column("photo_ref", sa.String(length=500), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        # citizen handle; future: FK → user.id
        sa.Column("verified_by", sa.String(length=100), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["work_order_id"], ["work_order.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_verification_work_order_id", "verification", ["work_order_id"])
    op.execute("CREATE SEQUENCE IF NOT EXISTS verification_id_seq")
    op.execute(
        "ALTER TABLE verification ALTER COLUMN id SET DEFAULT nextval('verification_id_seq')"
    )
    op.execute("ALTER SEQUENCE verification_id_seq OWNED BY verification.id")

    # --- ledger_entry (append-only hash-chain) ---
    op.create_table(
        "ledger_entry",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False),   # JSON string
        sa.Column("prev_hash", sa.String(length=64), nullable=False),
        sa.Column("hash", sa.String(length=64), nullable=False),
        sa.Column("signature", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.execute("CREATE SEQUENCE IF NOT EXISTS ledger_entry_id_seq")
    op.execute(
        "ALTER TABLE ledger_entry ALTER COLUMN id SET DEFAULT nextval('ledger_entry_id_seq')"
    )
    op.execute("ALTER SEQUENCE ledger_entry_id_seq OWNED BY ledger_entry.id")


def downgrade() -> None:
    op.drop_index("ix_verification_work_order_id", table_name="verification")
    op.drop_table("verification")
    op.drop_table("ledger_entry")
