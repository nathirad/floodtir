from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, text
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base


class OsintReport(Base):
    """Hypertable (TimescaleDB) — partitioned on ts. Migration handles conversion."""

    __tablename__ = "osint_report"

    # Composite PK required by TimescaleDB — partition column must be in PK.
    # server_default is required for asyncpg RETURNING to populate id on INSERT.
    id: Mapped[int] = mapped_column(
        primary_key=True,
        server_default=text("nextval('osint_report_id_seq')"),
    )
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True, index=True)
    geom: Mapped[object] = mapped_column(Geometry("POINT", srid=4326), nullable=False)
    # AI-estimated water level in meters (from VLM analysis of photo)
    water_level_m: Mapped[float | None] = mapped_column(Float)
    confidence: Mapped[float] = mapped_column(Float, server_default=text("0.0"))
    photo_ref: Mapped[str | None] = mapped_column(String(500))
    reporter_id: Mapped[int] = mapped_column(ForeignKey("reporter.id"))
    flood_node_id: Mapped[int | None] = mapped_column(ForeignKey("flood_node.id"))
    is_simulated: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    source_label: Mapped[str] = mapped_column(String(50), server_default=text("'citizen'"))
