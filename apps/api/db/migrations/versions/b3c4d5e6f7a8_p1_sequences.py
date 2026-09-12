"""p1_sequences — add autoincrement sequences for all id columns

Alembic's op.create_table generates INTEGER NOT NULL (not SERIAL).
asyncpg uses INSERT ... RETURNING id which requires a server-side DEFAULT.

Revision ID: b3c4d5e6f7a8
Revises: 81b22b51b571
Create Date: 2026-06-23

"""

from collections.abc import Sequence

from alembic import op

revision: str = "b3c4d5e6f7a8"
down_revision: str | Sequence[str] | None = "81b22b51b571"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for table in ("reporter", "flood_node"):
        op.execute(f"CREATE SEQUENCE IF NOT EXISTS {table}_id_seq")
        op.execute(
            f"ALTER TABLE {table} ALTER COLUMN id SET DEFAULT nextval('{table}_id_seq')"
        )
        op.execute(f"ALTER SEQUENCE {table}_id_seq OWNED BY {table}.id")
        op.execute(
            f"SELECT setval('{table}_id_seq',"
            f" COALESCE((SELECT MAX(id) FROM {table}), 0) + 1, false)"
        )

    op.execute("CREATE SEQUENCE IF NOT EXISTS osint_report_id_seq")
    op.execute(
        "ALTER TABLE osint_report ALTER COLUMN id"
        " SET DEFAULT nextval('osint_report_id_seq')"
    )
    op.execute("ALTER SEQUENCE osint_report_id_seq OWNED BY osint_report.id")
    op.execute(
        "SELECT setval('osint_report_id_seq',"
        " COALESCE((SELECT MAX(id) FROM osint_report), 0) + 1, false)"
    )


def downgrade() -> None:
    for table in ("reporter", "flood_node", "osint_report"):
        op.execute(f"ALTER TABLE {table} ALTER COLUMN id DROP DEFAULT")
        op.execute(f"DROP SEQUENCE IF EXISTS {table}_id_seq")
