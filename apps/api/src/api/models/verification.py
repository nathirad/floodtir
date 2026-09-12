from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base


class Verification(Base):
    __tablename__ = "verification"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        server_default=text("nextval('verification_id_seq')"),
    )
    work_order_id: Mapped[int] = mapped_column(ForeignKey("work_order.id"), nullable=False, index=True)
    # VERIFIED | MISMATCH
    outcome: Mapped[str] = mapped_column(String(10), nullable=False)
    # PENDING-WIRE: store actual path/URL when citizen app + VLM wired
    photo_ref: Mapped[str | None] = mapped_column(String(500))
    notes: Mapped[str | None] = mapped_column(Text)
    # citizen handle; future: FK → user.id
    verified_by: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()")
    )
    # G5: provenance label — all current rows are SIMULATED-by-design
    is_simulated: Mapped[bool] = mapped_column(Boolean, server_default=text("TRUE"))
