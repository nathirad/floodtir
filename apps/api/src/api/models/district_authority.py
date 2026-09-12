from sqlalchemy import Boolean, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from api.database import Base

class DistrictAuthorityCandidate(Base):
    __tablename__ = "district_authority_candidate"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    district: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[str] = mapped_column(String(100), nullable=False)
    authority_provision_hashes: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    is_simulated: Mapped[bool] = mapped_column(Boolean, server_default="FALSE")
