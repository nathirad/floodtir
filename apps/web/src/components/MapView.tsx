"use client";

import "leaflet/dist/leaflet.css";
import { useEffect, useRef } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "/api/demo";
const POLL_NODES_MS = 5000;
const POLL_SURFACE_MS = 15000;

interface FloodNode {
  id: number;
  name: string;
  lat: number;
  lon: number;
  district: string;
  current_fused_level: number | null;
  n_reports: number;
  last_updated: string | null;
}

interface SurfacePoint {
  lat: number;
  lon: number;
  level: number;
  dlat: number;
  dlon: number;
}

function levelColor(level: number): string {
  if (level > 1.0) return "#dc2626";
  if (level > 0.7) return "#f97316";
  if (level > 0.5) return "#fbbf24";
  if (level > 0.3) return "#60a5fa";
  return "#bfdbfe";
}

function surfaceOpacity(level: number): number {
  return Math.min(0.55, Math.max(0.05, level / 2.0));
}

interface MapViewProps {
  visibleLayers: Set<string>;
  activeCanalMode: string;
  dangerViewEnabled: boolean;
  onZoomChange?: (zoom: number, level: number) => void;
  onStatsLoaded?: (stats: Record<string, any>) => void;
}

const colors = {
  safe: "#2ea043",
  warn: "#d29922",
  danger: "#da3633",
  accent: "#388bfd",
  purple: "#a371f7",
  cyan: "#39c5cf",
  pink: "#f778ba",
  orange: "#ff9f1c",
  muted: "#8b949e",
  text: "#e6edf3",
};

const ZOOM_MAJOR = 11;
const ZOOM_MAIN = 12;
const ZOOM_DETAIL = 14;

// Helper: escape HTML to prevent XSS in popups
const esc = (s: any) =>
  (s || "")
    .toString()
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");

export default function MapView({
  visibleLayers,
  activeCanalMode,
  dangerViewEnabled,
  onZoomChange,
  onStatsLoaded,
}: MapViewProps) {
  const mapRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<any>(null);
  const LRef = useRef<any>(null);

  // References to data sets and layers
  const BRef = useRef<Record<string, any>>({});
  const GLayersRef = useRef<Record<string, any>>({});
  
  // Chunk loader states
  const loadedChunksRef = useRef<Set<string>>(new Set());
  const dangerChunksLoadedRef = useRef<Set<string>>(new Set());
  const dangerRegistryRef = useRef<Record<string, any>>({});
  const canalIndexRef = useRef<any>(null);
  const currentZoomLevelRef = useRef<number>(1);
  const pipeReqRef = useRef<number>(0);

  // Helper inside component to parse CSS variables dynamically or fallback to values
  const getCol = (colStr: string) => {
    if (colStr.startsWith("--")) {
      const name = colStr.substring(2);
      return (colors as any)[name] || "#ffffff";
    }
    return colStr;
  };

  const getZoomLevel = (z: number) => {
    if (z >= ZOOM_DETAIL) return 4; // all canals + width
    if (z >= ZOOM_MAIN) return 3; // all canals, thin
    if (z >= ZOOM_MAJOR) return 2; // Main canals only
    return 1; // major monitored canals only;
  };

  // 1. Helper function: point in polygon
  const ptInPolygon = (pt: number[], ring: number[][]) => {
    let x = pt[0], y = pt[1];
    let inside = false;
    for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
      let xi = ring[i][0], yi = ring[i][1];
      let xj = ring[j][0], yj = ring[j][1];
      if ((yi > y) !== (yj > y) && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) {
        inside = !inside;
      }
    }
    return inside;
  };

  const ptInGeometry = (pt: number[], geom: any) => {
    if (geom.type === "Polygon") {
      return ptInPolygon(pt, geom.coordinates[0]);
    } else if (geom.type === "MultiPolygon") {
      return geom.coordinates.some((poly: any) => ptInPolygon(pt, poly[0]));
    }
    return false;
  };

  // Helper color mappings
  const floodColor = (p: any) => {
    if (p.device_status && p.device_status !== "normal") return colors.muted;
    const f = p.flood || 0;
    if (f >= 10) return colors.danger;
    if (f > 0) return colors.warn;
    return colors.safe;
  };

  const expoColor = (n: number) => {
    return n >= 5 ? colors.danger : n >= 3 ? colors.warn : n >= 1 ? colors.accent : colors.safe;
  };

  const wlStatusColor = (status: string, fallback: string) => {
    if (status === "critical") return colors.danger;
    if (status === "warning") return colors.warn;
    if (status === "normal") return colors.safe;
    if (status === "offline") return "#4b5563";
    return fallback;
  };

  const riskScoreColor = (s: number) => {
    return s >= 0.7 ? colors.danger : s >= 0.4 ? colors.warn : colors.safe;
  };

  const parseCanalWidth = (widthStr: any) => {
    if (!widthStr) return 5;
    const nums = String(widthStr).match(/[\d.]+/g);
    if (!nums) return 5;
    const vals = nums.map(Number).filter((v) => v > 0);
    return vals.length ? vals.reduce((a, b) => a + b, 0) / vals.length : 5;
  };

  // Proximity water level lookup for canals
  const findNearestWaterLevel = (canalFeature: any) => {
    const MAX_DEG = 0.05;
    const coords = canalFeature.geometry.coordinates;
    const isMulti = canalFeature.geometry.type === "MultiLineString";
    const line = isMulti ? coords[0] : coords;
    const midPt = line[Math.floor(line.length / 2)];
    const canalName = (canalFeature.properties.canal_name || "").trim();
    if (!midPt) return { val: null, name: "", status: null } as any;

    const B = BRef.current;

    // 1. Match by canal name via waterEdges (most accurate)
    for (const [rName, edges] of Object.entries(B.riverEdgeMap || {})) {
      const matchName = rName === canalName || rName.includes(canalName) || canalName.includes(rName);
      if (matchName) {
        const stationIdSet = new Set<number>();
        (edges as any[]).forEach((e) => {
          if (e.proxy && e.proxy.start) stationIdSet.add(e.proxy.start.station_id);
          if (e.proxy && e.proxy.end) stationIdSet.add(e.proxy.end.station_id);
        });

        const freshLevs: number[] = [], freshStatuses: string[] = [];
        stationIdSet.forEach((sid) => {
          const st = B.stationById[sid];
          if (!st) return;
          if (st.props.wl_in != null) freshLevs.push(st.props.wl_in);
          if (st.props.status) freshStatuses.push(st.props.status);
        });

        const avgLev = freshLevs.length ? freshLevs.reduce((a, b) => a + b, 0) / freshLevs.length : null;
        const hasCrit = freshStatuses.includes("critical");
        const hasWarn = freshStatuses.includes("warning");
        const status = hasCrit ? "critical" : hasWarn ? "warning" : avgLev != null ? "normal" : null;

        let warn: number | null = null, crit: number | null = null, leftBank: number | null = null, rightBank: number | null = null;
        let dailyMax: number | null = null, dailyMaxYst: number | null = null, wlOut: number | null = null, stName = "";
        let bestD = Infinity;
        stationIdSet.forEach((sid) => {
          const st = B.stationById[sid];
          if (!st) return;
          const d = Math.hypot(st.coords[1] - midPt[1], st.coords[0] - midPt[0]);
          if (d < bestD) {
            bestD = d;
            const p = st.props;
            warn = p.warning_in;
            crit = p.critical_in;
            leftBank = p.left_bank;
            rightBank = p.right_bank;
            dailyMax = p.daily_max;
            dailyMaxYst = p.daily_max_yst;
            wlOut = p.wl_out;
            stName = p.name || "";
          }
        });

        let maxRisk = null;
        if (crit != null && avgLev != null) {
          const warnRef = warn != null ? warn : (crit as number) * 0.7;
          const range = (crit as number) - warnRef;
          maxRisk = range > 0 ? Math.min(1, Math.max(0, (avgLev - warnRef) / range)) : (avgLev >= (crit as number) ? 1 : 0);
        }
        const gradient = (edges as any[]).length > 0 && (edges as any[])[0].proxy ? (edges as any[])[0].proxy.gradient_m_per_km : null;
        return {
          val: avgLev,
          name: stName || (edges as any[])[0].river_name_en || rName,
          status,
          warn,
          crit,
          leftBank,
          rightBank,
          dailyMax,
          dailyMaxYst,
          wlOut,
          riskScore: maxRisk,
          gradient,
          stationCount: stationIdSet.size,
          fromEdges: true,
        };
      }
    }

    // 2. Fallback: proximity search in B.waterlevel
    if (!B.waterlevel || !B.waterlevel.features) return { val: null, name: "", status: null };
    const nameMatch = B.waterlevel.features.filter((f: any) => {
      const r = (f.properties.river || "").trim();
      return r && canalName && (canalName === r || canalName.includes(r) || r.includes(canalName));
    });
    const pool = nameMatch.length > 0 ? nameMatch : B.waterlevel.features;
    let minD = Infinity, best: any = null;
    pool.forEach((f: any) => {
      const sp = f.geometry.coordinates;
      const d = Math.hypot(sp[1] - midPt[1], sp[0] - midPt[0]);
      if (d < minD && d < MAX_DEG) {
        minD = d;
        best = f.properties;
      }
    });
    if (!best) return { val: null, name: "", status: null };
    return {
      val: best.wl_in,
      name: best.name || "",
      status: best.status || null,
      warn: best.warning_in,
      crit: best.critical_in,
      leftBank: best.left_bank,
      rightBank: best.right_bank,
      dailyMax: best.daily_max,
      dailyMaxYst: best.daily_max_yst,
      wlOut: best.wl_out,
    };
  };

  const getCanalStyle = (feature: any, mode: string, currentZoom: number) => {
    const p = feature.properties;
    const isMain = p.canal_type === "Main";
    const detailed = currentZoom >= ZOOM_DETAIL;
    const cls = "flow-canal";
    let baseWeight: number;
    if (detailed) {
      const widthM = parseCanalWidth(p.canal_width);
      baseWeight = widthM >= 25 ? 6 : widthM >= 15 ? 4.5 : widthM >= 8 ? 3 : 1.8;
    } else {
      baseWeight = isMain ? 2.5 : 1.2;
    }

    if (mode === "hierarchy") {
      return { color: isMain ? colors.cyan : "#0e7490", weight: baseWeight, opacity: 0.85, className: cls };
    }

    if (mode === "status") {
      const nearest = findNearestWaterLevel(feature);
      let color;
      if (!nearest.status || nearest.status === "offline") color = "#4b5563";
      else if (nearest.status === "critical") color = colors.danger;
      else if (nearest.status === "warning") color = colors.warn;
      else color = colors.safe;
      return { color, weight: baseWeight, opacity: 0.9, className: cls };
    }

    // capacity mode
    const nearest = findNearestWaterLevel(feature);
    const depth = parseFloat(p.canal_depth);
    const bank = nearest.leftBank || nearest.rightBank;
    const capacity = depth && depth > 0 ? depth : bank || 2.0;
    let color = "#3b82f6";
    if (nearest.val === null) {
      color = "#4b5563";
    } else {
      const ratio = nearest.val / capacity;
      if (ratio >= 0.8) color = colors.danger;
      else if (ratio >= 0.5) color = colors.warn;
    }
    return { color, weight: baseWeight, opacity: 0.85, className: cls };
  };

  const getBgStyle = (feature: any, mode: string, currentZoom: number) => {
    if (mode === "hierarchy") {
      if (currentZoom >= ZOOM_DETAIL && feature) {
        const widthM = parseCanalWidth(feature.properties.canal_width);
        const bgW = widthM >= 25 ? 10 : widthM >= 15 ? 7.5 : widthM >= 8 ? 5 : 3.5;
        return { color: "#083344", weight: bgW, opacity: 0.6 };
      }
      return { color: "#083344", weight: 1.8, opacity: 0.4 };
    }
    return { color: "#111827", weight: 1.8, opacity: 0.25 };
  };

  const canalPopupFn = (f: any) => {
    return () => {
      const p = f.properties;
      const n = findNearestWaterLevel(f);
      const wl = n.val !== null && n.val !== undefined ? n.val.toFixed(2) + " ม." : "ไม่มีข้อมูล";
      const depth = p.canal_depth && parseFloat(p.canal_depth) > 0 ? parseFloat(p.canal_depth).toFixed(1) + " ม." : "ไม่ระบุ";
      const bank = n.leftBank || n.rightBank;
      const bankStr = bank ? bank.toFixed(2) + " ม." : "ไม่ระบุ";
      const headroom = n.val != null && bank ? (bank - n.val).toFixed(2) + " ม." : "-";
      const dailyMax = n.dailyMax != null ? n.dailyMax.toFixed(2) + " ม." : "-";
      const dailyMaxYst = n.dailyMaxYst != null ? n.dailyMaxYst.toFixed(2) + " ม." : "-";
      const stName = esc(n.name || "N/A");
      const warn = n.warn ? n.warn.toFixed(2) : "-";
      const crit = n.crit ? n.crit.toFixed(2) : "-";
      const statusColor =
        n.status === "critical"
          ? colors.danger
          : n.status === "warning"
          ? colors.warn
          : n.status === "normal"
          ? colors.safe
          : "#4b5563";
      const statusTh =
        n.status === "critical"
          ? "วิกฤต"
          : n.status === "warning"
          ? "เฝ้าระวัง"
          : n.status === "normal"
          ? "ปกติ"
          : "ไม่มีข้อมูล";

      const edgeExtra = n.fromEdges
        ? '<div style="background:#1e293b;border-radius:4px;padding:3px 6px;margin:3px 0;font-size:11px;color:#94a3b8">' +
          (n.riskScore != null
            ? 'Risk: <b style="color:' + riskScoreColor(n.riskScore) + '">' + (n.riskScore * 100).toFixed(0) + "%</b>"
            : "") +
          (n.gradient != null ? " &nbsp;·&nbsp; ↗ " + n.gradient.toFixed(3) + " ม./กม." : "") +
          (n.stationCount ? " &nbsp;·&nbsp; " + n.stationCount + " จุดวัด" : "") +
          "</div>"
        : "";

      return (
        "<b>" +
        esc(p.canal_name) +
        "</b>" +
        '<span style="float:right;background:' +
        statusColor +
        ';color:#fff;font-size:10px;padding:1px 6px;border-radius:8px;margin-left:6px">' +
        statusTh +
        "</span><br>" +
        "ประเภท: " +
        (p.canal_type === "Main" ? "คลองหลัก" : "คลองรอง") +
        " · กว้าง: " +
        esc(p.canal_width) +
        " ม.<br>" +
        '<hr style="margin:4px 0;border-color:#374151">' +
        (n.fromEdges ? "<b>ระดับน้ำเฉลี่ยในคลอง:</b> " : "<b>สถานีใกล้สุด:</b> " + stName + "<br>ระดับน้ำ: ") +
        "<b>" +
        wl +
        "</b>" +
        (n.fromEdges
          ? ' <span style="color:#6b7280;font-size:11px">(ค่าเฉลี่ย ' +
            (n.stationCount || 0) +
            " สถานีในคลอง)</span><br>" +
            (stName !== "N/A" ? "สถานีอ้างอิง: " + stName + "<br>" : "")
          : "") +
        (n.warn ? ' <span style="color:#d29922">(เฝ้าระวัง: ' + warn + ")</span>" : "") +
        (n.crit ? ' <span style="color:#da3633">(วิกฤต: ' + crit + ")</span>" : "") +
        "<br>" +
        "ระดับตลิ่ง: " +
        bankStr +
        " · เหลือ: <b>" +
        headroom +
        "</b><br>" +
        "สูงสุดวันนี้: " +
        dailyMax +
        " · เมื่อวาน: " +
        dailyMaxYst +
        "<br>" +
        "ความลึกคลอง: " +
        depth +
        edgeExtra
      );
    };
  };

  // 2. Load geojson chunk dynamically for canals
  const updateCanalsLayer = () => {
    const map = mapInstanceRef.current;
    const L = LRef.current;
    if (!map || !L || !canalIndexRef.current || !map.hasLayer(GLayersRef.current.canals)) return;

    const newLevel = getZoomLevel(map.getZoom());
    if (newLevel !== currentZoomLevelRef.current) {
      GLayersRef.current.flowCanals.clearLayers();
      GLayersRef.current.hitCanals.clearLayers();
      GLayersRef.current.bgCanals.clearLayers();
      loadedChunksRef.current.clear();
      currentZoomLevelRef.current = newLevel;
    }

    const majorNames = newLevel === 1 ? new Set(Object.keys(BRef.current.riverEdgeMap || {})) : null;
    const bounds = map.getBounds();
    const [mapS, mapW, mapN, mapE] = [bounds.getSouth(), bounds.getWest(), bounds.getNorth(), bounds.getEast()];

    for (const district in canalIndexRef.current) {
      const info = canalIndexRef.current[district];
      const [dMinLat, dMinLon, dMaxLat, dMaxLon] = info.bbox;
      const overlaps = !(mapN < dMinLat || mapS > dMaxLat || mapE < dMinLon || mapW > dMaxLon);
      if (!overlaps || loadedChunksRef.current.has(info.file)) continue;
      loadedChunksRef.current.add(info.file);

      const levelAtFetch = currentZoomLevelRef.current;
      fetch("/geojson/canals_chunks/" + info.file)
        .then((r) => r.json())
        .then((geojson) => {
          if (currentZoomLevelRef.current !== levelAtFetch) return; // stale response
          
          geojson.features.forEach((f: any) => {
            const name = (f.properties.canal_name || "").trim();
            if (name && !dangerRegistryRef.current[name]) {
              dangerRegistryRef.current[name] = {
                feature: f,
                riskScore: computeCanalRisk(f),
                widthM: parseCanalWidth(f.properties.canal_width),
              };
            }
          });

          let features = geojson.features;
          if (levelAtFetch === 1) {
            if (!(majorNames instanceof Set)) return;
            features = features.filter((f: any) => {
              const n = (f.properties.canal_name || "").trim();
              return [...majorNames].some((rn) => rn === n || rn.includes(n) || n.includes(rn));
            });
          } else if (levelAtFetch === 2) {
            features = features.filter((f: any) => f.properties.canal_type === "Main");
          } else if (levelAtFetch === 3) {
            features = features.filter((f: any) => {
              if (f.properties.canal_type === "Main") return true;
              const nearest = findNearestWaterLevel(f);
              const val = nearest.val;
              const warn = nearest.warn;
              if (val == null || !warn || warn <= 0) return false;
              return val / warn >= 0.7;
            });
          }

          const fc = { type: "FeatureCollection", features };
          GLayersRef.current.flowCanals.addData(fc);
          GLayersRef.current.hitCanals.addData(fc);
          GLayersRef.current.bgCanals.addData(fc);
        })
        .catch((err) => {
          console.error("Canal chunk error:", info.file, err);
          loadedChunksRef.current.delete(info.file);
        });
    }
  };

  const computeCanalRisk = (feature: any) => {
    const p = feature.properties;
    const canalName = (p.canal_name || "").trim();
    for (const [rName, edges] of Object.entries(BRef.current.riverEdgeMap || {})) {
      if (rName === canalName || rName.includes(canalName) || canalName.includes(rName)) {
        const proxyScores = (edges as any[]).map((e) => e.proxy?.risk_score ?? -1).filter((s) => s >= 0);
        if (proxyScores.length) return Math.max(...proxyScores);
        
        const stationIdSet = new Set<number>();
        (edges as any[]).forEach((e) => {
          if (e.proxy && e.proxy.start) stationIdSet.add(e.proxy.start.station_id);
          if (e.proxy && e.proxy.end) stationIdSet.add(e.proxy.end.station_id);
        });
        
        const freshLevs: number[] = [];
        let crit: number | null = null, warn: number | null = null, bank: number | null = null;
        stationIdSet.forEach((sid) => {
          const st = BRef.current.stationById[sid];
          if (!st) return;
          if (st.props.wl_in != null) freshLevs.push(st.props.wl_in);
          if (crit == null) {
            crit = st.props.critical_in;
            warn = st.props.warning_in;
            bank = st.props.left_bank || st.props.right_bank;
          }
        });
        if (!freshLevs.length) return 0;
        const avgLev = freshLevs.reduce((a, b) => a + b, 0) / freshLevs.length;
        const depth = parseFloat(p.canal_depth);
        const capacity = depth && depth > 0 ? depth : bank || 2.0;
        const critRef = crit || capacity;
        const warnRef = warn || critRef * 0.7;
        const range = critRef - warnRef;
        return range > 0 ? Math.min(1, Math.max(0, (avgLev - warnRef) / range)) : (avgLev >= critRef ? 1 : 0);
      }
    }
    return 0;
  };

  // 3. Load pipes dynamically from ArcGIS server
  const loadPipes = () => {
    const map = mapInstanceRef.current;
    const L = LRef.current;
    if (!map || !L || !visibleLayers.has("pipes")) return;

    const note = document.getElementById("pipenote");
    if (map.getZoom() < 15) {
      GLayersRef.current.pipes.clearLayers();
      if (note) {
        note.style.display = "block";
        note.textContent = "Zoom in (level ≥15) to stream drainage pipes.";
      }
      return;
    }
    if (note) {
      note.style.display = "block";
      note.textContent = "Loading pipes…";
    }
    
    const b = map.getBounds();
    const my = ++pipeReqRef.current;
    const env = [b.getWest(), b.getSouth(), b.getEast(), b.getNorth()].join(",");
    const PIPE_URL = "https://bmasedgis.bangkok.go.th/sedgis/rest/services/Hosted/drainage_200268_gdb/FeatureServer/5/query";
    const u =
      PIPE_URL +
      "?where=1%3D1&outFields=pipe_code,dimension,pipe_class,roadcl_name,clean_type&outSR=4326&f=geojson" +
      "&geometryType=esriGeometryEnvelope&inSR=4326&spatialRel=esriSpatialRelIntersects&resultRecordCount=4000" +
      "&geometry=" +
      encodeURIComponent(env);
      
    fetch(u)
      .then((r) => r.json())
      .then((j) => {
        if (my !== pipeReqRef.current) return;
        GLayersRef.current.pipes.clearLayers();
        const n = (j.features || []).length;
        L.geoJSON(j, {
          style: { color: "#6e7681", weight: 1, opacity: 0.7 },
          onEachFeature: (f: any, l: any) => {
            const p = f.properties;
            l.bindPopup(
              "<b>ท่อระบายน้ำ</b><br>" +
                esc(p.pipe_code) +
                "<br>" +
                esc(p.roadcl_name) +
                "<br>" +
                esc(p.dimension) +
                " · " +
                esc(p.pipe_class) +
                "<br>ล้างท่อ: " +
                esc(p.clean_type)
            );
          },
        }).addTo(GLayersRef.current.pipes);
        if (note) {
          note.textContent =
            n >= 4000
              ? "Showing 4000 pipes (capped) — zoom in for more."
              : n + " pipes in view.";
        }
      })
      .catch(() => {
        if (my === pipeReqRef.current && note) {
          note.textContent = "Pipe load failed (server/CORS).";
        }
      });
  };

  // 4. Load canals index at startup
  const loadCanalsIndex = async () => {
    try {
      const res = await fetch("/geojson/canals_chunks/index.json");
      if (!res.ok) return;
      canalIndexRef.current = await res.json();
      updateCanalsLayer();
    } catch (e) {
      console.error("Failed to load canal index", e);
    }
  };

  // 5. Danger views calculations
  const loadAllChunksForDanger = async () => {
    if (!canalIndexRef.current) return;
    const pending = Object.values(canalIndexRef.current)
      .map((i: any) => i.file)
      .filter((f) => !dangerChunksLoadedRef.current.has(f));
      
    if (!pending.length) {
      buildCanalGraph();
      refreshTop5Layer();
      return;
    }
    
    await Promise.all(
      pending.map((file) =>
        fetch("/geojson/canals_chunks/" + file)
          .then((r) => r.json())
          .then((geojson) => {
            dangerChunksLoadedRef.current.add(file);
            geojson.features.forEach((f: any) => {
              const name = (f.properties.canal_name || "").trim();
              if (!name) return;
              const riskScore = computeCanalRisk(f);
              const widthM = parseCanalWidth(f.properties.canal_width);
              if (!dangerRegistryRef.current[name] || riskScore > dangerRegistryRef.current[name].riskScore) {
                dangerRegistryRef.current[name] = { feature: f, riskScore, widthM };
              }
            });
          })
          .catch((err) => console.error("Danger chunk error:", file, err))
      )
    );
    buildCanalGraph();
    refreshTop5Layer();
  };

  const buildCanalGraph = () => {
    const GGraph: Record<string, any> = {};
    // Pass 1
    Object.entries(dangerRegistryRef.current).forEach(([name, entry]) => {
      GGraph[name] = {
        feature: entry.feature,
        riskScore: entry.riskScore,
        widthM: entry.widthM,
        toCanal: (entry.feature.properties.to_canal || "").trim(),
        from: [],
      };
    });
    // Pass 2
    Object.entries(GGraph).forEach(([name, node]) => {
      const dest = node.toCanal;
      if (dest && GGraph[dest]) GGraph[dest].from.push(name);
    });
    BRef.current.canalGraph = GGraph;
  };

  const addCanalToLayer = (name: string, node: any, role: string, label: string, shown: Set<string>) => {
    const L = LRef.current;
    if (shown.has(name)) return;
    shown.add(name);
    
    const color = role === "danger" ? colors.danger : role === "warn" ? colors.warn : colors.orange;
    const w = node.widthM >= 20 ? 7 : node.widthM >= 10 ? 5 : 3.5;
    
    L.geoJSON(node.feature, {
      style: {
        color,
        weight: role === "danger" ? w + 2 : w,
        opacity: role === "upstream" ? 0.65 : 0.9,
        className: "flow-canal",
      },
      onEachFeature: (f: any, l: any) => {
        l.bindTooltip(label, { permanent: true, direction: "center", className: "canal-top5-label", sticky: false });
        l.bindPopup(canalPopupFn(f));
      },
    }).addTo(GLayersRef.current.top5Layer);
  };

  const refreshTop5Layer = () => {
    const map = mapInstanceRef.current;
    const top5Layer = GLayersRef.current.top5Layer;
    if (!top5Layer) return;
    
    top5Layer.clearLayers();
    if (!dangerViewEnabled) {
      if (map.hasLayer(top5Layer)) map.removeLayer(top5Layer);
      return;
    }
    
    top5Layer.addTo(map);
    if (!BRef.current.canalGraph || !Object.keys(BRef.current.canalGraph).length) {
      buildCanalGraph();
    }
    
    const shown = new Set<string>();
    const bottlenecks = Object.entries(BRef.current.canalGraph || {})
      .filter(([, n]: any) => n.riskScore >= 0.5)
      .sort(([, a]: any, [, b]: any) => b.riskScore - a.riskScore)
      .slice(0, 25);
      
    bottlenecks.forEach(([name, node]: any) => {
      const pct = (node.riskScore * 100).toFixed(0);
      addCanalToLayer(
        name,
        node,
        "danger",
        '<span class="canal-rank-badge">⚠ คอขวด</span><br>' +
          esc(name) +
          "<br>" +
          '<span style="color:var(--danger)">' +
          pct +
          "% เต็มความจุ</span>",
        shown
      );
      
      const destName = node.toCanal;
      const destNode = BRef.current.canalGraph[destName];
      if (destName && destNode) {
        addCanalToLayer(destName, destNode, "warn", '<span style="color:var(--warn)">↓ รับน้ำล้นจาก</span><br>' + esc(name), shown);
      }
      
      node.from.forEach((upName: string) => {
        const upNode = BRef.current.canalGraph[upName];
        if (upNode) {
          addCanalToLayer(
            upName,
            upNode,
            "upstream",
            esc(upName) +
              "<br>" +
              '<span style="color:var(--orange)">↑ ระบายเข้า</span> <b>' +
              esc(name) +
              "</b><br>" +
              '<span style="color:var(--muted)">ปลายทางเต็ม </span><span style="color:var(--danger)">' +
              pct +
              "%</span>",
            shown
          );
        }
      });
    });
  };

  // Main mounting logic
  useEffect(() => {
    if (!mapRef.current || mapInstanceRef.current) return;

    let mounted = true;

    void import("leaflet").then((L: any) => {
      if (!mounted) return;
      LRef.current = L;

      // Base Leaflet setup
      const map = L.map(mapRef.current!).setView([13.7462, 100.7764], 12);
      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: "© OpenStreetMap contributors",
      }).addTo(map);

      mapInstanceRef.current = map;
      
      GLayersRef.current.floodnode = L.layerGroup().addTo(map);
      GLayersRef.current.surface = L.layerGroup().addTo(map);
      
      // Zoom initial settings trigger
      if (onZoomChange) {
        onZoomChange(map.getZoom(), getZoomLevel(map.getZoom()));
      }

      // Load all geojson files on mount
      void loadGeoJSONs();
    });

    return () => {
      mounted = false;
      if (mapInstanceRef.current) {
        mapInstanceRef.current.remove();
        mapInstanceRef.current = null;
      }
    };
  }, []);

  // Set up the Leaflet GeoJSON layer creation
  const loadGeoJSONs = async () => {
    const layers = [
      "districts",
      "protection",
      "tunnels",
      "pipejack",
      "sumps",
      "gates",
      "pumps",
      "waterlevel",
      "expo473",
      "roadflood",
      "rivers",
      "waterEdges",
    ];

    await Promise.all(
      layers.map(async (name) => {
        try {
          const res = await fetch(`/geojson/${name}.geojson`);
          if (res.ok) {
            BRef.current[name] = await res.json();
          }
        } catch (e) {
          console.error(`Failed to load ${name} geojson`, e);
        }
      })
    );

    const B = BRef.current;
    
    // Check if waterlevel data exists
    const hasLiveData = B.waterlevel && B.waterlevel.features && B.waterlevel.features.some((f: any) => f.properties.observed_at);
    if (!hasLiveData && B.waterlevel && B.waterlevel.features) {
      B.waterlevel.features.forEach((f: any) => {
        if (f.properties.wl_in === null || f.properties.wl_in === undefined) {
          f.properties.wl_in = Math.round((Math.random() * 2.0 - 0.8) * 100) / 100;
        }
      });
    }

    // Hash maps for fast station lookup
    BRef.current.stationById = {};
    if (B.waterlevel && B.waterlevel.features) {
      B.waterlevel.features.forEach((f: any) => {
        const id = f.properties.station_id;
        if (id != null) BRef.current.stationById[id] = { props: f.properties, coords: f.geometry.coordinates };
      });
    }

    BRef.current.riverEdgeMap = {};
    if (B.waterEdges && B.waterEdges.features) {
      B.waterEdges.features.forEach((f: any) => {
        const r = (f.properties.river_name_th || "").trim();
        if (r) {
          if (!BRef.current.riverEdgeMap[r]) BRef.current.riverEdgeMap[r] = [];
          BRef.current.riverEdgeMap[r].push(f.properties);
        }
      });
    }

    // Now instantiate layers in Leaflet
    createLeafletLayers();
  };

  const createLeafletLayers = () => {
    const L = LRef.current;
    const B = BRef.current;
    const G = GLayersRef.current;
    const map = mapInstanceRef.current;

    const pts = (fc: any, style: any, popup: any) => {
      return L.geoJSON(fc, {
        pointToLayer: (f: any, ll: any) => L.circleMarker(ll, style(f.properties)),
        onEachFeature: (f: any, l: any) => l.bindPopup(popup(f.properties)),
      });
    };

    const lines = (fc: any, style: any, popup: any) => {
      return L.geoJSON(fc, {
        style,
        onEachFeature: (f: any, l: any) => l.bindPopup(popup(f.properties)),
      });
    };

    G.districts = L.geoJSON(B.districts, {
      style: { color: "#000000", weight: 1, fill: false, opacity: 0.5 },
      interactive: false,
    });

    G.protection = L.geoJSON(B.protection, {
      style: { color: colors.accent, weight: 1, fillColor: colors.accent, fillOpacity: 0.07 },
      onEachFeature: (f: any, l: any) =>
        l.bindPopup(
          "<b>พื้นที่ป้องกันน้ำท่วม</b><br>" +
            esc(f.properties.fd_name) +
            "<br>" +
            esc(f.properties.district_t) +
            " · " +
            esc(f.properties.area_bma) +
            " กม.²"
        ),
    });

    G.rivers = L.layerGroup([
      L.geoJSON(B.rivers, { style: { color: "#1d4ed8", weight: 7, opacity: 0.55 }, interactive: false }),
      L.geoJSON(B.rivers, {
        style: { color: "#60a5fa", weight: 2.8, opacity: 0.95 },
        onEachFeature: (f: any, l: any) =>
          l.bindPopup("<b>" + esc(f.properties.name_th) + "</b><br>" + esc(f.properties.name_en)),
      }),
    ]);

    G.tunnels = lines(B.tunnels, { color: colors.pink, weight: 4, opacity: 0.9 }, (p: any) =>
      "<b>อุโมงค์ระบายน้ำ</b><br>" +
        esc(p.tunnel_name) +
        "<br>" +
        esc(p.tunnel_code) +
        " · " +
        esc(p.tunnel_length) +
        " m<br>" +
        esc(p.owner)
    );

    G.pipejack = lines(B.pipejack, { color: colors.orange, weight: 3, opacity: 0.9, dashArray: "5,4" }, (p: any) =>
      "<b>ท่อดันลอด</b><br>" +
        esc(p.pipej_code) +
        " · " +
        esc(p.pipej_type) +
        "<br>" +
        esc(p.dimension) +
        " · " +
        esc(p.discharge)
    );

    G.sumps = pts(
      B.sumps,
      () => ({ radius: 3.5, color: "#fff", weight: 1, fillColor: "#d2a8ff", fillOpacity: 0.85 }),
      (p: any) =>
        "<b>บ่อสูบน้ำ</b><br>" +
        esc(p.sump_name) +
        "<br>" +
        esc(p.sump_code) +
        " · " +
        esc(p.district_t) +
        "<br>" +
        esc(p.sump_type) +
        " · " +
        esc(p.volume) +
        " ลบ.ม. · " +
        esc(p.sump_depth) +
        " ม.<br>ปั๊ม " +
        esc(p.pump_amount)
    );

    G.gates = pts(
      B.floodgates, // geojson filename is floodgates but property matches 'gates'
      () => ({ radius: 4, color: "#fff", weight: 1, fillColor: colors.purple, fillOpacity: 0.9 }),
      (p: any) => "<b>ประตูระบายน้ำ</b><br>" + esc(p.gate_name) + "<br>" + esc(p.hy_lname) + "<br>" + esc(p.district_t)
    );

    G.pumps = pts(
      B.pumpstations, // geojson filename is pumpstations but property matches 'pumps'
      () => ({ radius: 4, color: "#fff", weight: 1, fillColor: colors.orange, fillOpacity: 0.9 }),
      (p: any) =>
        "<b>สถานีสูบน้ำ</b><br>" +
        esc(p.pump_name) +
        "<br>" +
        esc(p.hy_lname) +
        "<br>" +
        esc(p.district_t) +
        " · " +
        esc(p.motor_num)
    );

    G.waterlevel = pts(
      B.waterlevel,
      (p: any) => ({ radius: 4.5, color: "#fff", weight: 1, fillColor: wlStatusColor(p.status, colors.accent), fillOpacity: 0.9 }),
      (p: any) => {
        const wl = p.wl_in !== null && p.wl_in !== undefined ? p.wl_in.toFixed(2) + " ม.รทก." : "ไม่มีข้อมูล";
        const wlOut = p.wl_out !== null && p.wl_out !== undefined ? p.wl_out.toFixed(2) + " ม.รทก." : "ไม่มีข้อมูล";
        const warn = p.warning_in !== null && p.warning_in !== undefined ? p.warning_in.toFixed(2) + " ม.รทก." : "N/A";
        const crit = p.critical_in !== null && p.critical_in !== undefined ? p.critical_in.toFixed(2) + " ม.รทก." : "N/A";
        const time = p.observed_at ? p.observed_at : "N/A";
        const statusText =
          p.status === "critical"
            ? '<span style="color:var(--danger);font-weight:bold">วิกฤต (Critical)</span>'
            : p.status === "warning"
            ? '<span style="color:var(--warn);font-weight:bold">เฝ้าระวัง (Warning)</span>'
            : p.status === "normal"
            ? '<span style="color:var(--safe);font-weight:bold">ปกติ (Normal)</span>'
            : p.status === "offline"
            ? '<span style="color:var(--muted)">ออฟไลน์ (Offline)</span>'
            : "ไม่ทราบสถานะ";
            
        return (
          "<b>สถานีวัดระดับน้ำ: " +
          esc(p.name) +
          "</b><br>" +
          "รหัส: " +
          esc(p.code) +
          " · เขต" +
          esc(p.district) +
          "<br>" +
          "แหล่งน้ำ: " +
          esc(p.river) +
          "<br>" +
          "ระดับน้ำในคลอง: <b>" +
          wl +
          "</b> (เกณฑ์เตือนภัย: " +
          warn +
          " / วิกฤต: " +
          crit +
          ")<br>" +
          "ระดับน้ำนอกคลอง: " +
          wlOut +
          "<br>" +
          "สถานะ: " +
          statusText +
          "<br>" +
          '<span style="color:var(--muted);font-size:11px">เวลาอัปเดต: ' +
          esc(time) +
          "</span>"
        );
      }
    );

    G.expo473 = pts(
      B.expo473,
      (p: any) => ({ radius: 5, color: "#fff", weight: 1, fillColor: expoColor(p.status_num), fillOpacity: 0.95 }),
      (p: any) =>
        "<b>จุดเสี่ยง 473</b><br>" +
        esc(p.name) +
        "<br>เขต " +
        esc(p.district) +
        "<br>" +
        esc(p.status_detail) +
        " (" +
        esc(p.status_num) +
        ")<br>" +
        esc(p.problem) +
        '<br><span style="color:#444">' +
        esc((p.detail || "").slice(0, 160)) +
        "</span>"
    );

    G.roadflood = pts(
      B.roadflood,
      (p: any) => ({ radius: 6, color: "#fff", weight: 1.5, fillColor: floodColor(p), fillOpacity: 1 }),
      (p: any) =>
        "<b>สถานีวัดน้ำท่วมถนน</b><br>" +
        esc(p.name) +
        "<br>" +
        esc(p.code) +
        " · " +
        esc(p.district) +
        "<br>" +
        esc(p.road) +
        "<br><b>" +
        esc(p.flood) +
        " ซม.</b> · " +
        esc(p.device_status) +
        '<br><span style="color:#888">' +
        esc(p.date_updated) +
        "</span>"
    );

    // Initialize canals sublayers: flowCanals, hitCanals, bgCanals
    G.bgCanals = L.geoJSON(null, {
      renderer: L.canvas({ padding: 0.5 }),
      style: (f: any) => getBgStyle(f, activeCanalMode, map.getZoom()),
      interactive: false,
    });

    G.hitCanals = L.geoJSON(null, {
      renderer: L.svg({ padding: 0.5 }),
      style: () => ({ color: "#fff", weight: 14, opacity: 0.01, fill: false }),
      onEachFeature: (f: any, l: any) => l.bindPopup(canalPopupFn(f)),
    });

    G.flowCanals = L.geoJSON(null, {
      renderer: L.svg({ padding: 0.5 }),
      style: (f: any) => getCanalStyle(f, activeCanalMode, map.getZoom()),
      onEachFeature: (f: any, l: any) => l.bindPopup(canalPopupFn(f)),
    });

    G.canals = L.layerGroup([G.bgCanals, G.hitCanals, G.flowCanals]);
    G.pipes = L.layerGroup();
    G.top5Layer = L.layerGroup();

    // Setup district click handler
    map.on("click", (e: any) => {
      if (!map.hasLayer(G.districts)) return;
      const pt = [e.latlng.lng, e.latlng.lat];
      const clickedDistrict = B.districts.features.find((f: any) => ptInGeometry(pt, f.geometry));
      if (clickedDistrict) {
        const props = clickedDistrict.properties;
        L.popup()
          .setLatLng(e.latlng)
          .setContent("<b>เขต " + esc(props.DISTRICT_N) + "</b><br>code " + esc(props.CODE) + ' · ' + esc(props.AREA_BMA) + " กม.²")
          .openOn(map);
      }
    });

    // Setup moveend for canals chunks index and live pipes stream
    map.on("moveend", () => {
      updateCanalsLayer();
      loadPipes();
    });

    map.on("zoomend", () => {
      const z = map.getZoom();
      const lvl = getZoomLevel(z);
      if (onZoomChange) {
        onZoomChange(z, lvl);
      }
      updateCanalsLayer();
      loadPipes();
    });

    // Load canals chunks index if canals is enabled
    loadCanalsIndex();

    // Trigger onStatsLoaded to parent
    if (onStatsLoaded) {
      const rf = B.roadflood.features.map((f: any) => f.properties);
      const flooded = rf.filter((p: any) => (p.flood || 0) > 0 && p.device_status === "normal").length;
      let tot = 81574; // pipes cap
      for (const key of ["districts", "protection", "tunnels", "pipejack", "sumps", "gates", "pumps", "waterlevel", "expo473", "roadflood", "rivers"]) {
        const layerData = B[key];
        if (layerData && layerData.features) {
          tot += layerData.features.length;
        }
      }

      onStatsLoaded({
        totalFeatures: tot,
        districts: B.districts.features.length,
        roadSensors: rf.length,
        floodedNow: flooded,
        pumpsCount: B.pumps.features.length,
        gatesCount: B.gates.features.length,
        sumpsCount: B.sumps.features.length,
        waterLevelCount: B.waterlevel.features.length,
        risk473Count: B.expo473.features.length,
      });
    }

    // Now, sync initial visibility of layers
    syncInitialLayers();
  };

  const syncInitialLayers = () => {
    const map = mapInstanceRef.current;
    const G = GLayersRef.current;
    if (!map) return;

    for (const [k, layer] of Object.entries(G)) {
      if (k === "pipes" || k === "canals" || k === "floodnode" || k === "surface") continue;
      const isVisible = visibleLayers.has(k);
      if (isVisible) {
        layer.addTo(map);
      }
    }

    if (visibleLayers.has("canals")) {
      G.canals.addTo(map);
      updateCanalsLayer();
    }
    if (visibleLayers.has("pipes")) {
      G.pipes.addTo(map);
      loadPipes();
    }
  };

  // Sync layer visibility on props changes
  useEffect(() => {
    const map = mapInstanceRef.current;
    const G = GLayersRef.current;
    if (!map || !G || Object.keys(G).length === 0) return;

    for (const [k, layer] of Object.entries(G)) {
      if (
        k === "pipes" ||
        k === "canals" ||
        k === "top5Layer" ||
        k === "bgCanals" ||
        k === "flowCanals" ||
        k === "hitCanals" ||
        k === "floodnode" ||
        k === "surface"
      )
        continue;
      const isVisible = visibleLayers.has(k);
      if (isVisible) {
        if (!map.hasLayer(layer)) layer.addTo(map);
      } else {
        if (map.hasLayer(layer)) map.removeLayer(layer);
      }
    }

    // Canals
    const canalsVisible = visibleLayers.has("canals");
    if (canalsVisible) {
      if (!map.hasLayer(G.canals)) {
        G.canals.addTo(map);
        updateCanalsLayer();
      }
    } else {
      if (map.hasLayer(G.canals)) map.removeLayer(G.canals);
    }

    // Pipes
    const pipesVisible = visibleLayers.has("pipes");
    if (pipesVisible) {
      if (!map.hasLayer(G.pipes)) {
        G.pipes.addTo(map);
        loadPipes();
      }
    } else {
      if (map.hasLayer(G.pipes)) {
        G.pipes.clearLayers();
        map.removeLayer(G.pipes);
      }
    }
  }, [visibleLayers]);

  // Synchronize live situation layers: floodnode and water-surface
  useEffect(() => {
    const map = mapInstanceRef.current;
    const L = LRef.current;
    if (!map || !L) return;

    let nodesInterval: any = null;
    let surfaceInterval: any = null;

    const nodeLayer = GLayersRef.current.floodnode;
    const surfaceLayer = GLayersRef.current.surface;

    if (!nodeLayer || !surfaceLayer) return;

    const updateNodes = async () => {
      try {
        const res = await fetch(`${API_URL}/flood-nodes`);
        if (!res.ok) return;
        const nodes = (await res.json()) as FloodNode[];
        nodeLayer.clearLayers();
        for (const node of nodes) {
          if (node.current_fused_level === null) continue;
          const color = levelColor(node.current_fused_level);
          const radius = Math.max(8, node.current_fused_level * 18);
          L.circleMarker([node.lat, node.lon], {
            radius,
            color,
            fillColor: color,
            fillOpacity: 0.85,
            weight: 2,
          })
            .addTo(nodeLayer)
            .bindPopup(
              `<b>${node.name}</b><br>` +
                `ระดับน้ำ: <b>${node.current_fused_level.toFixed(2)} ม.</b><br>` +
                `รายงาน: ${node.n_reports} รายการ`
            );
        }
      } catch {
        // ignore
      }
    };

    const updateSurface = async () => {
      try {
        const res = await fetch(`${API_URL}/water-surface`);
        if (!res.ok) return;
        const data = (await res.json()) as { points: SurfacePoint[] };
        surfaceLayer.clearLayers();
        for (const pt of data.points) {
          const bounds: [[number, number], [number, number]] = [
            [pt.lat - pt.dlat, pt.lon - pt.dlon],
            [pt.lat + pt.dlat, pt.lon + pt.dlon],
          ];
          L.rectangle(bounds, {
            color: "transparent",
            fillColor: levelColor(pt.level),
            fillOpacity: surfaceOpacity(pt.level),
            weight: 0,
            interactive: false,
          }).addTo(surfaceLayer);
        }
      } catch {
        // ignore
      }
    };

    // Handle floodnode layer
    if (visibleLayers.has("floodnode")) {
      if (!map.hasLayer(nodeLayer)) {
        nodeLayer.addTo(map);
      }
      void updateNodes();
      nodesInterval = setInterval(() => void updateNodes(), POLL_NODES_MS);
    } else {
      nodeLayer.clearLayers();
      if (map.hasLayer(nodeLayer)) {
        map.removeLayer(nodeLayer);
      }
    }

    // Handle water-surface layer
    if (visibleLayers.has("water-surface")) {
      if (!map.hasLayer(surfaceLayer)) {
        surfaceLayer.addTo(map);
      }
      void updateSurface();
      surfaceInterval = setInterval(() => void updateSurface(), POLL_SURFACE_MS);
    } else {
      surfaceLayer.clearLayers();
      if (map.hasLayer(surfaceLayer)) {
        map.removeLayer(surfaceLayer);
      }
    }

    return () => {
      if (nodesInterval) clearInterval(nodesInterval);
      if (surfaceInterval) clearInterval(surfaceInterval);
    };
  }, [visibleLayers]);

  // Sync canal mode change
  useEffect(() => {
    const map = mapInstanceRef.current;
    const G = GLayersRef.current;
    if (!map || !G || !G.flowCanals) return;

    G.flowCanals.setStyle((f: any) => getCanalStyle(f, activeCanalMode, map.getZoom()));
    G.bgCanals.setStyle((f: any) => getBgStyle(f, activeCanalMode, map.getZoom()));
  }, [activeCanalMode]);

  // Sync danger view changes
  useEffect(() => {
    const map = mapInstanceRef.current;
    const G = GLayersRef.current;
    if (!map || !G || !G.top5Layer) return;

    if (dangerViewEnabled) {
      void loadAllChunksForDanger();
    } else {
      G.top5Layer.clearLayers();
      if (map.hasLayer(G.top5Layer)) map.removeLayer(G.top5Layer);
    }
  }, [dangerViewEnabled]);

  return (
    <div className="h-full w-full relative">
      <div ref={mapRef} className="h-full w-full" />
      <svg style={{ position: "absolute", width: 0, height: 0, overflow: "hidden" }} version="1.1" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="9" markerHeight="9" orient="auto">
            <path d="M 2 2.5 L 8 5 L 2 7.5 z" fill="#39c5cf" />
          </marker>
        </defs>
      </svg>
      <style>{`
        @keyframes canalFlow {
          to {
            stroke-dashoffset: -20;
          }
        }
        .flow-canal {
          stroke-dasharray: 6, 8;
          animation: canalFlow 1.2s steps(12) infinite;
          marker-end: url(#arrow);
        }
        .canal-top5-label {
          background: rgba(13, 17, 23, 0.9);
          border: 1.5px solid #da3633;
          border-radius: 5px;
          color: #e6edf3;
          font-size: 11.5px;
          padding: 3px 8px;
          white-space: nowrap;
          pointer-events: none;
          box-shadow: 0 2px 6px rgba(0,0,0,.5);
        }
        .canal-top5-label::before {
          display: none;
        }
        .canal-rank-badge {
          color: #da3633;
          font-weight: 700;
          font-size: 13px;
        }
      `}</style>
    </div>
  );
}
