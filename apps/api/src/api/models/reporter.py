from sqlalchemy import Boolean, Float, String, text
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base


class Reporter(Base):
    __tablename__ = "reporter"

    id: Mapped[int] = mapped_column(primary_key=True)
    handle: Mapped[str | None] = mapped_column(String(100))
    trust_score: Mapped[float] = mapped_column(Float, server_default=text("0.5"))
    is_simulated: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
