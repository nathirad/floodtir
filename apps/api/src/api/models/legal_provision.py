from sqlalchemy import Boolean, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from api.database import Base

class LegalProvision(Base):
    __tablename__ = "legal_provision"

    provision_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    source_id: Mapped[str] = mapped_column(String(200), nullable=False)
    provision_reference: Mapped[str] = mapped_column(String(100), nullable=False)
    authority_type: Mapped[str] = mapped_column(String(100), nullable=False)
    territorial_scope: Mapped[str] = mapped_column(String(100), nullable=False)
    action_codes: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    requires_action_specific_order: Mapped[bool] = mapped_column(Boolean, nullable=False)
    may_auto_dispatch: Mapped[bool] = mapped_column(Boolean, nullable=False)
    is_simulated: Mapped[bool] = mapped_column(Boolean, server_default="FALSE")
