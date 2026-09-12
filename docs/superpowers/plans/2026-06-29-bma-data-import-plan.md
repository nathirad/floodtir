# BMA Data Ingestion and Folder Rename Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** สร้างสคริปต์ Python ใน `Tanu/floodtir` เพื่อแปลงและนำเข้าข้อมูลประวัติและสถานีวัดน้ำ กทม. (BMA) จากไฟล์ JSON ใน `Floodtirdatta` และสร้างไฟล์ `context.md` อธิบายโครงสร้างข้อมูล

**Architecture:** สคริปต์ Python เชื่อมต่อโดยตรงกับฐานข้อมูลผ่าน SQLAlchemy Session ของระบบ FastAPI นำเข้าข้อมูลสถานีเป็น `flood_node` และข้อมูลประวัติเป็น `osint_report` โดยกำหนด `is_simulated = False` ( REAL observation ) ตามกฎ G5

**Tech Stack:** Python, SQLAlchemy, GeoAlchemy2, TimescaleDB, PostGIS

## Global Constraints
- **G5** - ทุกแถวข้อมูลที่จำลองขึ้นต้องมี `is_simulated = true` และข้อมูลจริงจากเซนเซอร์ต้องมี `is_simulated = false`
- **G7** - ข้อมูลจากการสังเกตการณ์ทั่วไปจะต้องมีผลยืนยันร่วม (corroboration) ก่อนสั่งการ แต่ข้อมูล REAL จากเซนเซอร์/สถานีวัดน้ำ BMA ถือเป็นพยานยืนยันในตัวเองได้

---

## Tasks

### Task 1: Create Documentation `context.md`

**Files:**
- Create: `D:\Floodtir\Floodtirdatta\context.md`

**Interfaces:**
- Consumes: JSON files inside `D:\Floodtir\Floodtirdatta\water-data`
- Produces: Detailed documentation markdown

- [ ] **Step 1: Write context.md**
  สร้างไฟล์ `D:\Floodtir\Floodtirdatta\context.md` เพื่อสรุปข้อมูลและวิธีการใช้งานระบบ รวมถึงคำสั่งที่ใช้ในการประมวลผลและการอัปเดตข้อมูลระดับน้ำในระบบ
  
- [ ] **Step 2: Commit documentation**
  ```bash
  git add D:\Floodtir\Floodtirdatta\context.md
  git commit -m "docs: add context.md detailing data structure and update flow"
  ```

---

### Task 2: Implement `convert_and_seed_bma.py` Script

**Files:**
- Create: `D:\Floodtir\Tanu\floodtir\scripts\convert_and_seed_bma.py`

**Interfaces:**
- Consumes: `D:\Floodtir\Floodtirdatta\water-data\water_all_stations.json`, `D:\Floodtir\Floodtirdatta\water-data\station_histories/*.json`
- Produces: Entries in `reporter`, `flood_node`, and `osint_report` tables in PostgreSQL

- [ ] **Step 1: Write seeder code**
  สร้างไฟล์ `D:\Floodtir\Tanu\floodtir\scripts\convert_and_seed_bma.py` ด้วยโครงสร้างโค้ดดังนี้:

  ```python
  #!/usr/bin/env python3
  import argparse
  import asyncio
  import datetime
  import json
  from pathlib import Path
  from geoalchemy2.elements import WKTElement
  from sqlalchemy import text, delete
  from sqlalchemy.ext.asyncio import AsyncSession
  from api.database import AsyncSessionLocal
  from api.models.flood_node import FloodNode
  from api.models.osint_report import OsintReport
  from api.models.reporter import Reporter

  async def seed_bma(source_dir: Path, clear: bool, limit_history: int | None):
      async with AsyncSessionLocal() as db:
          print("Connecting to DB...")
          # 1. Reporter
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
          
          # 2. Clear if requested
          if clear:
              print("Clearing existing BMA node data...")
              # Delete BMA reports (reporter_id = reporter_id)
              await db.execute(
                  text("DELETE FROM osint_report WHERE reporter_id = :rep_id"),
                  {"rep_id": reporter_id}
              )
              # Delete BMA flood nodes (stations with IDs matching station catalog)
              with open(source_dir / "water_all_stations.json", "r", encoding="utf-8") as f:
                  stations_data = json.load(f)["stations"]
                  station_ids = [s["station_id"] for s in stations_data]
              
              if station_ids:
                  await db.execute(
                      text("DELETE FROM flood_node WHERE id = ANY(:ids)"),
                      {"ids": station_ids}
                  )
              await db.commit()

          # 3. Seed Flood Nodes (Stations)
          print("Reading stations...")
          with open(source_dir / "water_all_stations.json", "r", encoding="utf-8") as f:
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
                      h_data = json.load(f)
                      series = h_data.get("series", [])
                      if series:
                          raw_points = series[0].get("points", [])
                          # Sort by observed_at_utc desc
                          raw_points.sort(key=lambda x: x["observed_at_utc"], reverse=True)
                          if limit_history:
                              raw_points = raw_points[:limit_history]
                          points.extend(raw_points)

              # Add latest snapshot measurement if not duplicate
              if station_id in latest_snap_data:
                  snap = latest_snap_data[station_id]
                  obs_at = snap.get("observed_at")
                  # Convert observed_at if it has +07:00 timezone
                  # Check wl_in_m_msl / wl_in
                  wl = snap.get("water_levels_m_msl", {}).get("wl_in") or snap.get("wl_in_m_msl")
                  if obs_at and wl is not None and wl != -99:
                      # Avoid duplicates with history
                      if not any(p["observed_at_utc"] == obs_at for p in points):
                          points.append({"observed_at_utc": obs_at, "value_m_msl": wl})

              if not points:
                  continue

              print(f"Station {station_id}: seeding {len(points)} records...")
              for pt in points:
                  val = pt["value_m_msl"]
                  if val == -99 or val is None:
                      continue
                  
                  ts_str = pt["observed_at_utc"]
                  # Convert ISO to datetime object
                  # For example: 2026-06-25T00:40:00Z
                  try:
                      ts = datetime.datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                  except ValueError:
                      # Handle other formats if any
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
      parser.add_argument("--source-dir", type=str, default="D:\\Floodtir\\Floodtirdatta\\water-data", help="Source directory containing BMA JSONs")
      args = parser.parse_args()
      
      asyncio.run(seed_bma(Path(args.source_dir), args.clear, args.limit_history))
  ```

- [ ] **Step 2: Dry Run with Limit**
  ทดลองรันสคริปต์ในโหมดทดสอบด้วยจำกัดข้อมูลประวัติ 5 แถวเพื่อดูข้อผิดพลาด:
  Run command in `D:\Floodtir\Tanu\floodtir`:
  ```bash
  uv run --package api python scripts/convert_and_seed_bma.py --clear --limit-history 5
  ```
  Expected: ทำงานผ่านเสร็จสิ้นและพิมพ์ "Seeding completed successfully."

- [ ] **Step 3: Commit code**
  ```bash
  git add D:\Floodtir\Tanu\floodtir\scripts\convert_and_seed_bma.py
  git commit -m "feat: add BMA seeder script to populate flood_nodes and real telemetry measurements"
  ```

---

## Verification Plan

### Automated Verification
- ตรวจสอบจำนวนข้อมูลในฐานข้อมูล:
  ```bash
  psql -U floodtir -h localhost -d floodtir -c "SELECT COUNT(*) FROM flood_node"
  psql -U floodtir -h localhost -d floodtir -c "SELECT is_simulated, count(*) FROM osint_report GROUP BY is_simulated"
  ```
  คาดหวัง:
  - `flood_node` count = 283 (หรือบวกกับ 20 โหนดจำลองของเดิม = 303)
  - มีแถวข้อมูลใน `osint_report` ที่มี `is_simulated = false` (REAL)
