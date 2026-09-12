from geoalchemy2 import Geometry
from sqlalchemy import Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from api.database import Base

class Sump(Base):
    __tablename__ = "sump"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str | None] = mapped_column(String(100))
    sump_type: Mapped[str | None] = mapped_column(String(100))
    district: Mapped[str | None] = mapped_column(String(100))
    geom: Mapped[object] = mapped_column(Geometry("POINT", srid=4326), nullable=False)
    depth: Mapped[float | None] = mapped_column(Float)
    width: Mapped[float | None] = mapped_column(Float)
    length: Mapped[float | None] = mapped_column(Float)
