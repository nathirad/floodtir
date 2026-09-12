from datetime import datetime

from pydantic import BaseModel


class LineDispatchOptions(BaseModel):
    include_node_name:     bool = True
    include_water_level:   bool = True
    include_action_type:   bool = True
    include_assigned_unit: bool = True
    extra_notes: str | None = None


class WorkOrderCreate(BaseModel):
    flood_node_id: int
    # coordinator who approved the plan — MOCK: replace with auth session
    approved_by: str
    # human overrides — if omitted, orchestrator decides (G2)
    action_type: str | None = None
    assigned_unit: str | None = None
    notes: str | None = None
    notify_line: bool = False
    line_options: LineDispatchOptions = LineDispatchOptions()


class WorkOrderConfirm(BaseModel):
    # field ops handle confirming execution; future: FK → user.id
    confirmed_by: str


class WorkOrderPatch(BaseModel):
    action_type: str | None = None
    assigned_unit: str | None = None
    notes: str | None = None


class LineNotifyRequest(BaseModel):
    line_options: LineDispatchOptions = LineDispatchOptions()


class DispatchPlanOut(BaseModel):
    action_type: str
    assigned_unit: str
    water_level_m: float | None
    district: str
    flood_node_name: str
    n_reports: int


class WorkOrderOut(BaseModel):
    id: int
    flood_node_id: int
    flood_node_name: str
    flood_node_district: str
    status: str
    action_type: str
    assigned_unit: str
    notes: str | None
    approved_by: str | None
    confirmed_by: str | None
    water_level_m: float | None
    created_at: datetime
    updated_at: datetime
    dispatched_at: datetime | None
    line_dispatched: bool
    line_dispatched_at: datetime | None
    # True when WO was previously LINE-dispatched and has just been edited
    resend_required: bool = False
