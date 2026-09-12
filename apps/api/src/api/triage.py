"""Triage agent stub — maps rough water-level label to metres.

PENDING-WIRE: replace function body with ThaiLLM 30B VLM call when Ollama is up.
Interface (signature + TriageResult shape) must stay stable for that swap.
"""

import random
from dataclasses import dataclass

from api.schemas.ingest import RoughLevel

_LABEL_TO_METRES: dict[RoughLevel, float] = {
    RoughLevel.ankle: 0.15,
    RoughLevel.knee: 0.45,
    RoughLevel.waist: 0.85,
    RoughLevel.chest: 1.20,
    RoughLevel.neck: 1.50,
}

_BASE_CONFIDENCE = 0.40
_PHOTO_BONUS = 0.05


@dataclass
class TriageResult:
    water_level_m: float | None
    confidence: float


def triage(rough_level: RoughLevel | None, *, has_photo: bool) -> TriageResult:
    if rough_level is None and not has_photo:
        return TriageResult(water_level_m=None, confidence=0.0)
    base = _LABEL_TO_METRES.get(rough_level, 0.30) if rough_level is not None else 0.30
    jitter = random.uniform(-0.05, 0.05)
    confidence = _BASE_CONFIDENCE + (_PHOTO_BONUS if has_photo else 0.0)
    return TriageResult(water_level_m=round(base + jitter, 2), confidence=confidence)
