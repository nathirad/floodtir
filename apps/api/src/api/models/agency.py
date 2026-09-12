from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column
from api.database import Base

class Agency(Base):
    __tablename__ = "agency"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    name_th: Mapped[str] = mapped_column(String(200), nullable=False)
    name_en: Mapped[str | None] = mapped_column(String(200), nullable=True)
    agency_type: Mapped[str] = mapped_column(String(100), nullable=False)
    parent_agency_id: Mapped[str | None] = mapped_column(String(100), ForeignKey("agency.id"), nullable=True)
    is_simulated: Mapped[bool] = mapped_column(Boolean, server_default="FALSE")
