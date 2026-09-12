from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base


class WorkOrder(Base):
    __tablename__ = "work_order"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        server_default=text("nextval('work_order_id_seq')"),
    )
    flood_node_id: Mapped[int] = mapped_column(ForeignKey("flood_node.id"), nullable=False, index=True)
    # state machine: pending → dispatched → done | mismatch
    status: Mapped[str] = mapped_column(String(20), server_default=text("'pending'"), index=True)
    action_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # SIMULATED-by-design: synthetic unit names until real unit registry is wired
    assigned_unit: Mapped[str] = mapped_column(String(200), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    # coordinator who approved the plan; future: FK → user.id
    approved_by: Mapped[str | None] = mapped_column(String(100))
    # field ops who confirmed execution; future: FK → user.id
    confirmed_by: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()")
    )
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # G5: provenance label — all current rows are SIMULATED-by-design
    is_simulated: Mapped[bool] = mapped_column(Boolean, server_default=text("TRUE"))
    # LINE OA dispatch tracking
    line_dispatched: Mapped[bool] = mapped_column(Boolean, server_default=text("FALSE"))
    line_dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
