from dataclasses import dataclass


@dataclass
class DispatchPlan:
    action_type: str
    # SIMULATED-by-design: unit names are synthetic until real unit registry is wired
    assigned_unit: str


# Water level thresholds (metres) → action type
_THRESHOLDS = [
    (1.2, "pump_emergency"),
    (0.8, "pump_high"),
    (0.4, "pump_standard"),
]

# SIMULATED-by-design: unit name templates per action type
_UNIT_TEMPLATES = {
    "pump_emergency": "ปั๊มฉุกเฉิน-{district}",
    "pump_high":      "ปั๊ม-{district}-01",
    "pump_standard":  "ปั๊ม-{district}-02",
    "inspect":        "เจ้าหน้าที่ตรวจสอบ-{district}",
}


def plan_dispatch(district: str, water_level_m: float) -> DispatchPlan:
    """Deterministic routing — no LLM (G2).

    Maps fused water level to action type and assigns a simulated unit
    based on the flood node's district.
    """
    action_type = "inspect"
    for threshold, atype in _THRESHOLDS:
        if water_level_m >= threshold:
            action_type = atype
            break

    # SIMULATED-by-design: unit registry not yet wired
    assigned_unit = _UNIT_TEMPLATES[action_type].format(district=district)
    return DispatchPlan(action_type=action_type, assigned_unit=assigned_unit)
