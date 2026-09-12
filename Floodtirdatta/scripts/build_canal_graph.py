"""
build_canal_graph.py
Builds graph_data.js and canal_graph.html with proper node/edge model:
  - Nodes: canal junctions + gate/pump/sump/waterlevel POIs
  - Edges: canal segments (with live water level from snapshot)
"""
import json
import os
import math

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
DATA_DIR = os.path.join(ROOT, "data", "geojson")
SNAPSHOT_PATH = os.path.join(ROOT, "water-data", "water_latest_snapshot.json")
GRAPH_JS_PATH = os.path.join(HERE, "graph_data.js")
CANAL_GRAPH_HTML = os.path.join(ROOT, "canal_graph.html")


def distance(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    print("Loading data...")
    canals = load_json(os.path.join(DATA_DIR, "canals.geojson"))
    gates = load_json(os.path.join(DATA_DIR, "floodgates.geojson"))
    pumps = load_json(os.path.join(DATA_DIR, "pumpstations.geojson"))
    sumps = load_json(os.path.join(DATA_DIR, "sumps.geojson"))
    wl_geo = load_json(os.path.join(DATA_DIR, "waterlevel.geojson"))

    # Load live snapshot if available
    snap_wl = {}  # code -> {wl_in, status, warning_in, critical_in, river, left_bank, right_bank, daily_max}
    if os.path.exists(SNAPSHOT_PATH):
        snap = load_json(SNAPSHOT_PATH)
        mm = {m["station_id"]: m for m in snap.get("measurements", [])}
        c2id = {s["station_code"]: s["station_id"] for s in snap.get("stations", [])}
        for s in snap.get("stations", []):
            sid = s["station_id"]
            m = mm.get(sid, {})
            snap_wl[s["station_code"]] = {
                "wl_in": m.get("water_levels_m_msl", {}).get("wl_in"),
                "wl_out": m.get("water_levels_m_msl", {}).get("wl_out01"),
                "status": m.get("status", {}).get("alert_level"),
                "warning_in": s.get("thresholds", {}).get("warning_in_m_msl"),
                "critical_in": s.get("thresholds", {}).get("critical_in_m_msl"),
                "river": s.get("river_name_th"),
                "left_bank": s.get("levels", {}).get("left_bank_m_msl"),
                "right_bank": s.get("levels", {}).get("right_bank_m_msl"),
                "daily_max": m.get("daily_max_m_msl", {}).get("max_in_day"),
            }
        print(f"  Loaded {len(snap_wl)} live water level records")
    else:
        print("  No snapshot found — graph will have no live water level data")

    # ── 1. Build nodes from canal endpoints ──────────────────────────────────
    nodes_map = {}  # (lon_r, lat_r) -> node dict

    def get_or_create_node(lon, lat, district=""):
        key = (round(lon, 5), round(lat, 5))
        if key not in nodes_map:
            nodes_map[key] = {
                "id": f"N_{len(nodes_map)}",
                "type": "junction",
                "pt": list(key),
                "degree": 0,
                "district": district,
            }
        return nodes_map[key]

    edges = []
    for i, feat in enumerate(canals["features"]):
        geom = feat["geometry"]
        props = feat["properties"]
        coords = geom["coordinates"]
        line = coords[0] if geom["type"] == "MultiLineString" else coords
        if len(line) < 2:
            continue

        s_node = get_or_create_node(line[0][0], line[0][1], (props.get("district_t") or "").strip())
        t_node = get_or_create_node(line[-1][0], line[-1][1], (props.get("district_t") or "").strip())
        if s_node["id"] == t_node["id"]:
            continue
        s_node["degree"] += 1
        t_node["degree"] += 1

        edges.append({
            "id": f"E_{i}",
            "s": s_node["id"],
            "t": t_node["id"],
            "name": props.get("canal_name") or "ไม่มีชื่อ",
            "canal_type": props.get("canal_type") or "Secondary",
            "canal_width": props.get("canal_width"),
            "canal_depth": props.get("canal_depth"),
            "to_canal": props.get("to_canal"),
            "district": (props.get("district_t") or "").strip(),
        })

    node_list = list(nodes_map.values())
    # Mark intersections
    for n in node_list:
        n["node_type"] = "intersection" if n["degree"] > 2 else "endpoint"

    print(f"  Canal junctions: {len(node_list)}")
    print(f"  Canal edges: {len(edges)}")

    # ── 2. Snap POIs to nearest junction node ────────────────────────────────
    SNAP_DEG = 0.005  # ~550m
    GRID_SIZE = 0.01

    # Build spatial grid for O(1) query
    from collections import defaultdict
    spatial_grid = defaultdict(list)
    for n in node_list:
        lon, lat = n["pt"]
        grid_key = (math.floor(lon / GRID_SIZE), math.floor(lat / GRID_SIZE))
        spatial_grid[grid_key].append(n)

    def snap_to_nearest(lon, lat):
        target_key_x = math.floor(lon / GRID_SIZE)
        target_key_y = math.floor(lat / GRID_SIZE)
        
        best_id = None
        best_d = float("inf")
        
        # Check 3x3 cells enclosing target
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                key = (target_key_x + dx, target_key_y + dy)
                for n in spatial_grid.get(key, []):
                    d = distance([lon, lat], n["pt"])
                    if d < best_d:
                        best_d = d
                        best_id = n["id"]
        return best_id if best_d < SNAP_DEG else None

    poi_nodes = []

    # Floodgates
    for i, feat in enumerate(gates["features"]):
        p = feat["properties"]
        c = feat["geometry"]["coordinates"]
        linked = snap_to_nearest(c[0], c[1])
        poi_nodes.append({
            "id": f"POI_GATE_{i}",
            "type": "gate",
            "pt": [round(c[0], 5), round(c[1], 5)],
            "name": p.get("gate_name") or "ประตูระบายน้ำ",
            "district": (p.get("district_t") or "").strip(),
            "linked": linked,
        })

    # Pump stations
    for i, feat in enumerate(pumps["features"]):
        p = feat["properties"]
        c = feat["geometry"]["coordinates"]
        linked = snap_to_nearest(c[0], c[1])
        poi_nodes.append({
            "id": f"POI_PUMP_{i}",
            "type": "pump",
            "pt": [round(c[0], 5), round(c[1], 5)],
            "name": p.get("pump_name") or "สถานีสูบน้ำ",
            "district": (p.get("district_t") or "").strip(),
            "capacity": p.get("rate"),
            "linked": linked,
        })

    # Sumps
    for i, feat in enumerate(sumps["features"]):
        p = feat["properties"]
        c = feat["geometry"]["coordinates"]
        linked = snap_to_nearest(c[0], c[1])
        poi_nodes.append({
            "id": f"POI_SUMP_{i}",
            "type": "sump",
            "pt": [round(c[0], 5), round(c[1], 5)],
            "name": p.get("sump_name") or "บ่อสูบน้ำ",
            "district": (p.get("district_t") or "").strip(),
            "linked": linked,
        })

    # Water level stations
    for i, feat in enumerate(wl_geo["features"]):
        p = feat["properties"]
        c = feat["geometry"]["coordinates"]
        linked = snap_to_nearest(c[0], c[1])
        code = p.get("code", "")
        live = snap_wl.get(code, {})
        poi_nodes.append({
            "id": f"POI_WL_{i}",
            "type": "waterlevel",
            "pt": [round(c[0], 5), round(c[1], 5)],
            "name": p.get("name") or "สถานีวัดระดับน้ำ",
            "code": code,
            "district": (p.get("district") or "").strip(),
            "river": live.get("river") or p.get("river", ""),
            "wl_in": live.get("wl_in"),
            "wl_out": live.get("wl_out"),
            "status": live.get("status"),
            "warning_in": live.get("warning_in"),
            "critical_in": live.get("critical_in"),
            "left_bank": live.get("left_bank"),
            "right_bank": live.get("right_bank"),
            "daily_max": live.get("daily_max"),
            "linked": linked,
        })

    linked_count = sum(1 for p in poi_nodes if p["linked"])
    print(f"  POI nodes: {len(poi_nodes)} ({linked_count} linked to canal junctions)")

    # ── 3. Write graph_data.js ───────────────────────────────────────────────
    # Compile adjacency list
    adjacency = {}
    for e in edges:
        adjacency.setdefault(e["s"], []).append(e["t"])

    # Compile spatial grid with string keys
    serialized_grid = {}
    for key, val in spatial_grid.items():
        key_str = f"{key[0]},{key[1]}"
        serialized_grid[key_str] = [n["id"] for n in val]

    graph = {
        "nodes": node_list,
        "poi_nodes": poi_nodes,
        "edges": edges,
        "adjacency": adjacency,
        "spatial_grid": serialized_grid,
    }
    js = "window.GRAPH=" + json.dumps(graph, ensure_ascii=False, separators=(",", ":")) + ";"
    with open(GRAPH_JS_PATH, "w", encoding="utf-8") as f:
        f.write(js)
    print(f"Wrote {GRAPH_JS_PATH}")

    # ── 4. Build canal_graph.html ────────────────────────────────────────────
    build_canal_graph_html(node_list, poi_nodes, edges)
    print(f"Wrote {CANAL_GRAPH_HTML}")
    print("Done!")


def build_canal_graph_html(nodes, poi_nodes, edges):
    # Compute bounding box for geographic projection
    all_pts = [n["pt"] for n in nodes] + [p["pt"] for p in poi_nodes]
    min_lon = min(p[0] for p in all_pts)
    max_lon = max(p[0] for p in all_pts)
    min_lat = min(p[1] for p in all_pts)
    max_lat = max(p[1] for p in all_pts)

    graph_json = json.dumps(
        {"nodes": nodes, "poi_nodes": poi_nodes, "edges": edges},
        ensure_ascii=False, separators=(",", ":")
    )

    html = f"""<!DOCTYPE html><html lang="th"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Floodtir — Canal Network Graph</title>
<script src="https://unpkg.com/d3@7/dist/d3.min.js"></script>
<style>
:root{{--bg:#0b0f17;--panel:#111827;--line:#1f2937;--text:#e5e7eb;--muted:#6b7280;
--cyan:#39c5cf;--safe:#2ea043;--warn:#d29922;--danger:#da3633;--purple:#a371f7;--orange:#ff9f1c;--pink:#f778ba}}
*{{box-sizing:border-box}}html,body{{margin:0;height:100%;background:var(--bg);color:var(--text);
font-family:system-ui,"Segoe UI",Tahoma,sans-serif;overflow:hidden}}
#wrap{{display:flex;height:100%}}
#cv{{flex:1;cursor:move}}
#side{{width:300px;background:var(--panel);border-left:1px solid var(--line);padding:14px;overflow:auto;flex-shrink:0}}
h1{{font-size:15px;margin:0 0 2px}}.sub{{color:var(--muted);font-size:11px;margin-bottom:10px;line-height:1.5}}
.card{{background:#0b0f17;border:1px solid var(--line);border-radius:8px;padding:10px 12px;margin-bottom:10px}}
.card h3{{margin:0 0 8px;font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.5px}}
.row{{display:flex;align-items:center;gap:7px;font-size:12px;padding:2px 0}}
.dot{{width:10px;height:10px;border-radius:50%;display:inline-block;flex:none}}
.bar{{width:14px;height:0;border-top:3px solid;display:inline-block;flex:none}}
input[type=text]{{width:100%;background:#0b0f17;border:1px solid var(--line);color:var(--text);border-radius:6px;padding:5px 8px;font-size:12px}}
label.chk{{display:flex;align-items:center;gap:7px;font-size:12px;padding:2px 0;cursor:pointer}}
#info{{font-size:12px;line-height:1.6;color:var(--text)}}
#info b{{color:#fff}}
#tt{{position:fixed;display:none;background:#0b0f17;border:1px solid var(--line);border-radius:6px;
padding:6px 10px;font-size:11.5px;pointer-events:none;z-index:99;max-width:220px;line-height:1.5}}
.stat{{font-size:18px;font-weight:700}}.statlbl{{font-size:10px;color:var(--muted)}}
.statgrid{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:6px;text-align:center}}
.hint{{position:absolute;left:10px;bottom:10px;font-size:10.5px;color:var(--muted);
background:rgba(11,15,23,.8);padding:3px 8px;border-radius:5px;pointer-events:none}}
</style></head><body>
<div id="wrap">
<svg id="cv"></svg>
<div id="side">
<h1>🌊 Canal Network</h1>
<div class="sub">คลอง = เส้น (Edge) · จุดตัด/สถานี = โหนด (Node)<br>สีตามสถานะระดับน้ำจริง</div>
<div class="card"><h3>สถิติ</h3>
<div class="statgrid">
<div><div class="stat" id="s-junctions">-</div><div class="statlbl">Junctions</div></div>
<div><div class="stat" id="s-edges">-</div><div class="statlbl">Canals</div></div>
<div><div class="stat" id="s-pois">-</div><div class="statlbl">Facilities</div></div>
</div></div>
<div class="card"><h3>ค้นหา</h3>
<input id="q" type="text" placeholder="ชื่อคลอง / สถานี..."/>
</div>
<div class="card"><h3>แสดงชั้นข้อมูล</h3>
<label class="chk"><input type="checkbox" id="show-junctions" checked/><span class="dot" style="background:#374151;border:1px solid #6b7280"></span>จุดตัดคลอง</label>
<label class="chk"><input type="checkbox" id="show-gates" checked/><span class="dot" style="background:var(--purple)"></span>ประตูระบายน้ำ</label>
<label class="chk"><input type="checkbox" id="show-pumps" checked/><span class="dot" style="background:var(--orange)"></span>สถานีสูบน้ำ</label>
<label class="chk"><input type="checkbox" id="show-sumps" checked/><span class="dot" style="background:var(--pink)"></span>บ่อสูบน้ำ</label>
<label class="chk"><input type="checkbox" id="show-wl" checked/><span class="dot" style="background:var(--cyan)"></span>สถานีวัดระดับน้ำ</label>
</div>
<div class="card"><h3>สีคลอง</h3>
<label class="chk"><input type="radio" name="ecolor" value="type" checked/>ลำดับชั้น (Main/Secondary)</label>
<label class="chk"><input type="radio" name="ecolor" value="status"/>สถานะระดับน้ำ</label>
</div>
<div class="card"><h3>รายละเอียด</h3><div id="info"><span style="color:var(--muted)">คลิกที่โหนดหรือเส้นเพื่อดูข้อมูล</span></div></div>
<div class="card"><h3>สัญลักษณ์</h3>
<div class="row"><span class="bar" style="border-color:var(--cyan)"></span>คลองหลัก (Main)</div>
<div class="row"><span class="bar" style="border-color:#0e7490"></span>คลองรอง (Secondary)</div>
<div class="row"><span class="bar" style="border-color:var(--safe)"></span>ระดับน้ำปกติ</div>
<div class="row"><span class="bar" style="border-color:var(--warn)"></span>เฝ้าระวัง</div>
<div class="row"><span class="bar" style="border-color:var(--danger)"></span>วิกฤต</div>
<div class="row"><span class="bar" style="border-color:#374151"></span>ออฟไลน์/ไม่มีข้อมูล</div>
</div>
</div></div>
<div id="tt"></div>
<div class="hint">เลื่อน = แพน · สกรอลล์ = ซูม · คลิก = รายละเอียด</div>
<script>
const G=window.GRAPH={graph_json};
const W=document.getElementById('cv');

// Stats
document.getElementById('s-junctions').textContent=G.nodes.filter(n=>n.node_type==='intersection').length.toLocaleString();
document.getElementById('s-edges').textContent=G.edges.length.toLocaleString();
document.getElementById('s-pois').textContent=G.poi_nodes.length.toLocaleString();

// Geographic projection
const BKK_BOUNDS={{minLon:{min_lon:.5f},maxLon:{max_lon:.5f},minLat:{min_lat:.5f},maxLat:{max_lat:.5f}}};
const PAD=40;

function makeScales(W,H){{
  const xS=d3.scaleLinear().domain([BKK_BOUNDS.minLon,BKK_BOUNDS.maxLon]).range([PAD,W-PAD]);
  const yS=d3.scaleLinear().domain([BKK_BOUNDS.minLat,BKK_BOUNDS.maxLat]).range([H-PAD,PAD]);
  return {{x:xS,y:yS}};
}}

const svg=d3.select('#cv');
let {{width:W0,height:H0}}=W.getBoundingClientRect();
svg.attr('width',W0).attr('height',H0);
let sc=makeScales(W0,H0);

// Node lookup
const nodeById={{}};
G.nodes.forEach(n=>nodeById[n.id]=n);

// SVG layers
const g=svg.append('g');
const edgeLayer=g.append('g').attr('class','edges');
const junctionLayer=g.append('g').attr('class','junctions');
const poiLayer=g.append('g').attr('class','pois');

// Color helpers
const C={{
  get:v=>getComputedStyle(document.documentElement).getPropertyValue(v).trim(),
  edge(e,mode){{
    if(mode==='status'){{
      const wl=nearestWL(e);
      if(!wl) return '#374151';
      const s=wl.status;
      if(s==='critical') return C.get('--danger');
      if(s==='warning') return C.get('--warn');
      if(s==='normal') return C.get('--safe');
      return '#374151';
    }}
    return e.canal_type==='Main'?C.get('--cyan'):'#0e7490';
  }},
  poi(type){{
    if(type==='gate') return C.get('--purple');
    if(type==='pump') return C.get('--orange');
    if(type==='sump') return C.get('--pink');
    if(type==='waterlevel') return C.get('--cyan');
    return '#6b7280';
  }},
  status(s){{
    if(s==='critical') return C.get('--danger');
    if(s==='warning') return C.get('--warn');
    if(s==='normal') return C.get('--safe');
    return '#6b7280';
  }}
}};

// Build WL lookup by nearest to edge midpoint
const wlPois=G.poi_nodes.filter(p=>p.type==='waterlevel'&&p.wl_in!=null);
function nearestWL(edge){{
  const sn=nodeById[edge.s];
  const tn=nodeById[edge.t];
  if(!sn||!tn) return null;
  const mx=(sn.pt[0]+tn.pt[0])/2, my=(sn.pt[1]+tn.pt[1])/2;
  let best=null, bd=Infinity;
  wlPois.forEach(p=>{{
    const d=Math.hypot(p.pt[0]-mx,p.pt[1]-my);
    if(d<bd){{bd=d;best=p;}}
  }});
  return bd<0.05?best:null;
}}

let ecolorMode='type';
document.querySelectorAll('input[name="ecolor"]').forEach(r=>r.addEventListener('change',e=>{{
  ecolorMode=e.target.value;
  edgeLayer.selectAll('line').attr('stroke',d=>C.edge(d,ecolorMode));
}}));

function px(pt){{return sc.x(pt[0]);}}
function py(pt){{return sc.y(pt[1]);}}

function render(){{
  const zoom=currentTransform?currentTransform.k:1;

  // Edges
  const lines=edgeLayer.selectAll('line').data(G.edges,d=>d.id);
  lines.enter().append('line')
    .attr('x1',d=>{{const n=nodeById[d.s];return n?px(n.pt):0;}})
    .attr('y1',d=>{{const n=nodeById[d.s];return n?py(n.pt):0;}})
    .attr('x2',d=>{{const n=nodeById[d.t];return n?px(n.pt):0;}})
    .attr('y2',d=>{{const n=nodeById[d.t];return n?py(n.pt):0;}})
    .attr('stroke',d=>C.edge(d,ecolorMode))
    .attr('stroke-width',d=>d.canal_type==='Main'?1.8:0.8)
    .attr('stroke-opacity',0.75)
    .style('cursor','pointer')
    .on('mouseover',showEdgeTT)
    .on('mousemove',moveTT)
    .on('mouseout',hideTT)
    .on('click',clickEdge)
    .merge(lines);
  lines.exit().remove();

  // Junctions (only intersections, visible at zoom > 2)
  const showJ=document.getElementById('show-junctions').checked;
  const jData=showJ&&zoom>1.5?G.nodes.filter(n=>n.node_type==='intersection'):[];
  const jCircles=junctionLayer.selectAll('circle').data(jData,d=>d.id);
  jCircles.enter().append('circle')
    .attr('r',2)
    .attr('fill','#374151')
    .attr('stroke','#6b7280')
    .attr('stroke-width',0.5)
    .merge(jCircles)
    .attr('cx',d=>px(d.pt))
    .attr('cy',d=>py(d.pt));
  jCircles.exit().remove();

  // POI nodes
  const showTypes={{
    gate:document.getElementById('show-gates').checked,
    pump:document.getElementById('show-pumps').checked,
    sump:document.getElementById('show-sumps').checked,
    waterlevel:document.getElementById('show-wl').checked,
  }};
  const poiData=G.poi_nodes.filter(p=>showTypes[p.type]);
  const poiR=zoom>3?7:zoom>1.5?5:4;
  const poiCircles=poiLayer.selectAll('circle').data(poiData,d=>d.id);
  poiCircles.enter().append('circle')
    .style('cursor','pointer')
    .on('mouseover',showPoiTT)
    .on('mousemove',moveTT)
    .on('mouseout',hideTT)
    .on('click',clickPoi)
    .merge(poiCircles)
    .attr('cx',d=>px(d.pt))
    .attr('cy',d=>py(d.pt))
    .attr('r',d=>d.type==='waterlevel'?poiR+1:poiR)
    .attr('fill',d=>d.type==='waterlevel'&&d.status?C.status(d.status):C.poi(d.type))
    .attr('stroke','#0b0f17')
    .attr('stroke-width',1);
  poiCircles.exit().remove();
}}

// Zoom/pan
let currentTransform=null;
const zoom=d3.zoom().scaleExtent([0.5,40]).on('zoom',e=>{{
  currentTransform=e.transform;
  g.attr('transform',e.transform);
  render();
}});
svg.call(zoom);

// Tooltip
const tt=document.getElementById('tt');
function showEdgeTT(e,d){{
  const wl=nearestWL(d);
  let html=`<b>${{d.name}}</b><br>ประเภท: ${{d.canal_type==='Main'?'คลองหลัก':'คลองรอง'}}<br>เขต: ${{d.district||'-'}}`;
  if(wl){{
    const lvl=wl.wl_in!=null?wl.wl_in.toFixed(2)+' ม.':'ไม่มีข้อมูล';
    const bank=wl.left_bank||wl.right_bank;
    const hr=wl.wl_in!=null&&bank?(bank-wl.wl_in).toFixed(2)+' ม.':'-';
    html+=`<br>ระดับน้ำ: <b>${{lvl}}</b><br>เหลือถึงตลิ่ง: ${{hr}}<br><span style="color:${{C.status(wl.status)}}">${{wl.status||''}}</span>`;
  }}
  tt.innerHTML=html;tt.style.display='block';
}}
function showPoiTT(e,d){{
  const typeTh={{gate:'ประตูระบายน้ำ',pump:'สถานีสูบน้ำ',sump:'บ่อสูบน้ำ',waterlevel:'สถานีวัดระดับน้ำ'}};
  let html=`<b>${{d.name}}</b><br>${{typeTh[d.type]||d.type}}<br>เขต: ${{d.district||'-'}}`;
  if(d.type==='waterlevel'&&d.wl_in!=null){{
    const bank=d.left_bank||d.right_bank;
    const hr=bank?(bank-d.wl_in).toFixed(2)+' ม.':'-';
    html+=`<br>ระดับน้ำ: <b>${{d.wl_in.toFixed(2)}} ม.</b>`;
    if(d.warning_in) html+=`<br>เฝ้าระวัง: ${{d.warning_in}} / วิกฤต: ${{d.critical_in}}`;
    html+=`<br>เหลือถึงตลิ่ง: ${{hr}}`;
    if(d.status) html+=`<br><span style="color:${{C.status(d.status)}}">${{d.status}}</span>`;
  }}
  if(d.capacity!=null) html+=`<br>ความจุ: ${{d.capacity}}`;
  tt.innerHTML=html;tt.style.display='block';
}}
function moveTT(e){{tt.style.left=(e.clientX+14)+'px';tt.style.top=(e.clientY-10)+'px';}}
function hideTT(){{tt.style.display='none';}}

// Click info panel
const typeTh={{gate:'ประตูระบายน้ำ',pump:'สถานีสูบน้ำ',sump:'บ่อสูบน้ำ',waterlevel:'สถานีวัดระดับน้ำ'}};
function clickEdge(e,d){{
  const wl=nearestWL(d);
  let h=`<b>${{d.name}}</b><br>`;
  h+=`ประเภท: ${{d.canal_type==='Main'?'คลองหลัก':'คลองรอง'}}<br>`;
  h+=`เขต: ${{d.district||'-'}}<br>`;
  if(d.canal_width) h+=`กว้าง: ${{d.canal_width}} ม.<br>`;
  if(d.to_canal) h+=`ไหลลง: ${{d.to_canal}}<br>`;
  if(wl){{
    h+=`<hr style="border-color:#1f2937;margin:6px 0">`;
    h+=`<b>สถานีวัด: ${{wl.name}}</b><br>`;
    if(wl.wl_in!=null) h+=`ระดับน้ำ: <b>${{wl.wl_in.toFixed(2)}} ม.</b><br>`;
    const bank=wl.left_bank||wl.right_bank;
    if(wl.wl_in!=null&&bank) h+=`เหลือถึงตลิ่ง: <b>${{(bank-wl.wl_in).toFixed(2)}} ม.</b><br>`;
    if(wl.daily_max!=null) h+=`สูงสุดวันนี้: ${{wl.daily_max.toFixed(2)}} ม.<br>`;
    if(wl.status) h+=`สถานะ: <span style="color:${{C.status(wl.status)}}">${{wl.status}}</span>`;
  }}
  document.getElementById('info').innerHTML=h;
}}
function clickPoi(e,d){{
  let h=`<b>${{d.name}}</b><br>${{typeTh[d.type]||d.type}}<br>เขต: ${{d.district||'-'}}`;
  if(d.type==='waterlevel'){{
    if(d.river) h+=`<br>คลอง: ${{d.river}}`;
    if(d.wl_in!=null) h+=`<br>ระดับน้ำ: <b>${{d.wl_in.toFixed(2)}} ม.</b>`;
    const bank=d.left_bank||d.right_bank;
    if(d.wl_in!=null&&bank) h+=`<br>ตลิ่ง: ${{bank.toFixed(2)}} ม. · เหลือ: <b>${{(bank-d.wl_in).toFixed(2)}} ม.</b>`;
    if(d.warning_in) h+=`<br>เฝ้าระวัง: ${{d.warning_in}} / วิกฤต: ${{d.critical_in}}`;
    if(d.daily_max!=null) h+=`<br>สูงสุดวันนี้: ${{d.daily_max.toFixed(2)}} ม.`;
    if(d.status) h+=`<br>สถานะ: <span style="color:${{C.status(d.status)}}">${{d.status}}</span>`;
  }}
  if(d.capacity!=null) h+=`<br>ความจุ: ${{d.capacity}}`;
  if(d.linked) h+=`<br><span style="color:var(--muted)">เชื่อมกับ junction: ${{d.linked}}</span>`;
  document.getElementById('info').innerHTML=h;
}}

// Search
document.getElementById('q').addEventListener('input',function(){{
  const q=this.value.trim().toLowerCase();
  if(!q){{
    edgeLayer.selectAll('line').attr('stroke-opacity',0.75);
    poiLayer.selectAll('circle').attr('opacity',1);
    return;
  }}
  edgeLayer.selectAll('line').attr('stroke-opacity',d=>d.name.toLowerCase().includes(q)?1:0.08);
  poiLayer.selectAll('circle').attr('opacity',d=>(d.name||'').toLowerCase().includes(q)?1:0.1);
}});

// Layer toggles
['show-junctions','show-gates','show-pumps','show-sumps','show-wl'].forEach(id=>
  document.getElementById(id).addEventListener('change',render));

// Initial render
render();

// Resize
window.addEventListener('resize',()=>{{
  const r=W.getBoundingClientRect();
  svg.attr('width',r.width).attr('height',r.height);
  sc=makeScales(r.width,r.height);
  render();
}});
</script></body></html>"""

    with open(CANAL_GRAPH_HTML, "w", encoding="utf-8") as f:
        f.write(html)


if __name__ == "__main__":
    main()
