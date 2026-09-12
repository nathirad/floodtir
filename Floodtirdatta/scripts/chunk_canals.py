import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
CANALS_GEOJSON = os.path.join(ROOT, "data", "geojson", "canals.geojson")
CHUNKS_DIR = os.path.join(ROOT, "data", "geojson", "canals_chunks")
BKK_DATA_JS = os.path.join(ROOT, "templates", "bkk_data.js")


def get_bbox(coords, is_multi=False):
    lats, lons = [], []
    lines = coords if is_multi else [coords]
    for line in lines:
        for pt in line:
            lons.append(pt[0])
            lats.append(pt[1])
    if not lats or not lons:
        return [0, 0, 0, 0]
    return [min(lats), min(lons), max(lats), max(lons)]


def main():
    if not os.path.exists(CHUNKS_DIR):
        os.makedirs(CHUNKS_DIR)

    print("Loading canals.geojson...")
    with open(CANALS_GEOJSON, "r", encoding="utf-8") as f:
        geojson = json.load(f)

    features = geojson.get("features", [])
    print(f"Loaded {len(features)} canals.")

    # Group by district_t
    by_district = {}
    for feat in features:
        props = feat.get("properties", {})
        district = props.get("district_t") or "Unknown"
        district = district.strip()
        by_district.setdefault(district, []).append(feat)

    # Write chunks and build index
    index = {}
    for idx, (district, feats) in enumerate(by_district.items()):
        chunk_file = f"c{idx}.json"
        chunk_path = os.path.join(CHUNKS_DIR, chunk_file)

        # Calculate bounding box for all features in this district
        min_lats, min_lons, max_lats, max_lons = [], [], [], []
        for feat in feats:
            geom = feat.get("geometry", {})
            coords = geom.get("coordinates", [])
            is_multi = geom.get("type") == "MultiLineString"
            bbox = get_bbox(coords, is_multi)
            min_lats.append(bbox[0])
            min_lons.append(bbox[1])
            max_lats.append(bbox[2])
            max_lons.append(bbox[3])

        district_bbox = [min(min_lats), min(min_lons), max(max_lats), max(max_lons)]

        chunk_data = {"type": "FeatureCollection", "features": feats}

        with open(chunk_path, "w", encoding="utf-8") as f:
            json.dump(chunk_data, f, ensure_ascii=False)

        index[district] = {"bbox": district_bbox, "file": chunk_file}

    # Write index
    index_path = os.path.join(CHUNKS_DIR, "index.json")
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)
    print(f"Created {len(by_district)} chunks and index.json.")

    # Now, modify bkk_data.js to empty the canals features list
    print("Modifying bkk_data.js to reduce initial size...")
    with open(BKK_DATA_JS, "r", encoding="utf-8") as f:
        s = f.read()

    start_idx = s.find("{")
    end_idx = s.rfind("}") + 1
    prefix = s[:start_idx]
    suffix = s[end_idx:]

    bkk_data = json.loads(s[start_idx:end_idx])
    if "canals" in bkk_data:
        bkk_data["canals"]["features"] = []
        print("Emptied canals list in memory.")

    with open(BKK_DATA_JS, "w", encoding="utf-8") as f:
        f.write(prefix + json.dumps(bkk_data, ensure_ascii=False) + suffix)
    print("Saved modified bkk_data.js!")


if __name__ == "__main__":
    main()
