"""Water surface IDW interpolation.

Computes Inverse Distance Weighting over a 25×25 grid from fused flood_node levels.
Pure Python — no numpy/scipy dependency.
"""

import math
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db

router = APIRouter(tags=["water-surface"])

DBDep = Annotated[AsyncSession, Depends(get_db)]

_LAT_MIN, _LAT_MAX = 13.68, 13.80
_LON_MIN, _LON_MAX = 100.73, 100.83
_GRID_N = 25
_IDW_POWER = 2.0
_MIN_NODES = 2


def _idw(
    q_lat: float,
    q_lon: float,
    lats: list[float],
    lons: list[float],
    levels: list[float],
) -> float:
    total_w = 0.0
    total_wl = 0.0
    for lat, lon, level in zip(lats, lons, levels, strict=True):
        d = math.sqrt((lat - q_lat) ** 2 + (lon - q_lon) ** 2)
        if d < 1e-10:
            return level
        w = 1.0 / d**_IDW_POWER
        total_w += w
        total_wl += w * level
    return total_wl / total_w


@router.get("/water-surface")
async def get_water_surface(
    db: DBDep,
) -> dict[str, list[dict[str, float]]]:
    result = await db.execute(
        text("""
            SELECT ST_Y(geom) AS lat, ST_X(geom) AS lon, current_fused_level
            FROM flood_node
            WHERE current_fused_level IS NOT NULL
        """)
    )
    rows = result.all()
    if len(rows) < _MIN_NODES:
        return {"points": []}

    lats = [float(r[0]) for r in rows]
    lons = [float(r[1]) for r in rows]
    levels = [float(r[2]) for r in rows]

    lat_step = (_LAT_MAX - _LAT_MIN) / _GRID_N
    lon_step = (_LON_MAX - _LON_MIN) / _GRID_N

    points: list[dict[str, float]] = []
    for i in range(_GRID_N):
        for j in range(_GRID_N):
            q_lat = _LAT_MIN + (i + 0.5) * lat_step
            q_lon = _LON_MIN + (j + 0.5) * lon_step
            level = _idw(q_lat, q_lon, lats, lons, levels)
            points.append(
                {
                    "lat": round(q_lat, 6),
                    "lon": round(q_lon, 6),
                    "level": round(level, 3),
                    "dlat": round(lat_step / 2, 6),
                    "dlon": round(lon_step / 2, 6),
                }
            )
    return {"points": points}
