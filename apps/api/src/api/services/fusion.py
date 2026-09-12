from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings


async def find_nearest_node(db: AsyncSession, lat: float, lon: float) -> int | None:
    """Return id of nearest flood_node within 500 m, or None."""
    result = await db.execute(
        text("""
            SELECT id
            FROM flood_node
            WHERE ST_DWithin(
                    geom::geography,
                    ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
                    500
                  )
            ORDER BY ST_Distance(
                geom::geography,
                ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography
            )
            LIMIT 1
        """),
        {"lat": lat, "lon": lon},
    )
    row = result.first()
    return int(row[0]) if row is not None else None


async def fuse_node(db: AsyncSession, node_id: int) -> None:
    """Weighted-average fusion over last 6 h; updates flood_node in place.

    weight = reporter.trust_score × osint_report.confidence
    Caller is responsible for committing the transaction.
    """
    result = await db.execute(
        text("""
            SELECT
              SUM(r.trust_score * o.confidence * o.water_level_m) /
                NULLIF(SUM(r.trust_score * o.confidence), 0) AS fused_level,
              COUNT(*) AS n_reports
            FROM osint_report o
            JOIN reporter r ON o.reporter_id = r.id
            WHERE o.flood_node_id = :nid
              AND o.ts > NOW() - INTERVAL '6 hours'
              AND o.water_level_m IS NOT NULL
        """),
        {"nid": node_id},
    )
    row = result.first()
    if row is None or row[0] is None:
        return
    if int(row[1]) < settings.corroboration_min_n:
        return
    await db.execute(
        text("""
            UPDATE flood_node
            SET current_fused_level = :fl,
                n_reports = :nr,
                last_updated = NOW()
            WHERE id = :nid
        """),
        {"fl": float(row[0]), "nr": int(row[1]), "nid": node_id},
    )
