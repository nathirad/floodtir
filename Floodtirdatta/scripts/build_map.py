import os
import json
import re
from datetime import datetime

# Paths (scripts/ → project root is one level up)
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
HEAD_PATH = os.path.join(ROOT, "templates", "_head.html")
DATA_PATH = os.path.join(ROOT, "templates", "bkk_data.js")
FOOT_PATH = os.path.join(ROOT, "templates", "_foot.html")
MAP_PATH = os.path.join(ROOT, "flood_bkk_map.html")
DASHBOARD_PATH = os.path.join(ROOT, "river_dashboard.html")
SNAPSHOT_PATH = os.path.join(ROOT, "water-data", "water_latest_snapshot.json")
WATER_EDGES_PATH = os.path.join(ROOT, "water-data", "water_edges_geojson.json")

def main():
    # 1. If _foot.html doesn't exist, extract it from the current flood_bkk_map.html
    if not os.path.exists(FOOT_PATH) and os.path.exists(MAP_PATH):
        print("Extracting map logic to _foot.html...")
        with open(MAP_PATH, "r", encoding="utf-8") as f:
            content = f.read()
        
        # We find the position after /*DATA*/ marker
        marker = "/*DATA*/\n"
        idx = content.find(marker)
        if idx != -1:
            foot_content = content[idx + len(marker):]
            with open(FOOT_PATH, "w", encoding="utf-8") as f:
                f.write(foot_content)
            print(f"Created _foot.html successfully at: {FOOT_PATH}")
        else:
            print("Could not find separator marker '/*DATA*/' in flood_bkk_map.html.")
            return

    # 2. Build the final flood_bkk_map.html
    if os.path.exists(HEAD_PATH) and os.path.exists(DATA_PATH) and os.path.exists(FOOT_PATH):
        print("Building flood_bkk_map.html...")
        with open(HEAD_PATH, "r", encoding="utf-8") as f:
            head = f.read()
        with open(DATA_PATH, "r", encoding="utf-8") as f:
            data_content = f.read()
        with open(FOOT_PATH, "r", encoding="utf-8") as f:
            foot = f.read()
            
        snapshot = None
        # Merge live data in-memory if available
        if os.path.exists(SNAPSHOT_PATH):
            print(f"Found live snapshot at: {SNAPSHOT_PATH}. Merging live telemetry...")
            try:
                with open(SNAPSHOT_PATH, "r", encoding="utf-8") as sf:
                    snapshot = json.load(sf)
                
                # Extract JSON from bkk_data.js
                json_str = data_content.replace('window.BKK=', '').strip().rstrip(';')
                bkk_json = json.loads(json_str)
                
                measurements_map = {int(m['station_id']): m for m in snapshot.get('measurements', [])}
                stations_map = {int(s['station_id']): s for s in snapshot.get('stations', [])}
                code_to_station_id = {s['station_code']: int(s['station_id']) for s in snapshot.get('stations', [])}
                
                existing_codes = set()
                for feature in bkk_json.get('waterlevel', {}).get('features', []):
                    props = feature.get('properties', {})
                    code = props.get('code')
                    if code:
                        existing_codes.add(code)
                        station_id = code_to_station_id.get(code)
                        if station_id is not None:
                            station = stations_map.get(station_id, {})
                            measurement = measurements_map.get(station_id, {})
                            # Merge live values
                            props['station_id'] = station_id
                            props['river'] = station.get('river_name_th')
                            props['wl_in'] = measurement.get('water_levels_m_msl', {}).get('wl_in')
                            props['wl_out'] = measurement.get('water_levels_m_msl', {}).get('wl_out01')
                            props['warning_in'] = station.get('thresholds', {}).get('warning_in_m_msl')
                            props['critical_in'] = station.get('thresholds', {}).get('critical_in_m_msl')
                            props['status'] = measurement.get('status', {}).get('alert_level')
                            props['observed_at'] = measurement.get('observed_at_th')
                            props['left_bank'] = station.get('levels', {}).get('left_bank_m_msl')
                            props['right_bank'] = station.get('levels', {}).get('right_bank_m_msl')
                            props['daily_max'] = measurement.get('daily_max_m_msl', {}).get('max_in_day')
                            props['daily_max_yst'] = measurement.get('daily_max_m_msl', {}).get('max_in_yesterday')
                
                # Append any new stations from snapshot not in existing
                for station in snapshot.get('stations', []):
                    code = station.get('station_code')
                    if code and code not in existing_codes:
                        station_id = int(station['station_id'])
                        measurement = measurements_map.get(station_id, {})
                        new_feature = {
                            "type": "Feature",
                            "geometry": {
                                "type": "Point",
                                "coordinates": [station['location']['longitude'], station['location']['latitude']]
                            },
                            "properties": {
                                "name": station.get('station_name_th'),
                                "code": code,
                                "district": station.get('district_name_th'),
                                "river": station.get('river_name_th'),
                                "station_id": station_id,
                                "wl_in": measurement.get('water_levels_m_msl', {}).get('wl_in'),
                                "wl_out": measurement.get('water_levels_m_msl', {}).get('wl_out01'),
                                "warning_in": station.get('thresholds', {}).get('warning_in_m_msl'),
                                "critical_in": station.get('thresholds', {}).get('critical_in_m_msl'),
                                "status": measurement.get('status', {}).get('alert_level'),
                                "observed_at": measurement.get('observed_at_th'),
                                "left_bank": station.get('levels', {}).get('left_bank_m_msl'),
                                "right_bank": station.get('levels', {}).get('right_bank_m_msl'),
                                "daily_max": measurement.get('daily_max_m_msl', {}).get('max_in_day'),
                                "daily_max_yst": measurement.get('daily_max_m_msl', {}).get('max_in_yesterday')
                            }
                        }
                        bkk_json['waterlevel']['features'].append(new_feature)
                        existing_codes.add(code)
                
                # Embed water edges (canal-to-station network)
                if os.path.exists(WATER_EDGES_PATH):
                    with open(WATER_EDGES_PATH, 'r', encoding='utf-8') as ef:
                        bkk_json['waterEdges'] = json.load(ef)
                    print(f"Embedded {len(bkk_json['waterEdges'].get('features', []))} water edges")

                # Re-serialize
                data_content = f"window.BKK={json.dumps(bkk_json, ensure_ascii=False)};"
                print(f"Merged live data successfully! Total waterlevel stations: {len(bkk_json['waterlevel']['features'])}")
            except Exception as e:
                print(f"Warning: Failed to merge live telemetry: {e}")
        else:
            print("No live snapshot found. Proceeding with static bkk_data.js...")

        # Update river_dashboard.html statically
        if snapshot and os.path.exists(DASHBOARD_PATH):
            try:
                print("Updating river_dashboard.html with baked data...")
                with open(DASHBOARD_PATH, "r", encoding="utf-8") as f:
                    dash_content = f.read()
                
                measurements_map = {int(m['station_id']): m for m in snapshot.get('measurements', [])}
                target_rivers = ["แม่น้ำเจ้าพระยา", "คลองแสนแสบ", "คลองเปรมประชากร", "คลองประเวศบุรีรมย์"]
                live_stations = []
                for s in snapshot.get('stations', []):
                    r_name = s.get('river_name_th')
                    if r_name in target_rivers:
                        m = measurements_map.get(int(s['station_id']), {})
                        wl_in = m.get('water_levels_m_msl', {}).get('wl_in', -99)
                        wl_out = m.get('water_levels_m_msl', {}).get('wl_out01', -99)
                        if wl_in is None: wl_in = -99
                        if wl_out is None: wl_out = -99
                        live_stations.append({
                            "id": str(s['station_id']),
                            "name_th": s.get('station_short_name_th') or s.get('station_name_th'),
                            "name_en": s.get('station_short_name_en') or s.get('station_name_en'),
                            "river": r_name,
                            "lat": s['location']['latitude'],
                            "lng": s['location']['longitude'],
                            "wl_in": wl_in,
                            "wl_out": wl_out,
                            "warn": s.get('thresholds', {}).get('warning_in_m_msl') or 1.0,
                            "crit": s.get('thresholds', {}).get('critical_in_m_msl') or 1.5,
                            "pumps": s.get('water_pump_count', 0),
                            "gates": s.get('water_gate_count', 0),
                            "status": m.get('status', {}).get('alert_level') or "Normal"
                        })
                
                # Format as JS array
                js_stations = json.dumps(live_stations, indent=6, ensure_ascii=False)
                pattern = r"const ALL_STATIONS\s*=\s*\[[\s\S]*?\];"
                replacement = f"const ALL_STATIONS = {js_stations};"
                new_dash_content = re.sub(pattern, replacement, dash_content)
                
                # Update header time
                time_pattern = r"document\.getElementById\('updateTime'\)\.textContent\s*=\s*'ข้อมูล ณ [^']*';"
                scraped_at = snapshot.get('metadata', {}).get('scraped_at')
                formatted_time = "ข้อมูล ณ ล่าสุด"
                if scraped_at:
                    try:
                        # Use isoformat parse
                        dt = datetime.fromisoformat(scraped_at.replace('Z', '+00:00'))
                        local_time_str = dt.strftime('%d/%m/%Y %H:%M')
                        parts = local_time_str.split('/')
                        parts[2] = str(int(parts[2].split()[0]) + 543) + local_time_str[local_time_str.find(' '):]
                        formatted_time = f"ข้อมูล ณ {'/'.join(parts)} น."
                    except Exception:
                        formatted_time = f"ข้อมูล ณ {scraped_at}"
                elif snapshot.get('measurements') and snapshot['measurements'][0].get('observed_at_th'):
                    formatted_time = f"ข้อมูล ณ {snapshot['measurements'][0]['observed_at_th']} น."
                    
                time_replacement = f"document.getElementById('updateTime').textContent = '{formatted_time}';"
                new_dash_content = re.sub(time_pattern, time_replacement, new_dash_content)
                
                with open(DASHBOARD_PATH, "w", encoding="utf-8") as f:
                    f.write(new_dash_content)
                print("Successfully updated river_dashboard.html statically.")
            except Exception as e:
                print(f"Warning: Failed to update river_dashboard.html: {e}")

        # Combine files
        # _head.html ends with <script>, then we add data, then separator, then footer JS
        combined = head.strip() + "\n" + data_content.strip() + "\n/*DATA*/\n" + foot
        
        with open(MAP_PATH, "w", encoding="utf-8") as f:
            f.write(combined)
        print(f"Build completed successfully! flood_bkk_map.html has been updated.")
    else:
        print("Error: Missing required files (_head.html, bkk_data.js, or _foot.html)")

if __name__ == "__main__":
    main()
