#!/usr/bin/env python3
"""
Build derived edge-network and standalone visualization artifacts.

This script intentionally labels edge water metrics as proxy values. The source
site exposes point water-level measurements, not true hydraulic edge volume.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path: str | Path, data: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def write_text(path: str | Path, text: str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def clean_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def is_bangkok_area(station: dict[str, Any]) -> bool:
    district_name_th = str(station.get("district_name_th") or "").strip()
    return not district_name_th.startswith("อำเภอ")


def merge_non_null(base: Any, override: Any) -> Any:
    if isinstance(base, dict) and isinstance(override, dict):
        keys = base.keys() | override.keys()
        return {
            key: merge_non_null(base.get(key), override.get(key))
            if key in base and key in override
            else override.get(key, base.get(key))
            for key in keys
        }
    return base if override is None else override


def build_all_station_catalog(catalog: dict[str, Any], latest: dict[str, Any]) -> dict[str, Any]:
    catalog_by_id = {station["station_id"]: station for station in catalog["stations"]}
    stations = []
    for source_station in latest["stations"]:
        station = merge_non_null(catalog_by_id.get(source_station["station_id"], {}), source_station)
        station["scope"] = {
            "is_bangkok_area": is_bangkok_area(station),
            "in_page_catalog": station["station_id"] in catalog_by_id,
            "classification_method": "district_name_th starts with อำเภอ => surrounding province",
        }
        stations.append(station)

    bangkok_count = sum(1 for station in stations if station["scope"]["is_bangkok_area"])
    return {
        "metadata": {
            "built_at": now_utc(),
            "source": "Union of latest endpoint stations and page catalog membership",
            "record_count": len(stations),
            "page_catalog_count": len(catalog["stations"]),
            "bangkok_area_count": bangkok_count,
            "surrounding_province_count": len(stations) - bangkok_count,
        },
        "stations": stations,
    }


def clamp(value: float, low: float, high: float) -> float:
    return min(high, max(low, value))


def haversine_km(a_lat: float, a_lon: float, b_lat: float, b_lon: float) -> float:
    radius = 6371.0088
    lat1 = math.radians(a_lat)
    lat2 = math.radians(b_lat)
    dlat = math.radians(b_lat - a_lat)
    dlon = math.radians(b_lon - a_lon)
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(h))


def station_level(station: dict[str, Any], measurements_by_id: dict[int, dict[str, Any]]) -> dict[str, Any]:
    station_id = station["station_id"]
    measurement = measurements_by_id.get(station_id, {})
    wl = clean_float((measurement.get("water_levels_m_msl") or {}).get("wl_in"))
    thresholds = station.get("thresholds") or {}
    levels = station.get("levels") or {}
    warning = clean_float(thresholds.get("warning_in_m_msl"))
    critical = clean_float(thresholds.get("critical_in_m_msl"))
    bed = clean_float(levels.get("bed_bank_m_msl"))
    alert = (measurement.get("status") or {}).get("alert_level") or "unknown"

    relative_to_critical = None
    if wl is not None and bed is not None and critical is not None and critical != bed:
        relative_to_critical = (wl - bed) / (critical - bed)

    risk_from_alert = {
        "normal": 0.2,
        "warning": 0.75,
        "critical": 1.0,
        "offline": 0.55,
        "unknown": 0.35,
    }.get(alert, 0.35)
    risk_from_level = clamp(relative_to_critical, 0, 1) if relative_to_critical is not None else 0

    return {
        "station_id": station_id,
        "wl_in_m_msl": wl,
        "warning_margin_m": warning - wl if warning is not None and wl is not None else None,
        "critical_margin_m": critical - wl if critical is not None and wl is not None else None,
        "relative_to_critical": relative_to_critical,
        "alert_level": alert,
        "risk_score": max(risk_from_alert, risk_from_level),
    }


def sort_group_stations(stations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    points = [
        station
        for station in stations
        if (station.get("location") or {}).get("latitude") is not None
        and (station.get("location") or {}).get("longitude") is not None
    ]
    if len(points) < 2:
        return points

    lats = [station["location"]["latitude"] for station in points]
    lons = [station["location"]["longitude"] for station in points]
    lat_span = max(lats) - min(lats)
    lon_span = max(lons) - min(lons)
    axis = "longitude" if lon_span >= lat_span else "latitude"
    return sorted(points, key=lambda station: (station["location"][axis], station["station_id"]))


def build_edges(catalog: dict[str, Any], latest: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    catalog_stations = catalog["stations"]
    latest_measurements = latest["measurements"]
    measurements_by_id = {measurement["station_id"]: measurement for measurement in latest_measurements}

    by_river: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for station in catalog_stations:
        key = station.get("river_name_th") or station.get("river_name_en") or f"river:{station.get('river_id')}"
        by_river[key].append(station)

    edges = []
    edge_index = 0
    for river_name, stations in sorted(by_river.items(), key=lambda item: item[0]):
        ordered = sort_group_stations(stations)
        if len(ordered) < 2:
            continue

        for seq, (start, end) in enumerate(zip(ordered, ordered[1:]), start=1):
            start_loc = start["location"]
            end_loc = end["location"]
            length_km = haversine_km(
                start_loc["latitude"],
                start_loc["longitude"],
                end_loc["latitude"],
                end_loc["longitude"],
            )
            start_level = station_level(start, measurements_by_id)
            end_level = station_level(end, measurements_by_id)
            water_values = [
                value
                for value in [start_level["wl_in_m_msl"], end_level["wl_in_m_msl"]]
                if value is not None
            ]
            proxy_water_level = sum(water_values) / len(water_values) if water_values else None
            delta = None
            gradient = None
            if start_level["wl_in_m_msl"] is not None and end_level["wl_in_m_msl"] is not None:
                delta = end_level["wl_in_m_msl"] - start_level["wl_in_m_msl"]
                gradient = delta / length_km if length_km else None

            risk_score = max(start_level["risk_score"], end_level["risk_score"])
            edge_index += 1
            edges.append(
                {
                    "edge_id": f"edge-{edge_index:03d}",
                    "river_name_th": river_name,
                    "river_name_en": start.get("river_name_en") or end.get("river_name_en"),
                    "river_id": start.get("river_id") or end.get("river_id"),
                    "sequence_in_river": seq,
                    "from_station_id": start["station_id"],
                    "to_station_id": end["station_id"],
                    "from_station_name_th": start.get("station_short_name_th") or start.get("station_name_th"),
                    "to_station_name_th": end.get("station_short_name_th") or end.get("station_name_th"),
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [
                            [start_loc["longitude"], start_loc["latitude"]],
                            [end_loc["longitude"], end_loc["latitude"]],
                        ],
                    },
                    "length_km": round(length_km, 4),
                    "proxy": {
                        "is_true_volume": False,
                        "method": "adjacent station interpolation within same river/canal group",
                        "water_level_avg_m_msl": round(proxy_water_level, 4) if proxy_water_level is not None else None,
                        "water_level_delta_m": round(delta, 4) if delta is not None else None,
                        "gradient_m_per_km": round(gradient, 4) if gradient is not None else None,
                        "risk_score": round(risk_score, 4),
                        "start": start_level,
                        "end": end_level,
                    },
                }
            )

    summary = {
        "metadata": {
            "built_at": now_utc(),
            "source_catalog_count": len(catalog_stations),
            "source_latest_count": latest["metadata"]["record_count"],
            "method": "For each river/canal group with >=2 catalog stations, sort by dominant latitude/longitude axis and connect adjacent stations.",
            "water_quantity_note": "Edge metrics are proxies from point water levels, not true water volume or flow.",
        },
        "summary": {
            "edge_count": len(edges),
            "river_group_count": len({edge["river_name_th"] for edge in edges}),
            "total_length_km": round(sum(edge["length_km"] for edge in edges), 4),
            "risk_score_max": max((edge["proxy"]["risk_score"] for edge in edges), default=None),
            "risk_score_avg": round(sum(edge["proxy"]["risk_score"] for edge in edges) / len(edges), 4) if edges else None,
            "missing_proxy_water_level_count": sum(1 for edge in edges if edge["proxy"]["water_level_avg_m_msl"] is None),
        },
        "top_river_edge_counts": dict(Counter(edge["river_name_th"] for edge in edges).most_common(20)),
        "highest_risk_edges": sorted(
            [
                {
                    "edge_id": edge["edge_id"],
                    "river_name_th": edge["river_name_th"],
                    "risk_score": edge["proxy"]["risk_score"],
                    "from_station_id": edge["from_station_id"],
                    "to_station_id": edge["to_station_id"],
                }
                for edge in edges
            ],
            key=lambda item: item["risk_score"],
            reverse=True,
        )[:20],
    }
    return edges, summary


def edges_geojson(edges: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": edge["geometry"],
                "properties": {key: value for key, value in edge.items() if key != "geometry"},
            }
            for edge in edges
        ],
    }


def load_histories(history_dir: str | Path) -> dict[str, Any]:
    histories = {}
    for path in sorted(Path(history_dir).glob("*.json"), key=lambda item: int(item.stem)):
        data = read_json(path)
        station_id = str(data["metadata"]["station_id"])
        histories[station_id] = {
            "metadata": data["metadata"],
            "series": [
                {
                    "name": series.get("name_expression") or f"series {series.get('series_index', 0) + 1}",
                    "unit": series.get("unit"),
                    "point_count": series.get("point_count"),
                    "points": [
                        [point["observed_at_utc"], point["value_m_msl"]]
                        for point in series.get("points", [])
                    ],
                }
                for series in data.get("series", [])
            ],
        }
    return histories


def build_viz_payload(
    latest: dict[str, Any],
    catalog: dict[str, Any],
    edges: list[dict[str, Any]],
    edge_summary: dict[str, Any],
    histories: dict[str, Any],
) -> dict[str, Any]:
    measurements_by_id = {measurement["station_id"]: measurement for measurement in latest["measurements"]}
    stations = []
    for station in catalog["stations"]:
        measurement = measurements_by_id.get(station["station_id"], {})
        stations.append(
            {
                "station_id": station["station_id"],
                "station_code": station["station_code"],
                "station_name_th": station["station_name_th"],
                "station_short_name_th": station["station_short_name_th"],
                "river_name_th": station["river_name_th"],
                "district_name_th": station["district_name_th"],
                "scope": station.get("scope"),
                "lat": station["location"]["latitude"],
                "lon": station["location"]["longitude"],
                "thresholds": station["thresholds"],
                "levels": station["levels"],
                "measurement": measurement,
                "history_point_count": sum(series["point_count"] for series in histories.get(str(station["station_id"]), {}).get("series", [])),
            }
        )

    return {
        "metadata": {
            "built_at": now_utc(),
            "dashboard_title": "Bangkok Water Network Dashboard",
            "station_count_all": len(catalog["stations"]),
            "station_count_catalog": catalog.get("metadata", {}).get("page_catalog_count", len(catalog["stations"])),
            "station_count_bangkok_area": catalog.get("metadata", {}).get("bangkok_area_count"),
            "station_count_surrounding_province": catalog.get("metadata", {}).get("surrounding_province_count"),
            "station_count_latest": latest["metadata"]["record_count"],
            "edge_count": len(edges),
            "history_station_count": len(histories),
            "history_total_points": sum(
                series["point_count"]
                for history in histories.values()
                for series in history.get("series", [])
            ),
            "water_quantity_note": "Edge water values are proxy metrics from adjacent station levels, not true edge volume.",
        },
        "summary": latest["summary"],
        "edge_summary": edge_summary,
        "stations": stations,
        "edges": edges,
        "histories": histories,
    }


def html_escape_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


def build_legacy_dashboard_html(payload: dict[str, Any]) -> str:
    payload_json = html_escape_json(payload)
    return f"""<!doctype html>
<html lang="th">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Bangkok Water Network Dashboard</title>
  <style>
    :root {{
      --bg: #f5f7f6;
      --panel: #ffffff;
      --ink: #17211f;
      --muted: #63716c;
      --line: #d9e2df;
      --normal: #1f9f7a;
      --offline: #6f7b81;
      --warning: #d78b24;
      --critical: #c9344d;
      --accent: #1b6b9b;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--ink);
      background: var(--bg);
    }}
    header {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 16px;
      align-items: end;
      padding: 18px 22px 12px;
      border-bottom: 1px solid var(--line);
      background: #fff;
    }}
    h1 {{ margin: 0; font-size: 22px; line-height: 1.2; font-weight: 760; }}
    .sub {{ margin-top: 5px; color: var(--muted); font-size: 13px; }}
    main {{ padding: 16px 18px 22px; display: grid; gap: 14px; }}
    .stats {{
      display: grid;
      grid-template-columns: repeat(6, minmax(120px, 1fr));
      gap: 10px;
    }}
    .stat {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 11px 12px;
      min-height: 74px;
    }}
    .stat .label {{ color: var(--muted); font-size: 12px; }}
    .stat .value {{ font-size: 24px; font-weight: 780; margin-top: 5px; }}
    .workspace {{
      display: grid;
      grid-template-columns: minmax(420px, 1.35fr) minmax(360px, 0.9fr);
      gap: 14px;
      min-height: 560px;
    }}
    .panel {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: hidden;
    }}
    .panel-head {{
      display: flex;
      gap: 10px;
      align-items: center;
      justify-content: space-between;
      padding: 10px 12px;
      border-bottom: 1px solid var(--line);
    }}
    .panel-title {{ font-size: 14px; font-weight: 740; }}
    .tools {{ display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }}
    input, select {{
      height: 34px;
      border: 1px solid var(--line);
      border-radius: 7px;
      padding: 0 9px;
      background: #fff;
      color: var(--ink);
      font-size: 13px;
    }}
    #mapWrap {{ position: relative; height: 610px; }}
    svg {{ display: block; width: 100%; height: 100%; background: #eef4f2; }}
    .edge {{ fill: none; stroke-linecap: round; opacity: 0.75; }}
    .station {{ stroke: #fff; stroke-width: 1.6; cursor: pointer; }}
    .station.selected {{ stroke: #111; stroke-width: 2.6; }}
    .tooltip {{
      position: absolute;
      pointer-events: none;
      background: #10211d;
      color: white;
      padding: 7px 8px;
      border-radius: 6px;
      font-size: 12px;
      max-width: 260px;
      display: none;
      z-index: 4;
    }}
    .detail {{
      display: grid;
      grid-template-rows: auto 260px minmax(220px, 1fr);
    }}
    .station-detail {{ padding: 12px; border-bottom: 1px solid var(--line); min-height: 112px; }}
    .station-name {{ font-weight: 780; font-size: 16px; line-height: 1.35; }}
    .chips {{ display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }}
    .chip {{ font-size: 12px; padding: 4px 7px; border-radius: 999px; border: 1px solid var(--line); background: #f7faf9; }}
    .chart-box {{ padding: 10px 12px; border-bottom: 1px solid var(--line); }}
    #historyCanvas {{ width: 100%; height: 210px; display: block; }}
    .table-wrap {{ overflow: auto; max-height: 360px; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 12px; }}
    th, td {{ padding: 8px 9px; border-bottom: 1px solid var(--line); text-align: left; vertical-align: top; }}
    th {{ position: sticky; top: 0; background: #fff; z-index: 2; color: var(--muted); font-weight: 680; }}
    tr {{ cursor: pointer; }}
    tr:hover {{ background: #f4f8f7; }}
    .note {{ color: var(--muted); font-size: 12px; line-height: 1.5; padding: 10px 12px; border-top: 1px solid var(--line); }}
    @media (max-width: 980px) {{
      header {{ grid-template-columns: 1fr; }}
      .stats {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .workspace {{ grid-template-columns: 1fr; }}
      #mapWrap {{ height: 480px; }}
    }}
  </style>
</head>
<body>
  <script id="waterPayload" type="application/json">{payload_json}</script>
  <header>
    <div>
      <h1>Bangkok Water Network Dashboard</h1>
      <div class="sub" id="metaLine"></div>
    </div>
    <div class="tools">
      <input id="searchBox" type="search" placeholder="ค้นหาสถานี / คลอง / เขต" />
      <select id="riverSelect"><option value="">ทุกคลอง/แม่น้ำ</option></select>
      <select id="statusSelect">
        <option value="">ทุกสถานะ</option>
        <option value="normal">normal</option>
        <option value="warning">warning</option>
        <option value="critical">critical</option>
        <option value="offline">offline</option>
        <option value="unknown">unknown</option>
      </select>
    </div>
  </header>
  <main>
    <section class="stats" id="stats"></section>
    <section class="workspace">
      <div class="panel">
        <div class="panel-head">
          <div class="panel-title">แผนที่ proxy network จากจุดวัด</div>
          <div class="sub" id="visibleCount"></div>
        </div>
        <div id="mapWrap">
          <svg id="mapSvg" viewBox="0 0 960 610" preserveAspectRatio="none"></svg>
          <div class="tooltip" id="tooltip"></div>
        </div>
        <div class="note">เส้น edge คือ proxy จากการเชื่อมจุดวัดที่อยู่ในคลอง/แม่น้ำเดียวกัน ไม่ใช่ปริมาตรน้ำหรือ flow จริงในคลอง</div>
      </div>
      <div class="panel detail">
        <div class="station-detail" id="stationDetail"></div>
        <div class="chart-box">
          <div class="panel-title">Time-series รายจุด</div>
          <canvas id="historyCanvas" width="640" height="210"></canvas>
        </div>
        <div class="table-wrap">
          <table>
            <thead><tr><th>สถานี</th><th>คลอง/เขต</th><th>ระดับน้ำ</th><th>สถานะ</th></tr></thead>
            <tbody id="stationRows"></tbody>
          </table>
        </div>
      </div>
    </section>
  </main>
  <script>
    const data = JSON.parse(document.getElementById('waterPayload').textContent);
    const state = {{ selectedId: null, filterText: '', river: '', status: '' }};
    const svg = document.getElementById('mapSvg');
    const tooltip = document.getElementById('tooltip');
    const stationById = new Map(data.stations.map(s => [String(s.station_id), s]));

    const colors = {{ normal: '#1f9f7a', warning: '#d78b24', critical: '#c9344d', offline: '#6f7b81', unknown: '#8b9692' }};
    const lats = data.stations.map(s => s.lat).filter(Number.isFinite);
    const lons = data.stations.map(s => s.lon).filter(Number.isFinite);
    const bounds = {{ minLat: Math.min(...lats), maxLat: Math.max(...lats), minLon: Math.min(...lons), maxLon: Math.max(...lons) }};
    const pad = 34;
    function x(lon) {{ return pad + ((lon - bounds.minLon) / (bounds.maxLon - bounds.minLon || 1)) * (960 - pad * 2); }}
    function y(lat) {{ return 610 - pad - ((lat - bounds.minLat) / (bounds.maxLat - bounds.minLat || 1)) * (610 - pad * 2); }}
    function statusOf(s) {{ return s.measurement?.status?.alert_level || 'unknown'; }}
    function levelOf(s) {{ return s.measurement?.water_levels_m_msl?.wl_in; }}
    function fmt(v, digits = 2) {{ return Number.isFinite(v) ? v.toFixed(digits) : '-'; }}
    function matches(s) {{
      const q = state.filterText;
      const status = statusOf(s);
      const blob = [s.station_code, s.station_name_th, s.station_short_name_th, s.river_name_th, s.district_name_th].join(' ').toLowerCase();
      return (!q || blob.includes(q)) && (!state.river || s.river_name_th === state.river) && (!state.status || status === state.status);
    }}
    function visibleStations() {{ return data.stations.filter(matches); }}

    function init() {{
      document.getElementById('metaLine').textContent = `${{data.metadata.station_count_catalog}} catalog stations · ${{data.metadata.edge_count}} edges · ${{data.metadata.history_station_count}} history files · ${{data.metadata.history_total_points.toLocaleString()}} history points`;
      const counts = data.summary.alert_level_counts || {{}};
      const stats = [
        ['Catalog stations', data.metadata.station_count_catalog],
        ['Latest stations', data.metadata.station_count_latest],
        ['Edges', data.metadata.edge_count],
        ['History points', data.metadata.history_total_points.toLocaleString()],
        ['Normal', counts.normal || 0],
        ['Offline', counts.offline || 0],
      ];
      document.getElementById('stats').innerHTML = stats.map(([label, value]) => `<div class="stat"><div class="label">${{label}}</div><div class="value">${{value}}</div></div>`).join('');
      const rivers = [...new Set(data.stations.map(s => s.river_name_th).filter(Boolean))].sort((a,b) => a.localeCompare(b, 'th'));
      document.getElementById('riverSelect').insertAdjacentHTML('beforeend', rivers.map(r => `<option value="${{r}}">${{r}}</option>`).join(''));
      document.getElementById('searchBox').addEventListener('input', e => {{ state.filterText = e.target.value.trim().toLowerCase(); render(); }});
      document.getElementById('riverSelect').addEventListener('change', e => {{ state.river = e.target.value; render(); }});
      document.getElementById('statusSelect').addEventListener('change', e => {{ state.status = e.target.value; render(); }});
      state.selectedId = String(data.stations[0]?.station_id || '');
      render();
    }}

    function edgeColor(edge) {{
      const risk = edge.proxy?.risk_score ?? 0;
      if (risk >= 0.85) return colors.critical;
      if (risk >= 0.6) return colors.warning;
      if (risk >= 0.45) return colors.offline;
      return '#4b9fba';
    }}

    function renderMap(stations) {{
      const visibleIds = new Set(stations.map(s => String(s.station_id)));
      const edgeEls = data.edges
        .filter(e => visibleIds.has(String(e.from_station_id)) || visibleIds.has(String(e.to_station_id)))
        .map(e => {{
          const [a, b] = e.geometry.coordinates;
          const width = 1.3 + Math.min(4, (e.proxy?.risk_score || 0) * 4);
          return `<line class="edge" x1="${{x(a[0])}}" y1="${{y(a[1])}}" x2="${{x(b[0])}}" y2="${{y(b[1])}}" stroke="${{edgeColor(e)}}" stroke-width="${{width}}"><title>${{e.river_name_th}} · risk ${{fmt(e.proxy?.risk_score, 2)}} · avg ${{fmt(e.proxy?.water_level_avg_m_msl)}} m</title></line>`;
        }}).join('');
      const stationEls = stations.map(s => {{
        const selected = String(s.station_id) === state.selectedId ? ' selected' : '';
        const radius = selected ? 6 : 4.4;
        return `<circle class="station${{selected}}" data-id="${{s.station_id}}" cx="${{x(s.lon)}}" cy="${{y(s.lat)}}" r="${{radius}}" fill="${{colors[statusOf(s)] || colors.unknown}}"></circle>`;
      }}).join('');
      svg.innerHTML = edgeEls + stationEls;
      svg.querySelectorAll('.station').forEach(el => {{
        el.addEventListener('mousemove', showTooltip);
        el.addEventListener('mouseleave', () => tooltip.style.display = 'none');
        el.addEventListener('click', () => {{ state.selectedId = el.dataset.id; render(); }});
      }});
    }}

    function showTooltip(event) {{
      const s = stationById.get(event.target.dataset.id);
      tooltip.innerHTML = `<strong>${{s.station_short_name_th || s.station_name_th}}</strong><br>${{s.river_name_th || '-'}} · ${{s.district_name_th || '-'}}<br>ระดับน้ำ ${{fmt(levelOf(s))}} ม.รทก. · ${{statusOf(s)}}`;
      tooltip.style.left = `${{event.offsetX + 14}}px`;
      tooltip.style.top = `${{event.offsetY + 14}}px`;
      tooltip.style.display = 'block';
    }}

    function renderTable(stations) {{
      document.getElementById('stationRows').innerHTML = stations.map(s => {{
        const active = String(s.station_id) === state.selectedId ? ' style="background:#eef6f3"' : '';
        return `<tr data-id="${{s.station_id}}"${{active}}><td><strong>${{s.station_short_name_th || s.station_name_th}}</strong><br><span class="sub">${{s.station_code || ''}}</span></td><td>${{s.river_name_th || '-'}}<br><span class="sub">${{s.district_name_th || '-'}}</span></td><td>${{fmt(levelOf(s))}}</td><td>${{statusOf(s)}}</td></tr>`;
      }}).join('');
      document.querySelectorAll('#stationRows tr').forEach(row => row.addEventListener('click', () => {{ state.selectedId = row.dataset.id; render(); }}));
    }}

    function renderDetail() {{
      const s = stationById.get(state.selectedId) || visibleStations()[0] || data.stations[0];
      if (!s) return;
      state.selectedId = String(s.station_id);
      const m = s.measurement || {{}};
      const history = data.histories[String(s.station_id)];
      document.getElementById('stationDetail').innerHTML = `
        <div class="station-name">${{s.station_name_th || s.station_short_name_th}}</div>
        <div class="sub">${{s.river_name_th || '-'}} · ${{s.district_name_th || '-'}} · station ${{s.station_id}}</div>
        <div class="chips">
          <span class="chip">WL ${{fmt(levelOf(s))}} ม.รทก.</span>
          <span class="chip">warning ${{fmt(s.thresholds?.warning_in_m_msl)}}</span>
          <span class="chip">critical ${{fmt(s.thresholds?.critical_in_m_msl)}}</span>
          <span class="chip">${{statusOf(s)}}</span>
          <span class="chip">${{history ? history.series.reduce((n, series) => n + series.point_count, 0).toLocaleString() : 0}} points</span>
        </div>
      `;
      drawHistory(s, history);
    }}

    function drawHistory(station, history) {{
      const canvas = document.getElementById('historyCanvas');
      const ctx = canvas.getContext('2d');
      const w = canvas.width, h = canvas.height;
      ctx.clearRect(0, 0, w, h);
      ctx.fillStyle = '#ffffff';
      ctx.fillRect(0, 0, w, h);
      ctx.strokeStyle = '#d9e2df';
      ctx.lineWidth = 1;
      for (let i = 0; i < 5; i++) {{
        const yy = 18 + i * ((h - 40) / 4);
        ctx.beginPath(); ctx.moveTo(40, yy); ctx.lineTo(w - 12, yy); ctx.stroke();
      }}
      if (!history || !history.series.length) {{
        ctx.fillStyle = '#63716c'; ctx.fillText('ไม่มี history สำหรับสถานีนี้', 42, 34); return;
      }}
      const all = history.series.flatMap(series => series.points.map(p => p[1])).filter(Number.isFinite);
      if (!all.length) return;
      const min = Math.min(...all), max = Math.max(...all);
      const yv = value => h - 24 - ((value - min) / (max - min || 1)) * (h - 46);
      const palette = ['#1b6b9b', '#d78b24', '#6b4ea0'];
      history.series.forEach((series, idx) => {{
        const pts = series.points;
        const step = Math.max(1, Math.floor(pts.length / 480));
        ctx.strokeStyle = palette[idx % palette.length];
        ctx.lineWidth = 1.8;
        ctx.beginPath();
        let drawn = 0;
        for (let i = 0; i < pts.length; i += step) {{
          const xx = 42 + (i / Math.max(1, pts.length - 1)) * (w - 58);
          const yy = yv(pts[i][1]);
          if (!drawn) ctx.moveTo(xx, yy); else ctx.lineTo(xx, yy);
          drawn++;
        }}
        ctx.stroke();
      }});
      ctx.fillStyle = '#63716c';
      ctx.font = '12px system-ui';
      ctx.fillText(`min ${{fmt(min)}} · max ${{fmt(max)}} ม.รทก.`, 42, 16);
    }}

    function render() {{
      const stations = visibleStations();
      document.getElementById('visibleCount').textContent = `${{stations.length}} visible stations`;
      if (!stations.some(s => String(s.station_id) === state.selectedId) && stations[0]) state.selectedId = String(stations[0].station_id);
      renderMap(stations);
      renderTable(stations);
      renderDetail();
    }}
    init();
  </script>
</body>
</html>
"""


def build_dashboard_html(payload: dict[str, Any]) -> str:
    template_path = Path(__file__).with_name("visualization-reference") / "water_dashboard_template.html"
    template = template_path.read_text(encoding="utf-8")
    return template.replace("__WATER_PAYLOAD__", html_escape_json(payload))


def command_build(args: argparse.Namespace) -> None:
    output_dir = Path(args.output_dir)
    latest = read_json(args.latest_json)
    catalog = read_json(args.catalog_json)
    histories = load_histories(args.history_dir)
    all_stations = build_all_station_catalog(catalog, latest)
    write_json(output_dir / "water_all_stations.json", all_stations)

    edges, edge_summary = build_edges(all_stations, latest)
    write_json(output_dir / "water_edges.json", {"metadata": edge_summary["metadata"], "edges": edges})
    write_json(output_dir / "water_edges_geojson.json", edges_geojson(edges))
    write_json(output_dir / "water_edge_summary.json", edge_summary)

    payload = build_viz_payload(latest, all_stations, edges, edge_summary, histories)
    write_json(output_dir / "water_viz_payload.json", payload)
    write_text(output_dir / "visualization-reference" / "water_dashboard.html", build_dashboard_html(payload))


def build_parser() -> argparse.ArgumentParser:
    _here = Path(__file__).parent
    _root = _here.parent
    _wd   = _root / "water-data"
    parser = argparse.ArgumentParser(description="Build Bangkok water edge and visualization artifacts.")
    parser.add_argument("--latest-json", default=str(_wd / "water_latest_snapshot.json"))
    parser.add_argument("--catalog-json", default=str(_wd / "water_catalog.json"))
    parser.add_argument("--history-dir",  default=str(_wd / "station_histories"))
    parser.add_argument("--output-dir",   default=str(_wd))
    parser.set_defaults(func=command_build)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
