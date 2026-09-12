from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# Bangkok bounding box — coarse geofence (G8)
_LAT_MIN, _LAT_MAX = 13.4, 14.0
_LON_MIN, _LON_MAX = 100.3, 100.95


def is_in_geofence(lat: float, lon: float) -> bool:
    return _LAT_MIN <= lat <= _LAT_MAX and _LON_MIN <= lon <= _LON_MAX


async def is_duplicate(
    db: AsyncSession, reporter_id: int, lat: float, lon: float
) -> bool:
    """True if same reporter posted from within 50 m in the last 5 minutes."""
    result = await db.execute(
        text("""
            SELECT 1 FROM osint_report
            WHERE reporter_id = :rid
              AND ts > NOW() - INTERVAL '5 minutes'
              AND ST_DWithin(
                    geom::geography,
                    ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
                    50
                  )
            LIMIT 1
        """),
        {"rid": reporter_id, "lat": lat, "lon": lon},
    )
    return result.first() is not None
