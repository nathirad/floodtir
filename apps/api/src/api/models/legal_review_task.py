from datetime import datetime
from sqlalchemy import Boolean, DateTime, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column
from api.database import Base

class LegalReviewTask(Base):
    __tablename__ = "legal_review_task"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    review_type: Mapped[str] = mapped_column(String(100), nullable=False)
    source_id: Mapped[str] = mapped_column(String(100), nullable=False)
    provision_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    review_question: Mapped[str] = mapped_column(Text, nullable=False)
    required_reviewer_role: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(50), server_default=text("'open'"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()")
    )
    is_simulated: Mapped[bool] = mapped_column(Boolean, server_default="FALSE")
