"""LINE dispatch — SIMULATED-by-design.

This module is a stub. No real LINE API call is made.
TODO: swap body of `send_dispatch` when LINE Notify / Messaging API is wired.
      Interface is intentionally identical so only this file changes.
"""

from datetime import UTC, datetime

from api.schemas.work_order import LineDispatchOptions


def send_dispatch(
    work_order_id: int,
    action_type: str,
    assigned_unit: str,
    flood_node_name: str,
    water_level_m: float | None,
    options: LineDispatchOptions | None = None,
) -> str:
    """Return the simulated LINE message string (caller stores in work_order.notes).

    Only includes fields selected in options (default: all fields).
    All output from this function is SIMULATED-by-design.
    """
    if options is None:
        options = LineDispatchOptions()

    # SIMULATED-by-design: no real LINE API call
    ts = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    lines: list[str] = [f"[SIMULATED LINE DISPATCH] {ts}", f"WO#{work_order_id}"]

    if options.include_node_name:
        lines.append(f"จุด: {flood_node_name}")
    if options.include_water_level:
        level_str = f"{water_level_m:.2f}m" if water_level_m is not None else "N/A"
        lines.append(f"ระดับน้ำ: {level_str}")
    if options.include_action_type:
        lines.append(f"คำสั่ง: {action_type}")
    if options.include_assigned_unit:
        lines.append(f"หน่วย: {assigned_unit}")
    if options.extra_notes:
        lines.append(f"หมายเหตุ: {options.extra_notes}")

    lines.append("[SIMULATED-by-design: ยังไม่ได้ต่อ LINE API จริง]")
    return "\n".join(lines)
