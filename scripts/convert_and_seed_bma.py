#!/usr/bin/env python3
import argparse
import asyncio
import datetime
import json
from pathlib import Path
from sqlalchemy import text
from api.database import AsyncSessionLocal

async def seed_bma(source_dir: Path, clear: bool, limit_history: int | None):
    async with AsyncSessionLocal() as db:
        print("Connecting to DB...")
        
        # 1. Reporter setup
        reporter_handle = "bma_telemetry"
        res = await db.execute(
            text("SELECT id FROM reporter WHERE handle = :handle"),
            {"handle": reporter_handle}
        )
        reporter_row = res.fetchone()
        if not reporter_row:
            print(f"Creating reporter: {reporter_handle}")
            res_insert = await db.execute(
                text("INSERT INTO reporter (handle, trust_score, is_simulated) VALUES (:handle, 1.0, false) RETURNING id"),
                {"handle": reporter_handle}
            )
            reporter_id = res_insert.scalar()
        else:
            reporter_id = reporter_row[0]
            print(f"Using existing reporter ID: {reporter_id}")
        
        # 2. Clear if requested
        if clear:
            print("Clearing existing BMA node data...")
            # Delete BMA reports
            await db.execute(
                text("DELETE FROM osint_report WHERE reporter_id = :rep_id"),
                {"rep_id": reporter_id}
            )
            
            # Delete BMA flood nodes matching the station catalog
            stations_file = source_dir / "water_all_stations.json"
            if stations_file.exists():
                with open(stations_file, "r", encoding="utf-8") as f:
                    stations_data = json.load(f)["stations"]
                    station_ids = [s["station_id"] for s in stations_data]
                
                if station_ids:
                    await db.execute(
                        text("DELETE FROM flood_node WHERE id = ANY(:ids)"),
                        {"ids": station_ids}
                    )
            await db.commit()
            print("BMA node data cleared.")

        # 3. Seed Flood Nodes (Stations)
        stations_file = source_dir / "water_all_stations.json"
        if not stations_file.exists():
            print(f"Error: {stations_file} not found.")
            return

        print("Reading stations...")
        with open(stations_file, "r", encoding="utf-8") as f:
            stations = json.load(f)["stations"]

        print(f"Importing {len(stations)} flood nodes...")
        for idx, station in enumerate(stations):
            station_id = station["station_id"]
            name = station["station_name_th"]
            lat = station["location"]["latitude"]
            lon = station["location"]["longitude"]
            district = station["district_name_th"]
            
            # Fallback threshold logic
            hml = (
                station.get("thresholds", {}).get("critical_in_m_msl")
                or station.get("levels", {}).get("left_bank_m_msl")
                or station.get("levels", {}).get("water_max_m_msl")
                or 1.50
            )

            # Insert node with ON CONFLICT DO UPDATE
            await db.execute(
                text("""
                    INSERT INTO flood_node (id, name, geom, district, historical_max_level)
                    VALUES (
                        :id, :name, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326), :district, :hml
                    )
                    ON CONFLICT (id) DO UPDATE SET
                        name = EXCLUDED.name,
                        geom = EXCLUDED.geom,
                        district = EXCLUDED.district,
                        historical_max_level = EXCLUDED.historical_max_level
                """),
                {"id": station_id, "name": name, "lat": lat, "lon": lon, "district": district, "hml": hml}
            )
            
            if idx % 50 == 0:
                await db.commit()
        await db.commit()
        print("Stations imported successfully.")

        # 4. Ingest Historical Measurements
        print("Importing history measurements...")
        histories_dir = source_dir / "station_histories"
        
        # Read latest snapshot as well
        latest_snap_file = source_dir / "water_latest_snapshot.json"
        latest_snap_data = {}
        if latest_snap_file.exists():
            with open(latest_snap_file, "r", encoding="utf-8") as f:
                latest_snap_data = {s["station_id"]: s for s in json.load(f).get("stations", [])}

        for idx, station in enumerate(stations):
            station_id = station["station_id"]
            history_file = histories_dir / f"{station_id}.json"
            points = []
            
            # Load historical points
            if history_file.exists():
                with open(history_file, "r", encoding="utf-8") as f:
                    try:
                        h_data = json.load(f)
                        series = h_data.get("series", [])
                        if series:
                            raw_points = series[0].get("points", [])
                            # Sort by observed_at_utc desc to get newest points
                            raw_points.sort(key=lambda x: x["observed_at_utc"], reverse=True)
                            if limit_history is not None:
                                raw_points = raw_points[:limit_history]
                            points.extend(raw_points)
                    except Exception as e:
                        print(f"Error reading history for station {station_id}: {e}")

            # Add latest snapshot measurement if not duplicate
            if station_id in latest_snap_data:
                snap = latest_snap_data[station_id]
                obs_at = snap.get("observed_at")
                wl = snap.get("water_levels_m_msl", {}).get("wl_in") or snap.get("wl_in_m_msl")
                if obs_at and wl is not None and wl != -99:
                    # Avoid duplicates with history
                    if not any(p["observed_at_utc"] == obs_at for p in points):
                        points.append({"observed_at_utc": obs_at, "value_m_msl": wl})

            if not points:
                continue

            print(f"Station {station_id} ({idx + 1}/{len(stations)}): seeding {len(points)} records...")
            for pt in points:
                val = pt["value_m_msl"]
                if val == -99 or val is None:
                    continue
                
                ts_str = pt["observed_at_utc"]
                try:
                    # Parse timestamp (e.g. 2026-06-25T00:40:00Z or with offset)
                    ts = datetime.datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                except ValueError:
                    ts = datetime.datetime.now(datetime.timezone.utc)
                
                # Insert report into osint_report
                await db.execute(
                    text("""
                        INSERT INTO osint_report (ts, geom, water_level_m, confidence, reporter_id, flood_node_id, is_simulated, source_label)
                        VALUES (
                            :ts, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326), :val, 1.0, :rep_id, :node_id, false, 'sensor'
                        )
                        ON CONFLICT DO NOTHING
                    """),
                    {
                        "ts": ts,
                        "lon": station["location"]["longitude"],
                        "lat": station["location"]["latitude"],
                        "val": val,
                        "rep_id": reporter_id,
                        "node_id": station_id
                    }
                )
            if idx % 20 == 0:
                await db.commit()
        await db.commit()
        
        # 5. Reset sequence generators
        print("Resetting primary key sequences...")
        await db.execute(text("SELECT setval('flood_node_id_seq', COALESCE((SELECT MAX(id) FROM flood_node), 0) + 1, false)"))
        await db.execute(text("SELECT setval('osint_report_id_seq', COALESCE((SELECT MAX(id) FROM osint_report), 0) + 1, false)"))
        await db.commit()
        print("Seeding completed successfully.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--clear", action="store_true", help="Clear existing BMA data before seeding")
    parser.add_argument("--limit-history", type=int, default=50, help="Max history items per station")
    parser.add_argument("--source-dir", type=str, default="D:\\Floodtir\\Tanu\\floodtir\\Floodtirdatta\\water-data", help="Source directory containing BMA JSONs")
    args = parser.parse_args()
    
    asyncio.run(seed_bma(Path(args.source_dir), args.clear, args.limit_history))
