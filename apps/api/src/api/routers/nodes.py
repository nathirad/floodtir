from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.schemas.node import FloodNodeOut

router = APIRouter(tags=["nodes"])

DBDep = Annotated[AsyncSession, Depends(get_db)]


class StatsOut(BaseModel):
    flood_node_count: int
    reports_today: int
    work_orders_open: int


@router.get("/stats", response_model=StatsOut)
async def get_stats(db: DBDep) -> StatsOut:
    node_result = await db.execute(text("SELECT COUNT(*) FROM flood_node"))
    node_count = int(node_result.scalar() or 0)

    today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    report_result = await db.execute(
        text("SELECT COUNT(*) FROM osint_report WHERE ts >= :today"),
        {"today": today_start},
    )
    reports_today = int(report_result.scalar() or 0)

    wo_result = await db.execute(
        text("SELECT COUNT(*) FROM work_order WHERE status IN ('pending', 'dispatched')")
    )
    work_orders_open = int(wo_result.scalar() or 0)

    return StatsOut(
        flood_node_count=node_count,
        reports_today=reports_today,
        work_orders_open=work_orders_open,
    )


@router.get("/flood-nodes", response_model=list[FloodNodeOut])
async def list_flood_nodes(db: DBDep) -> list[FloodNodeOut]:
    result = await db.execute(
        text("""
            SELECT id, name, district,
                   ST_Y(geom) AS lat, ST_X(geom) AS lon,
                   current_fused_level, n_reports, last_updated
            FROM flood_node
            ORDER BY id
        """)
    )
    return [
        FloodNodeOut(
            id=int(row[0]),
            name=str(row[1]),
            district=str(row[2]),
            lat=float(row[3]),
            lon=float(row[4]),
            current_fused_level=float(row[5]) if row[5] is not None else None,
            n_reports=int(row[6]) if row[6] is not None else 0,
            last_updated=row[7],
        )
        for row in result.all()
    ]
