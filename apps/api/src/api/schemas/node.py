from datetime import datetime

from pydantic import BaseModel


class FloodNodeOut(BaseModel):
    id: int
    name: str
    lat: float
    lon: float
    district: str
    current_fused_level: float | None
    n_reports: int
    last_updated: datetime | None
