from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.services import ledger as ledger_svc
from api.services.orchestrator import plan_dispatch


async def create_verification(
    db: AsyncSession,
    wo_id: int,
    outcome: str,
    verified_by: str,
    photo_ref: str | None,
) -> tuple[int, datetime, int | None]:
    """Verify a dispatched work order.

    Returns (verification_id, created_at, new_work_order_id).
    new_work_order_id is non-None only when outcome == MISMATCH.
    Raises HTTPException on bad state.
    """
    result = await db.execute(
        text("SELECT id, flood_node_id, status FROM work_order WHERE id = :id FOR UPDATE"),
        {"id": wo_id},
    )
    raw = result.first()
    if raw is None:
        raise HTTPException(status_code=404, detail=f"work_order {wo_id} not found")
    if raw[2] != "dispatched":
        raise HTTPException(
            status_code=409,
            detail=f"work_order {wo_id} is '{raw[2]}', expected 'dispatched'",
        )

    flood_node_id: int = int(raw[1])
    now = datetime.now(UTC)

    v_result = await db.execute(
        text("""
            INSERT INTO verification (work_order_id, outcome, photo_ref, verified_by, created_at)
            VALUES (:wo_id, :outcome, :photo_ref, :verified_by, :created_at)
            RETURNING id
        """),
        {
            "wo_id": wo_id,
            "outcome": outcome,
            "photo_ref": photo_ref,
            "verified_by": verified_by,
            "created_at": now,
        },
    )
    v_id = int(v_result.scalar_one())

    # FIX #7: use distinct terminal states so WO status alone reflects outcome
    # VERIFIED → 'done' | MISMATCH → 'mismatch' (avoids JOIN to distinguish on P5 board)
    terminal_status = "done" if outcome == "VERIFIED" else "mismatch"
    await db.execute(
        text("UPDATE work_order SET status = :status, updated_at = :now WHERE id = :id"),
        {"status": terminal_status, "now": now, "id": wo_id},
    )

    await ledger_svc.append_event(
        db,
        "VERIFY_OUTCOME",
        {
            "work_order_id": wo_id,
            "verification_id": v_id,
            "outcome": outcome,
            "verified_by": verified_by,
            "flood_node_id": flood_node_id,
            "ts": now.isoformat(),
        },
    )

    new_wo_id: int | None = None
    if outcome == "MISMATCH":
        node_result = await db.execute(
            text(
                "SELECT name, district, current_fused_level FROM flood_node WHERE id = :nid"
            ),
            {"nid": flood_node_id},
        )
        node = node_result.first()

        # FIX #4: raise explicitly — silent skip would return 201 with new_wo=None,
        # making caller believe escalation succeeded when it did not
        if node is None:
            raise HTTPException(
                status_code=409,
                detail=f"flood_node {flood_node_id} not found; cannot escalate MISMATCH",
            )

        # FIX #5: 0.0 fallback produces minimum-severity plan for an active flood;
        # require actual fused level so plan_dispatch chooses the right action_type
        if node[2] is None:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"flood_node {flood_node_id} has no current water level — "
                    "run datagen or wait for new reports before escalating"
                ),
            )

        district = str(node[1])
        water_level_m = float(node[2])
        plan = plan_dispatch(district, water_level_m)

        # FIX #9 (G5): include is_simulated so escalated WO carries provenance label
        cols = (
            "flood_node_id, status, action_type, "
            "assigned_unit, notes, is_simulated, created_at, updated_at"
        )
        new_wo_result = await db.execute(
            text(
                f"INSERT INTO work_order ({cols}) "
                "VALUES (:flood_node_id, 'pending', :action_type, "
                ":assigned_unit, :notes, TRUE, :now, :now) RETURNING id"
            ),
            {
                "flood_node_id": flood_node_id,
                "action_type": plan.action_type,
                "assigned_unit": plan.assigned_unit,
                "notes": f"[ESCALATED from WO#{wo_id} — MISMATCH outcome]",
                "now": now,
            },
        )
        new_wo_id = int(new_wo_result.scalar_one())

        await ledger_svc.append_event(
            db,
            "MISMATCH_ESCALATE",
            {
                "old_work_order_id": wo_id,
                "new_work_order_id": new_wo_id,
                "flood_node_id": flood_node_id,
                "ts": now.isoformat(),
            },
        )

    await db.commit()
    return v_id, now, new_wo_id
