from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import DateTime, Float, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base


class FloodNode(Base):
    __tablename__ = "flood_node"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    geom: Mapped[object] = mapped_column(Geometry("POINT", srid=4326), nullable=False)
    district: Mapped[str] = mapped_column(String(100))
    historical_max_level: Mapped[float | None] = mapped_column(Float)
    current_fused_level: Mapped[float | None] = mapped_column(Float)
    last_updated: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    n_reports: Mapped[int] = mapped_column(Integer, server_default=text("0"))
