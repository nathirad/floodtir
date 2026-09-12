from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import Row, text
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.database import get_db
from api.models.work_order import WorkOrder
from api.schemas.work_order import (
    DispatchPlanOut,
    LineDispatchOptions,
    LineNotifyRequest,
    WorkOrderConfirm,
    WorkOrderCreate,
    WorkOrderOut,
    WorkOrderPatch,
)
from api.services import ledger as ledger_svc
from api.services.line_dispatch import send_dispatch
from api.services.orchestrator import plan_dispatch

router = APIRouter(prefix="/work-orders", tags=["work-orders"])

DBDep = Annotated[AsyncSession, Depends(get_db)]

# Unified JOIN SQL — column indices documented below
# 0:wo.id  1:flood_node_id  2:status  3:action_type  4:assigned_unit
# 5:notes  6:confirmed_by   7:created_at  8:updated_at  9:dispatched_at
# 10:fn.name  11:fn.district  12:fn.current_fused_level
# 13:approved_by  14:line_dispatched  15:line_dispatched_at
_WO_JOIN = """
    SELECT wo.id, wo.flood_node_id, wo.status, wo.action_type, wo.assigned_unit,
           wo.notes, wo.confirmed_by, wo.created_at, wo.updated_at, wo.dispatched_at,
           fn.name, fn.district, fn.current_fused_level,
           wo.approved_by, wo.line_dispatched, wo.line_dispatched_at
    FROM work_order wo
    JOIN flood_node fn ON fn.id = wo.flood_node_id
"""


def _row_to_out(row: Row[Any], resend_required: bool = False) -> WorkOrderOut:
    return WorkOrderOut(
        id=int(row[0]),
        flood_node_id=int(row[1]),
        flood_node_name=str(row[10]),
        flood_node_district=str(row[11]),
        status=str(row[2]),
        action_type=str(row[3]),
        assigned_unit=str(row[4]),
        notes=str(row[5]) if row[5] is not None else None,
        approved_by=str(row[13]) if row[13] is not None else None,
        confirmed_by=str(row[6]) if row[6] is not None else None,
        water_level_m=float(row[12]) if row[12] is not None else None,
        created_at=row[7],
        updated_at=row[8],
        dispatched_at=row[9],
        line_dispatched=bool(row[14]),
        line_dispatched_at=row[15],
        resend_required=resend_required,
    )


async def _fetch_wo_out(
    db: AsyncSession, wo_id: int, resend_required: bool = False
) -> WorkOrderOut:
    result = await db.execute(
        text(_WO_JOIN + " WHERE wo.id = :id"), {"id": wo_id}
    )
    row = result.first()
    if row is None:
        raise HTTPException(status_code=500, detail=f"work_order {wo_id} not found after write")
    return _row_to_out(row, resend_required)


async def _get_node_row(db: AsyncSession, node_id: int) -> Row[Any]:
    result = await db.execute(
        text("SELECT id, name, district, current_fused_level FROM flood_node WHERE id = :nid"),
        {"nid": node_id},
    )
    row = result.first()
    if row is None:
        raise HTTPException(status_code=404, detail=f"flood_node {node_id} not found")
    return row


def _line_included_fields(opts: LineDispatchOptions) -> list[str]:
    return [
        k for k, v in {
            "node_name":    opts.include_node_name,
            "water_level":  opts.include_water_level,
            "action_type":  opts.include_action_type,
            "assigned_unit": opts.include_assigned_unit,
        }.items() if v
    ]


# ── Read endpoints ────────────────────────────────────────────────────────────

@router.get("", response_model=list[WorkOrderOut])
async def list_work_orders(
    db: DBDep, status: str | None = None
) -> list[WorkOrderOut]:
    q = _WO_JOIN
    params: dict[str, Any] = {}
    if status:
        q += " WHERE wo.status = :status"
        params["status"] = status
    q += " ORDER BY wo.created_at DESC"
    result = await db.execute(text(q), params)
    return [_row_to_out(row) for row in result.all()]


@router.get("/plan-preview", response_model=DispatchPlanOut)
async def get_plan_preview(
    db: DBDep, flood_node_id: int = Query(...)
) -> DispatchPlanOut:
    """Return orchestrator's proposed plan without writing to DB.

    G7 check runs here so the modal fails fast before opening.
    plan_dispatch() is a pure function — deterministic on current_fused_level.
    """
    node = await _get_node_row(db, flood_node_id)
    water_level_m: float | None = float(node[3]) if node[3] is not None else None

    n_res = await db.execute(
        text("SELECT n_reports FROM flood_node WHERE id = :nid"), {"nid": flood_node_id}
    )
    n_row = n_res.first()
    n_reports = int(n_row[0]) if n_row and n_row[0] is not None else 0
    if n_reports < settings.corroboration_min_n:
        raise HTTPException(
            status_code=422,
            detail=(
                f"G7: flood_node {flood_node_id} has {n_reports} report(s); "
                f"≥{settings.corroboration_min_n} required before dispatch"
            ),
        )

    plan = plan_dispatch(str(node[2]), water_level_m or 0.0)
    return DispatchPlanOut(
        action_type=plan.action_type,
        assigned_unit=plan.assigned_unit,
        water_level_m=water_level_m,
        district=str(node[2]),
        flood_node_name=str(node[1]),
        n_reports=n_reports,
    )


@router.get("/line-preview")
async def get_line_preview(
    flood_node_name: str = Query(...),
    action_type: str = Query(...),
    assigned_unit: str = Query(...),
    water_level_m: float | None = Query(default=None),
    include_node_name: bool = Query(default=True),
    include_water_level: bool = Query(default=True),
    include_action_type: bool = Query(default=True),
    include_assigned_unit: bool = Query(default=True),
    extra_notes: str | None = Query(default=None),
    work_order_id: int = Query(default=0),
) -> dict[str, str]:
    """Compute the LINE message string server-side for frontend preview."""
    opts = LineDispatchOptions(
        include_node_name=include_node_name,
        include_water_level=include_water_level,
        include_action_type=include_action_type,
        include_assigned_unit=include_assigned_unit,
        extra_notes=extra_notes,
    )
    message = send_dispatch(
        work_order_id=work_order_id,
        action_type=action_type,
        assigned_unit=assigned_unit,
        flood_node_name=flood_node_name,
        water_level_m=water_level_m,
        options=opts,
    )
    return {"message": message}


# ── Write endpoints ───────────────────────────────────────────────────────────

@router.post("", response_model=WorkOrderOut, status_code=201)
async def create_work_order(body: WorkOrderCreate, db: DBDep) -> WorkOrderOut:
    node = await _get_node_row(db, body.flood_node_id)
    water_level_m: float = float(node[3]) if node[3] is not None else 0.0
    district = str(node[2])
    flood_node_name = str(node[1])

    # G7: corroboration check — require ≥ N reports before issuing a work order
    n_res = await db.execute(
        text("SELECT n_reports FROM flood_node WHERE id = :nid"),
        {"nid": body.flood_node_id},
    )
    n_row = n_res.first()
    n_reports = int(n_row[0]) if n_row and n_row[0] is not None else 0
    if n_reports < settings.corroboration_min_n:
        raise HTTPException(
            status_code=422,
            detail=(
                f"G7: flood_node {body.flood_node_id} has {n_reports} corroborated "
                f"report(s); ≥{settings.corroboration_min_n} required before dispatch"
            ),
        )

    # use human-provided overrides if both given, else delegate to orchestrator (G2)
    if body.action_type is not None and body.assigned_unit is not None:
        action_type = body.action_type
        assigned_unit = body.assigned_unit
    else:
        plan = plan_dispatch(district, water_level_m)
        action_type = body.action_type or plan.action_type
        assigned_unit = body.assigned_unit or plan.assigned_unit

    now = datetime.now(UTC)

    wo = WorkOrder(
        flood_node_id=body.flood_node_id,
        status="pending",
        action_type=action_type,
        assigned_unit=assigned_unit,
        notes=body.notes,
        approved_by=body.approved_by,
    )
    db.add(wo)
    await db.flush()  # assigns wo.id without committing

    await ledger_svc.append_event(
        db,
        "WO_CREATED",
        {
            "work_order_id": wo.id,
            "flood_node_id": body.flood_node_id,
            "action_type": action_type,
            "assigned_unit": assigned_unit,
            "district": district,
            "water_level_m": water_level_m,
            "approved_by": body.approved_by,
            "ts": now.isoformat(),
        },
    )

    if body.notify_line:
        dispatch_log = send_dispatch(
            work_order_id=wo.id,
            action_type=action_type,
            assigned_unit=assigned_unit,
            flood_node_name=flood_node_name,
            water_level_m=float(node[3]) if node[3] is not None else None,
            options=body.line_options,
        )
        wo.notes = f"{body.notes}\n{dispatch_log}".strip() if body.notes else dispatch_log
        wo.line_dispatched = True
        wo.line_dispatched_at = now
        await ledger_svc.append_event(
            db,
            "WO_LINE_SENT",
            {
                "work_order_id": wo.id,
                "included_fields": _line_included_fields(body.line_options),
                "ts": now.isoformat(),
            },
        )

    await db.commit()
    return await _fetch_wo_out(db, wo.id)


@router.post("/{wo_id}/confirm", response_model=WorkOrderOut)
async def confirm_work_order(wo_id: int, body: WorkOrderConfirm, db: DBDep) -> WorkOrderOut:
    result = await db.execute(
        text("SELECT id, status FROM work_order WHERE id = :id FOR UPDATE"),
        {"id": wo_id},
    )
    raw = result.first()
    if raw is None:
        raise HTTPException(status_code=404, detail=f"work_order {wo_id} not found")
    if raw[1] != "pending":
        raise HTTPException(
            status_code=409,
            detail=f"work_order {wo_id} is '{raw[1]}', expected 'pending'",
        )

    now = datetime.now(UTC)
    await db.execute(
        text("""
            UPDATE work_order
            SET status        = 'dispatched',
                confirmed_by  = :confirmed_by,
                updated_at    = :now,
                dispatched_at = :now
            WHERE id = :id
        """),
        {"confirmed_by": body.confirmed_by, "now": now, "id": wo_id},
    )

    await ledger_svc.append_event(
        db,
        "WO_DISPATCHED",
        {
            "work_order_id": wo_id,
            "confirmed_by": body.confirmed_by,
            "ts": now.isoformat(),
        },
    )
    await db.commit()
    # NOTE: when send_dispatch calls a real external API (LINE Notify etc.),
    # call it HERE — after db.commit() — to prevent double-dispatch on retry.
    return await _fetch_wo_out(db, wo_id)


@router.patch("/{wo_id}", response_model=WorkOrderOut)
async def update_work_order(wo_id: int, body: WorkOrderPatch, db: DBDep) -> WorkOrderOut:
    result = await db.execute(
        text("""
            SELECT id, status, action_type, assigned_unit, notes, line_dispatched
            FROM work_order WHERE id = :id FOR UPDATE
        """),
        {"id": wo_id},
    )
    raw = result.first()
    if raw is None:
        raise HTTPException(status_code=404, detail=f"work_order {wo_id} not found")
    if raw[1] != "pending":
        raise HTTPException(
            status_code=409,
            detail=f"work_order {wo_id} is '{raw[1]}'; can only edit pending work orders",
        )

    old_line_dispatched = bool(raw[5])
    old_values: dict[str, Any] = {}
    new_values: dict[str, Any] = {}
    changed_fields: list[str] = []
    set_clauses: list[str] = ["updated_at = :now"]
    params: dict[str, Any] = {"now": datetime.now(UTC), "id": wo_id}

    if body.action_type is not None and body.action_type != str(raw[2]):
        old_values["action_type"] = str(raw[2])
        new_values["action_type"] = body.action_type
        changed_fields.append("action_type")
        set_clauses.append("action_type = :action_type")
        params["action_type"] = body.action_type

    if body.assigned_unit is not None and body.assigned_unit != str(raw[3]):
        old_values["assigned_unit"] = str(raw[3])
        new_values["assigned_unit"] = body.assigned_unit
        changed_fields.append("assigned_unit")
        set_clauses.append("assigned_unit = :assigned_unit")
        params["assigned_unit"] = body.assigned_unit

    if body.notes is not None:
        old_notes = str(raw[4]) if raw[4] is not None else None
        if body.notes != old_notes:
            old_values["notes"] = old_notes
            new_values["notes"] = body.notes
            changed_fields.append("notes")
            set_clauses.append("notes = :notes")
            params["notes"] = body.notes or None

    if changed_fields:
        await db.execute(
            text(f"UPDATE work_order SET {', '.join(set_clauses)} WHERE id = :id"),
            params,
        )
        await ledger_svc.append_event(
            db,
            "WO_UPDATED",
            {
                "work_order_id": wo_id,
                "changed_fields": changed_fields,
                "old_values": old_values,
                "new_values": new_values,
            },
        )

    await db.commit()
    return await _fetch_wo_out(db, wo_id, resend_required=old_line_dispatched)


@router.post("/{wo_id}/notify-line", response_model=WorkOrderOut)
async def notify_line_dispatch(
    wo_id: int, body: LineNotifyRequest, db: DBDep
) -> WorkOrderOut:
    result = await db.execute(
        text("""
            SELECT wo.id, wo.status, wo.action_type, wo.assigned_unit,
                   fn.name, fn.current_fused_level
            FROM work_order wo
            JOIN flood_node fn ON fn.id = wo.flood_node_id
            WHERE wo.id = :id
            FOR UPDATE OF wo
        """),
        {"id": wo_id},
    )
    raw = result.first()
    if raw is None:
        raise HTTPException(status_code=404, detail=f"work_order {wo_id} not found")
    if raw[1] in ("done", "mismatch"):
        raise HTTPException(
            status_code=409,
            detail=f"work_order {wo_id} is terminal ('{raw[1]}'); cannot send LINE",
        )

    dispatch_log = send_dispatch(
        work_order_id=wo_id,
        action_type=str(raw[2]),
        assigned_unit=str(raw[3]),
        flood_node_name=str(raw[4]),
        water_level_m=float(raw[5]) if raw[5] is not None else None,
        options=body.line_options,
    )
    now = datetime.now(UTC)
    await db.execute(
        text("""
            UPDATE work_order
            SET line_dispatched    = TRUE,
                line_dispatched_at = :now,
                updated_at         = :now,
                notes = CASE
                    WHEN notes IS NULL THEN :log
                    ELSE notes || E'\\n' || :log
                END
            WHERE id = :id
        """),
        {"now": now, "log": dispatch_log, "id": wo_id},
    )

    await ledger_svc.append_event(
        db,
        "WO_LINE_SENT",
        {
            "work_order_id": wo_id,
            "included_fields": _line_included_fields(body.line_options),
            "ts": now.isoformat(),
        },
    )
    await db.commit()
    return await _fetch_wo_out(db, wo_id)
