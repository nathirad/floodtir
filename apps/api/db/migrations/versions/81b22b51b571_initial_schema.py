"""initial_schema

Revision ID: 81b22b51b571
Revises:
Create Date: 2026-06-23 16:13:57.793367

"""
from collections.abc import Sequence

import geoalchemy2
import sqlalchemy as sa
from alembic import op

revision: str = '81b22b51b571'
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE")

    op.create_table(
        'flood_node',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('geom', geoalchemy2.types.Geometry(
            geometry_type='POINT', srid=4326, from_text='ST_GeomFromEWKT', name='geometry',
        ), nullable=False),
        sa.Column('district', sa.String(length=100), nullable=False),
        sa.Column('historical_max_level', sa.Float(), nullable=True),
        sa.Column('current_fused_level', sa.Float(), nullable=True),
        sa.Column('last_updated', sa.DateTime(timezone=True), nullable=True),
        sa.Column('n_reports', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'reporter',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('handle', sa.String(length=100), nullable=True),
        sa.Column('trust_score', sa.Float(), server_default=sa.text('0.5'), nullable=False),
        sa.Column('is_simulated', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'osint_report',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('ts', sa.DateTime(timezone=True), nullable=False),
        # ts in PK required by TimescaleDB hypertable partitioning
        sa.Column('geom', geoalchemy2.types.Geometry(
            geometry_type='POINT', srid=4326, from_text='ST_GeomFromEWKT', name='geometry',
        ), nullable=False),
        sa.Column('water_level_m', sa.Float(), nullable=True),
        sa.Column('confidence', sa.Float(), server_default=sa.text('0.0'), nullable=False),
        sa.Column('photo_ref', sa.String(length=500), nullable=True),
        sa.Column('reporter_id', sa.Integer(), nullable=False),
        sa.Column('flood_node_id', sa.Integer(), nullable=True),
        sa.Column('is_simulated', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column(
            'source_label', sa.String(length=50),
            server_default=sa.text("'citizen'"), nullable=False,
        ),
        sa.ForeignKeyConstraint(['flood_node_id'], ['flood_node.id']),
        sa.ForeignKeyConstraint(['reporter_id'], ['reporter.id']),
        sa.PrimaryKeyConstraint('id', 'ts'),
    )
    op.create_index('ix_osint_report_ts', 'osint_report', ['ts'], unique=False)

    # Convert osint_report to TimescaleDB hypertable partitioned on ts
    op.execute("SELECT create_hypertable('osint_report', 'ts')")


def downgrade() -> None:
    op.drop_index('ix_osint_report_ts', table_name='osint_report')
    op.drop_table('osint_report')
    op.drop_table('reporter')
    op.drop_table('flood_node')
