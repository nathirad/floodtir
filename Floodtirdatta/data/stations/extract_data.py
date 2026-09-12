import json
import re
import csv
from datetime import datetime

def parse_date(date_str):
    if not date_str:
        return ""
    match = re.search(r'/Date\((\d+)\)/', date_str)
    if match:
        timestamp_ms = int(match.group(1))
        try:
            return datetime.fromtimestamp(timestamp_ms / 1000.0).strftime('%Y-%m-%d %H:%M:%S')
        except Exception:
            return str(timestamp_ms)
    return str(date_str)

with open("data.json", "r", encoding="utf-8") as f:
    data = json.load(f)

water_stations = data.get("waterStation", [])
cleaned_stations = []

for idx, station in enumerate(water_stations):
    info = station.get("water_station_info") or {}
    level_last = station.get("water_level_last") or {}
    gate_last = station.get("water_gate_last") or {}
    pump_last = station.get("water_pump_last") or {}
    
    # Active pumps counting
    active_pumps = 0
    pump_details = []
    for k, v in pump_last.items():
        if k.startswith("pump") and v is True:
            active_pumps += 1
            pump_details.append(k)
            
    # Gate details
    gate_details = []
    for k, v in gate_last.items():
        if k.startswith("watergate") and v is not None:
            gate_details.append(f"{k}:{v}")
            
    station_id = station.get("water_id") or info.get("water_id")
    station_name = station.get("station_name") or info.get("water_name") or info.get("water_shortname")
    station_name_en = station.get("station_name_en") or info.get("water_shortname_en")
    
    wl_in = level_last.get("wl_in")
    wl_out = level_last.get("wl_out01")
    wl_out2 = level_last.get("wl_out02")
    
    latitude = info.get("latitude")
    longitude = info.get("longitude")
    
    warning_in = info.get("warning")
    critical_in = info.get("critical")
    warning_out = info.get("warning_out01")
    critical_out = info.get("critical_out01")
    
    timestamp = parse_date(level_last.get("site_timestamp"))
    update_time = parse_date(level_last.get("update_timestamp"))
    
    # Status calculations
    status = "Normal"
    # If wl_in exceeds critical_in, it is critical
    if wl_in is not None and critical_in is not None and wl_in >= critical_in:
        status = "Critical"
    elif wl_in is not None and warning_in is not None and wl_in >= warning_in:
        status = "Warning"
        
    cleaned_stations.append({
        "id": station_id,
        "name_th": station_name,
        "name_en": station_name_en,
        "district_id": info.get("district_id"),
        "river_name": info.get("river_name"),
        "latitude": latitude,
        "longitude": longitude,
        "timestamp": timestamp,
        "update_timestamp": update_time,
        "wl_in": wl_in,
        "wl_out": wl_out,
        "wl_out2": wl_out2,
        "warning_in": warning_in,
        "critical_in": critical_in,
        "warning_out": warning_out,
        "critical_out": critical_out,
        "pump_count_total": info.get("pump_count"),
        "pump_count_active": active_pumps,
        "active_pumps": ",".join(pump_details),
        "gate_count_total": info.get("water_gate_count"),
        "gates_status": ",".join(gate_details),
        "status": status
    })

# Write to JSON
with open("cleaned_stations.json", "w", encoding="utf-8") as f:
    json.dump(cleaned_stations, f, indent=2, ensure_ascii=False)

# Write to CSV
fields = [
    "id", "name_th", "name_en", "river_name", "latitude", "longitude", 
    "timestamp", "wl_in", "wl_out", "warning_in", "critical_in", 
    "pump_count_total", "pump_count_active", "gate_count_total", "status"
]
with open("cleaned_stations.csv", "w", newline="", encoding="utf-8-sig") as f:
    writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(cleaned_stations)

print(f"Successfully processed {len(cleaned_stations)} stations.")
print("Saved to cleaned_stations.json and cleaned_stations.csv")
