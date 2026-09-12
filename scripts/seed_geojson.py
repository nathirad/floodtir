#!/usr/bin/env python3
import argparse
import asyncio
import json
from pathlib import Path
from sqlalchemy import text
from api.database import AsyncSessionLocal

async def seed_geojson(geojson_dir: Path, clear: bool):
    async with AsyncSessionLocal() as db:
        print("Connecting to DB...")
        
        if clear:
            print("Clearing existing geojson data from SQL...")
            await db.execute(text("TRUNCATE TABLE canal, pump_station, sump CASCADE"))
            await db.commit()
            print("Existing data cleared.")

        # 1. Seed Canals
        canals_file = geojson_dir / "canals.geojson"
        if canals_file.exists():
            print("Seeding canals...")
            with open(canals_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            features = data.get("features", [])
            print(f"Importing {len(features)} canals...")
            for idx, feat in enumerate(features):
                props = feat.get("properties", {})
                geom = feat.get("geometry", {})
                
                # Fallback properties
                name = props.get("canal_name") or f"คลองไม่มีชื่อ_{idx}"
                code = props.get("canal_code")
                ctype = props.get("canal_type")
                district = props.get("district_t")
                
                try:
                    length = float(props.get("shape_length") or props.get("SHAPE__Length") or 0.0)
                except (ValueError, TypeError):
                    length = 0.0
                try:
                    width = float(props.get("canal_width") or 0.0)
                except (ValueError, TypeError):
                    width = 0.0
                try:
                    depth = float(props.get("canal_depth") or 0.0)
                except (ValueError, TypeError):
                    depth = 0.0

                await db.execute(
                    text("""
                        INSERT INTO canal (name, code, canal_type, district, geom, length, width, depth)
                        VALUES (:name, :code, :ctype, :district, ST_GeomFromGeoJSON(:geom_str), :length, :width, :depth)
                    """),
                    {
                        "name": name,
                        "code": code,
                        "ctype": ctype,
                        "district": district,
                        "geom_str": json.dumps(geom),
                        "length": length,
                        "width": width,
                        "depth": depth
                    }
                )
                if idx % 100 == 0:
                    await db.commit()
            await db.commit()
            print("Canals seeded successfully.")
        else:
            print(f"File not found: {canals_file}")

        # 2. Seed Pump Stations
        pumps_file = geojson_dir / "pumpstations.geojson"
        if pumps_file.exists():
            print("Seeding pump stations...")
            with open(pumps_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            features = data.get("features", [])
            print(f"Importing {len(features)} pump stations...")
            for idx, feat in enumerate(features):
                props = feat.get("properties", {})
                geom = feat.get("geometry", {})
                
                name = props.get("pump_name") or f"สถานีสูบน้ำไม่มีชื่อ_{idx}"
                code = props.get("pump_code")
                ptype = props.get("pump_type")
                district = props.get("district_t")
                capacity = str(props.get("motor_total") or "")
                owner = props.get("owner")

                await db.execute(
                    text("""
                        INSERT INTO pump_station (name, code, pump_type, district, geom, capacity, owner)
                        VALUES (:name, :code, :ptype, :district, ST_GeomFromGeoJSON(:geom_str), :capacity, :owner)
                    """),
                    {
                        "name": name,
                        "code": code,
                        "ptype": ptype,
                        "district": district,
                        "geom_str": json.dumps(geom),
                        "capacity": capacity,
                        "owner": owner
                    }
                )
                if idx % 50 == 0:
                    await db.commit()
            await db.commit()
            print("Pump stations seeded successfully.")
        else:
            print(f"File not found: {pumps_file}")

        # 3. Seed Sumps
        sumps_file = geojson_dir / "sumps.geojson"
        if sumps_file.exists():
            print("Seeding sumps...")
            with open(sumps_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            features = data.get("features", [])
            print(f"Importing {len(features)} sumps...")
            for idx, feat in enumerate(features):
                props = feat.get("properties", {})
                geom = feat.get("geometry", {})
                
                name = props.get("sump_name") or f"บ่อสูบน้ำไม่มีชื่อ_{idx}"
                code = props.get("sump_code")
                stype = props.get("sump_type")
                district = props.get("district_t")
                
                try:
                    depth = float(props.get("sump_depth") or 0.0)
                except (ValueError, TypeError):
                    depth = 0.0
                try:
                    width = float(props.get("sump_width") or 0.0)
                except (ValueError, TypeError):
                    width = 0.0
                try:
                    length = float(props.get("sump_length") or 0.0)
                except (ValueError, TypeError):
                    length = 0.0

                await db.execute(
                    text("""
                        INSERT INTO sump (name, code, sump_type, district, geom, depth, width, length)
                        VALUES (:name, :code, :stype, :district, ST_GeomFromGeoJSON(:geom_str), :depth, :width, :length)
                    """),
                    {
                        "name": name,
                        "code": code,
                        "stype": stype,
                        "district": district,
                        "geom_str": json.dumps(geom),
                        "depth": depth,
                        "width": width,
                        "length": length
                    }
                )
                if idx % 50 == 0:
                    await db.commit()
            await db.commit()
            print("Sumps seeded successfully.")
        else:
            print(f"File not found: {sumps_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--clear", action="store_true", help="Clear existing data before seeding")
    parser.add_argument("--source-dir", type=str, default="D:\\Floodtir\\Tanu\\floodtir\\Floodtirdatta\\data\\geojson", help="Directory containing GeoJSON files")
    args = parser.parse_args()
    
    asyncio.run(seed_geojson(Path(args.source_dir), args.clear))
