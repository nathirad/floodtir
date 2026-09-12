from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class VerificationCreate(BaseModel):
    outcome: Literal["VERIFIED", "MISMATCH"]
    verified_by: str
    # PENDING-WIRE: actual photo path/URL when citizen app + VLM wired
    photo_ref: str | None = None


class VerificationOut(BaseModel):
    id: int
    work_order_id: int
    outcome: str
    verified_by: str | None
    photo_ref: str | None
    created_at: datetime
    new_work_order_id: int | None = None

    model_config = {"from_attributes": True}


class LedgerEntryOut(BaseModel):
    id: int
    event_type: str
    payload: str
    prev_hash: str
    hash: str
    # G9: label written at append-time, never derived
    data_class: str
    created_at: datetime

    model_config = {"from_attributes": True}
