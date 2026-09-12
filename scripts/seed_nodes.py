#!/usr/bin/env python3
"""Seed 20 flood_nodes for Lat Krabang district from 2011 flood extent.

Run: uv run --package api python scripts/seed_nodes.py
"""

import asyncio

from sqlalchemy import text

from api.database import AsyncSessionLocal

# (name, lat, lon, district, historical_max_level_m)
# Positions from 2011 Bangkok flood extent; levels approximate (metres).
_RAW: list[tuple[str, float, float, str, float]] = [
    ("ลาดกระบัง กลาง", 13.7462, 100.7764, "ลาดกระบัง", 1.20),
    ("ซ.ลาดกระบัง 1", 13.7490, 100.7720, "ลาดกระบัง", 1.10),
    ("ซ.ลาดกระบัง 3", 13.7520, 100.7680, "ลาดกระบัง", 0.90),
    ("ตลาดลาดกระบัง", 13.7441, 100.7695, "ลาดกระบัง", 1.30),
    ("สถานีลาดกระบัง", 13.7412, 100.7785, "ลาดกระบัง", 0.80),
    ("ชุมชนหัวตะเข้", 13.7600, 100.7540, "ลาดกระบัง", 1.50),
    ("ทับยาว", 13.7310, 100.7850, "ลาดกระบัง", 1.40),
    ("ขุมทอง", 13.7240, 100.7900, "ลาดกระบัง", 1.60),
    ("ลำปลาทิว", 13.7180, 100.7680, "ลาดกระบัง", 1.20),
    ("คลองสามประเวศ", 13.7380, 100.7590, "ลาดกระบัง", 1.00),
    ("บางชัน เหนือ", 13.7650, 100.8050, "คลองสาน", 1.10),
    ("มีนบุรี ใต้", 13.7770, 100.7620, "มีนบุรี", 0.95),
    ("บึงกุ่ม ตะวันออก", 13.7700, 100.7930, "บึงกุ่ม", 1.05),
    ("รามคำแหง-ลาดกระบัง", 13.7530, 100.8180, "ลาดกระบัง", 0.85),
    ("สะพานลาดกระบัง", 13.7520, 100.7870, "ลาดกระบัง", 1.15),
    ("โรงพยาบาลลาดกระบัง", 13.7410, 100.7690, "ลาดกระบัง", 0.70),
    ("สนามบินสุวรรณภูมิ-เหนือ", 13.6970, 100.7510, "ลาดกระบัง", 1.80),
    ("คลองหลวงแพ่ง", 13.7090, 100.8100, "ลาดกระบัง", 2.00),
    ("ประเวศ เหนือ", 13.7060, 100.7720, "ประเวศ", 1.35),
    ("สีเขียว-ลาดกระบัง", 13.7640, 100.7720, "ลาดกระบัง", 1.25),
]

NODES = [
    {"name": n, "lat": la, "lon": lo, "district": d, "hml": h}
    for n, la, lo, d, h in _RAW
]


async def seed() -> None:
    async with AsyncSessionLocal() as db:
        for node in NODES:
            await db.execute(
                text("""
                    INSERT INTO flood_node (name, geom, district, historical_max_level)
                    VALUES (
                        :name,
                        ST_SetSRID(ST_MakePoint(:lon, :lat), 4326),
                        :district,
                        :hml
                    )
                    ON CONFLICT DO NOTHING
                """),
                {
                    "name": node["name"],
                    "lat": node["lat"],
                    "lon": node["lon"],
                    "district": node["district"],
                    "hml": node["hml"],
                },
            )
        await db.commit()
    print(f"Seeded {len(NODES)} flood nodes")


if __name__ == "__main__":
    asyncio.run(seed())
