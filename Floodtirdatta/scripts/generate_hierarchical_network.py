import json
import os
import math

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
DATA_DIR = os.path.join(ROOT, "data", "geojson")

CANALS_PATH = os.path.join(DATA_DIR, "canals.geojson")
PUMPS_PATH = os.path.join(DATA_DIR, "pumpstations.geojson")
SUMPS_PATH = os.path.join(DATA_DIR, "sumps.geojson")
GATES_PATH = os.path.join(DATA_DIR, "floodgates.geojson")
WL_PATH = os.path.join(DATA_DIR, "waterlevel.geojson")


def distance(pt1, pt2):
    return math.hypot(pt1[0] - pt2[0], pt1[1] - pt2[1])


def main():
    print("Loading datasets...")
    # Load canals
    with open(CANALS_PATH, "r", encoding="utf-8") as f:
        canals = json.load(f)
    # Load pumps
    with open(PUMPS_PATH, "r", encoding="utf-8") as f:
        pumps = json.load(f)
    # Load sumps
    with open(SUMPS_PATH, "r", encoding="utf-8") as f:
        sumps = json.load(f)
    # Load gates
    with open(GATES_PATH, "r", encoding="utf-8") as f:
        gates = json.load(f)
    # Load waterlevel
    with open(WL_PATH, "r", encoding="utf-8") as f:
        waterlevels = json.load(f)

    # 1. Process Edges and extract unique Nodes
    nodes_map = {}  # (lon_round, lat_round) -> { id, coords, degree, district, subdistrict }
    edges = []

    def get_node_id(lon, lat):
        lon_r = round(lon, 5)
        lat_r = round(lat, 5)
        key = (lon_r, lat_r)
        if key not in nodes_map:
            nid = f"N_{len(nodes_map)}"
            nodes_map[key] = {
                "id": nid,
                "coordinates": [lon_r, lat_r],
                "degree": 0,
                "districts": set(),
                "subdistricts": set(),
            }
        return nodes_map[key]["id"], key

    for idx, feat in enumerate(canals["features"]):
        geom = feat["geometry"]
        props = feat["properties"]
        coords = geom["coordinates"]
        is_multi = geom["type"] == "MultiLineString"
        line = coords[0] if is_multi else coords

        if len(line) < 2:
            continue

        start_pt = line[0]
        end_pt = line[-1]

        s_id, s_key = get_node_id(start_pt[0], start_pt[1])
        t_id, t_key = get_node_id(end_pt[0], end_pt[1])

        nodes_map[s_key]["degree"] += 1
        nodes_map[t_key]["degree"] += 1

        district = (props.get("district_t") or "Unknown").strip()
        subdistrict = str(props.get("subdistrict_id") or "Unknown").strip()

        if district and district != "Unknown":
            nodes_map[s_key]["districts"].add(district)
            nodes_map[t_key]["districts"].add(district)
        if subdistrict and subdistrict != "Unknown":
            nodes_map[s_key]["subdistricts"].add(subdistrict)
            nodes_map[t_key]["subdistricts"].add(subdistrict)

        # Edge details
        edges.append(
            {
                "id": f"E_{idx}",
                "name": props.get("canal_name") or "ไม่มีชื่อ",
                "source": s_id,
                "target": t_id,
                "canal_type": props.get("canal_type") or "Secondary",
                "canal_width": props.get("canal_width"),
                "canal_depth": props.get("canal_depth"),
                "district": district,
                "subdistrict": subdistrict,
                "geometry": geom,
            }
        )

    # Prepare node records
    node_records = []
    for key, val in nodes_map.items():
        val["districts"] = list(val["districts"])
        val["subdistricts"] = list(val["subdistricts"])
        # Primary district/subdistrict
        val["district"] = val["districts"][0] if val["districts"] else "Unknown"
        val["subdistrict"] = val["subdistricts"][0] if val["subdistricts"] else "Unknown"
        val["node_type"] = "intersection" if val["degree"] > 2 else "endpoint"
        # remove sets
        del val["districts"]
        del val["subdistricts"]
        node_records.append(val)

    # Helper function to find nearest node to a coordinate pair
    # Always links to nearest node within 500m (~0.005 degrees)
    def find_nearest_node(lon, lat):
        min_d = Infinity
        nearest_id = None
        for n in node_records:
            d = distance([lon, lat], n["coordinates"])
            if d < min_d:
                min_d = d
                nearest_id = n["id"]
        if min_d < 0.005:
            return nearest_id
        return None

    # 2. Process POIs
    pois = []

    # Pumpstations
    for idx, feat in enumerate(pumps["features"]):
        geom = feat["geometry"]
        props = feat["properties"]
        coords = geom["coordinates"]
        lon, lat = coords[0], coords[1]
        linked = find_nearest_node(lon, lat)

        pois.append(
            {
                "id": f"POI_PUMP_{idx}",
                "name": props.get("pump_name") or "สถานีสูบน้ำ",
                "poi_type": "pump_station",
                "coordinates": [lon, lat],
                "linked_node": linked,
                "district": (props.get("district_t") or "Unknown").strip(),
                "subdistrict": str(props.get("subdistrict_id") or "Unknown").strip(),
                "capacity": props.get("rate"),  # pump capacity
            }
        )

    # Sumps
    for idx, feat in enumerate(sumps["features"]):
        geom = feat["geometry"]
        props = feat["properties"]
        coords = geom["coordinates"]
        lon, lat = coords[0], coords[1]
        linked = find_nearest_node(lon, lat)

        pois.append(
            {
                "id": f"POI_SUMP_{idx}",
                "name": props.get("sump_name") or "บ่อสูบน้ำ",
                "poi_type": "sump",
                "coordinates": [lon, lat],
                "linked_node": linked,
                "district": (props.get("district_t") or "Unknown").strip(),
                "subdistrict": str(props.get("subdistrict_id") or "Unknown").strip(),
                "capacity": props.get("volume"),
            }
        )

    # Floodgates
    for idx, feat in enumerate(gates["features"]):
        geom = feat["geometry"]
        props = feat["properties"]
        coords = geom["coordinates"]
        lon, lat = coords[0], coords[1]
        linked = find_nearest_node(lon, lat)

        pois.append(
            {
                "id": f"POI_GATE_{idx}",
                "name": props.get("gate_name") or "ประตูระบายน้ำ",
                "poi_type": "floodgate",
                "coordinates": [lon, lat],
                "linked_node": linked,
                "district": (props.get("district_t") or "Unknown").strip(),
                "subdistrict": str(props.get("subdistrict_id") or "Unknown").strip(),
                "capacity": props.get("size"),
            }
        )

    # Waterlevel
    for idx, feat in enumerate(waterlevels["features"]):
        geom = feat["geometry"]
        props = feat["properties"]
        coords = geom["coordinates"]
        lon, lat = coords[0], coords[1]
        linked = find_nearest_node(lon, lat)

        pois.append(
            {
                "id": f"POI_WL_{idx}",
                "name": props.get("name") or "สถานีวัดระดับน้ำ",
                "poi_type": "water_level",
                "coordinates": [lon, lat],
                "linked_node": linked,
                "district": (props.get("district") or "Unknown").strip(),
                "subdistrict": "Unknown",
                "capacity": props.get("wl_in"),
            }
        )

    # 3. Build the hierarchical index (จังหวัด -> เขต -> แขวง)
    hierarchy = {"province": "กรุงเทพมหานคร", "districts": {}}

    def ensure_path(d_name, s_name):
        d_map = hierarchy["districts"].setdefault(d_name, {"subdistricts": {}})
        s_map = d_map["subdistricts"].setdefault(s_name, {"nodes": [], "edges": [], "pois": []})
        return s_map

    # Classify Edges
    for e in edges:
        s_map = ensure_path(e["district"], e["subdistrict"])
        s_map["edges"].append(e)

    # Classify Nodes
    for n in node_records:
        s_map = ensure_path(n["district"], n["subdistrict"])
        s_map["nodes"].append(n)

    # Classify POIs
    for p in pois:
        s_map = ensure_path(p["district"], p["subdistrict"])
        s_map["pois"].append(p)

    output_path = os.path.join(DATA_DIR, "hierarchical_network.json")
    print(f"Saving to {output_path}...")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(hierarchy, f, ensure_ascii=False, indent=2)

    print("Process complete!")


if __name__ == "__main__":
    Infinity = float("inf")
    main()
