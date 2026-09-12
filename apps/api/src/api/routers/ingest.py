from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile
from geoalchemy2.elements import WKTElement
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.models.osint_report import OsintReport
from api.models.reporter import Reporter
from api.schemas.ingest import ReportOut, RoughLevel
from api.services.fusion import find_nearest_node, fuse_node
from api.services.quality import is_duplicate, is_in_geofence
from api.triage import triage

router = APIRouter(prefix="/ingest", tags=["ingest"])

DBDep = Annotated[AsyncSession, Depends(get_db)]


@router.post("/report", response_model=ReportOut)
async def ingest_report(
    lat: Annotated[float, Form()],
    lon: Annotated[float, Form()],
    db: DBDep,
    rough_level: Annotated[RoughLevel | None, Form()] = None,
    photo: Annotated[UploadFile | None, File()] = None,
    reporter_handle: Annotated[str | None, Form()] = None,
    is_simulated: Annotated[bool, Form()] = False,
) -> ReportOut:
    _label = "SIMULATED-by-design" if is_simulated else "REAL"

    if not is_in_geofence(lat, lon):
        return ReportOut(
            report_id=-1,
            ts=datetime.now(UTC),
            water_level_m=None,
            confidence=0.0,
            flood_node_id=None,
            status="rejected",
            label=_label,
        )

    handle = reporter_handle or ("sim" if is_simulated else "anon")
    row = await db.execute(
        select(Reporter)
        .where(Reporter.handle == handle)
        .where(Reporter.is_simulated == is_simulated)
    )
    reporter = row.scalar_one_or_none()
    if reporter is None:
        reporter = Reporter(handle=handle, is_simulated=is_simulated)
        db.add(reporter)
        await db.flush()

    assert reporter.id is not None
    if await is_duplicate(db, reporter.id, lat, lon):
        return ReportOut(
            report_id=-1,
            ts=datetime.now(UTC),
            water_level_m=None,
            confidence=0.0,
            flood_node_id=None,
            status="duplicate",
            label=_label,
        )

    result = triage(rough_level, has_photo=photo is not None)
    photo_ref: str | None = photo.filename if photo is not None else None
    node_id = await find_nearest_node(db, lat, lon)
    ts_now = datetime.now(UTC)

    report = OsintReport(
        ts=ts_now,
        geom=WKTElement(f"POINT({lon} {lat})", srid=4326),
        water_level_m=result.water_level_m,
        confidence=result.confidence,
        photo_ref=photo_ref,
        reporter_id=reporter.id,
        flood_node_id=node_id,
        is_simulated=is_simulated,
        source_label="datagen" if is_simulated else "citizen",
    )
    db.add(report)
    await db.flush()

    if node_id is not None:
        await fuse_node(db, node_id)

    await db.commit()
    await db.refresh(report)

    return ReportOut(
        report_id=report.id,
        ts=report.ts,
        water_level_m=report.water_level_m,
        confidence=report.confidence,
        flood_node_id=report.flood_node_id,
        status="accepted",
        label=_label,
    )
