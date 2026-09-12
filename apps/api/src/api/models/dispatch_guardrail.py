from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from api.database import Base

class DispatchGuardrail(Base):
    __tablename__ = "dispatch_guardrail"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    action_code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    is_prohibited_without_auth: Mapped[bool] = mapped_column(Boolean, nullable=False)
    is_allowed_before_approval: Mapped[bool] = mapped_column(Boolean, nullable=False)
    is_simulated: Mapped[bool] = mapped_column(Boolean, server_default="FALSE")
