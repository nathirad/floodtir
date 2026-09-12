from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel


class RoughLevel(StrEnum):
    ankle = "ข้อเท้า"
    knee = "เข่า"
    waist = "เอว"
    chest = "อก"
    neck = "คอ"


class ReportOut(BaseModel):
    report_id: int
    ts: datetime
    water_level_m: float | None
    confidence: float
    flood_node_id: int | None
    status: str  # accepted | duplicate | rejected
    label: str  # REAL | SIMULATED-by-design
