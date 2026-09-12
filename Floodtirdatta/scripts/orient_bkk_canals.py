import json
import os
import math

# Paths
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
BKK_DATA_JS = os.path.join(ROOT, "templates", "bkk_data.js")
DRAINAGE_FLOW_GEOJSON = os.path.join(ROOT, "mapwaterflow", "output", "drainage_flow.geojson")

def distance(p1, p2):
    return math.hypot(p1[0]-p2[0], p1[1]-p2[1])

def main():
    print("Loading data...")
    if not os.path.exists(DRAINAGE_FLOW_GEOJSON):
        print(f"Error: oriented flow file not found at {DRAINAGE_FLOW_GEOJSON}. Please run mapwaterflow/pipeline.py and make_flow.py first.")
        return
        
    with open(BKK_DATA_JS, "r", encoding="utf-8") as f:
        s = f.read()
    
    start_idx = s.find('{')
    end_idx = s.rfind('}') + 1
    prefix = s[:start_idx]
    suffix = s[end_idx:]
    
    bkk_data = json.loads(s[start_idx:end_idx])
    
    with open(DRAINAGE_FLOW_GEOJSON, "r", encoding="utf-8") as f:
        flow_data = json.load(f)
        
    flow_by_name = {}
    for f in flow_data["features"]:
        name = f["properties"].get("canal_name")
        if name:
            flow_by_name.setdefault(name, []).append(f)
            
    reversed_count = 0
    not_matched_count = 0
    matched_count = 0
    
    for canal in bkk_data["canals"]["features"]:
        geom = canal["geometry"]
        if geom["type"] not in ("LineString", "MultiLineString"):
            continue
            
        name = canal["properties"].get("canal_name")
        coords = geom["coordinates"]
        
        is_multi = geom["type"] == "MultiLineString"
        if is_multi:
            line_coords = coords[0]
        else:
            line_coords = coords
            
        if len(line_coords) < 2:
            continue
            
        start_pt = line_coords[0]
        end_pt = line_coords[-1]
        
        candidates = flow_by_name.get(name, [])
        best_candidate = None
        min_dist = float('inf')
        
        for cand in candidates:
            cand_geom = cand["geometry"]
            cand_coords = cand_geom["coordinates"]
            if cand_geom["type"] == "MultiLineString":
                cand_line = cand_coords[0]
            else:
                cand_line = cand_coords
                
            if len(cand_line) < 2:
                continue
                
            d1 = distance(start_pt, cand_line[0]) + distance(end_pt, cand_line[-1])
            d2 = distance(start_pt, cand_line[-1]) + distance(end_pt, cand_line[0])
            d = min(d1, d2)
            if d < min_dist:
                min_dist = d
                should_reverse = d2 < d1
                best_candidate = (cand, should_reverse)
                
        # Matching threshold (degrees distance)
        if best_candidate and min_dist < 0.05:
            matched_count += 1
            cand_feature, should_reverse = best_candidate
            if should_reverse:
                reversed_count += 1
                if is_multi:
                    geom["coordinates"] = [line[::-1] for line in coords]
                else:
                    geom["coordinates"] = coords[::-1]
                canal["properties"]["oriented"] = True
            else:
                canal["properties"]["oriented"] = True
        else:
            not_matched_count += 1
            canal["properties"]["oriented"] = False
            
    print(f"Canals matching finished. Matched: {matched_count}, Reversed: {reversed_count}, Not Matched: {not_matched_count}")
    
    with open(BKK_DATA_JS, "w", encoding="utf-8") as f:
        f.write(prefix + json.dumps(bkk_data, ensure_ascii=False) + suffix)
    print("Saved oriented canals back to bkk_data.js!")

if __name__ == "__main__":
    main()
