#!/usr/bin/env python3
"""Simulate 10 concurrent reporters posting flood observations to the ingest API.

All reports are tagged is_simulated=true (G5 guardrail).
Run: uv run --package api python scripts/datagen.py

Prerequisites:
  - API server running at http://localhost:8000
  - DB seeded: make seed
"""

import asyncio
import random

import httpx

API_URL = "http://localhost:8000"

# 10 simulated reporters — positions near seeded flood_nodes (within 500 m)
REPORTERS = [
    {"handle": "sim_00", "lat": 13.7465, "lon": 100.7770, "rough_level": "เข่า"},
    {"handle": "sim_01", "lat": 13.7492, "lon": 100.7724, "rough_level": "เอว"},
    {"handle": "sim_02", "lat": 13.7518, "lon": 100.7682, "rough_level": "ข้อเท้า"},
    {"handle": "sim_03", "lat": 13.7443, "lon": 100.7698, "rough_level": "เข่า"},
    {"handle": "sim_04", "lat": 13.7415, "lon": 100.7788, "rough_level": "ข้อเท้า"},
    {"handle": "sim_05", "lat": 13.7602, "lon": 100.7544, "rough_level": "เอว"},
    {"handle": "sim_06", "lat": 13.7312, "lon": 100.7852, "rough_level": "เข่า"},
    {"handle": "sim_07", "lat": 13.7242, "lon": 100.7902, "rough_level": "อก"},
    {"handle": "sim_08", "lat": 13.7183, "lon": 100.7682, "rough_level": "เอว"},
    {"handle": "sim_09", "lat": 13.7382, "lon": 100.7592, "rough_level": "เข่า"},
]


async def post_report(client: httpx.AsyncClient, reporter: dict[str, str | float]) -> None:
    jitter_lat = float(reporter["lat"]) + random.uniform(-0.0005, 0.0005)
    jitter_lon = float(reporter["lon"]) + random.uniform(-0.0005, 0.0005)
    try:
        resp = await client.post(
            f"{API_URL}/ingest/report",
            data={
                "lat": str(jitter_lat),
                "lon": str(jitter_lon),
                "rough_level": reporter["rough_level"],
                "reporter_handle": reporter["handle"],
                "is_simulated": "true",
            },
            timeout=10.0,
        )
        data: dict[str, object] = resp.json()
        level = data.get("water_level_m")
        level_str = f"{level:.2f}m" if isinstance(level, float) else "–"
        print(
            f"[{reporter['handle']}] {data.get('status'):10s} | "
            f"level={level_str} | node={data.get('flood_node_id')} | "
            f"label={data.get('label')}"
        )
    except Exception as exc:
        print(f"[{reporter['handle']}] ERROR: {exc}")


async def main() -> None:
    print(f"Posting {len(REPORTERS)} concurrent reports to {API_URL}/ingest/report ...\n")
    async with httpx.AsyncClient() as client:
        await asyncio.gather(*[post_report(client, r) for r in REPORTERS])
    print("\nDone. Refresh the map to see updated water levels.")


if __name__ == "__main__":
    asyncio.run(main())
