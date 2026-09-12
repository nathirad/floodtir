#!/usr/bin/env python3
"""
Bangkok DDS water-level scraper.

Sources:
- Latest/polling data: POST https://weather.bangkok.go.th/water/PageMap/GoogleMap
- Station catalog: GET https://weather.bangkok.go.th/water/
- Station history: GET https://weather.bangkok.go.th/water/StationDetail?id={water_id}

The script uses only Python standard library modules so it can run in a small
worker, cron job, or backend service without extra dependencies.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import csv
import hashlib
import json
import math
import re
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener


BASE_URL = "https://weather.bangkok.go.th"
LATEST_URL = f"{BASE_URL}/water/PageMap/GoogleMap"
CATALOG_URL = f"{BASE_URL}/water/"
STATION_DETAIL_URL = f"{BASE_URL}/water/StationDetail?id={{station_id}}"
BANGKOK_TZ = timezone(timedelta(hours=7), name="Asia/Bangkok")
POLL_INTERVAL_SECONDS = 300
POLL_PAYLOAD = "TEST_DATA_GOES_HERE"
ALLOWED_SOURCE_HOST = "weather.bangkok.go.th"
MAX_RESPONSE_BYTES = 25 * 1024 * 1024
MAX_STATION_RECORDS = 5000


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_text(path: str | Path) -> str:
    return Path(path).read_text(encoding="utf-8")


def write_text(path: str | Path | None, text: str, append: bool = False) -> None:
    if path is None or str(path) == "-":
        sys.stdout.write(text)
        if not text.endswith("\n"):
            sys.stdout.write("\n")
        return
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if append else "w"
    with target.open(mode, encoding="utf-8") as file:
        file.write(text)
        if not text.endswith("\n"):
            file.write("\n")


def validate_source_url(url: str) -> None:
    parsed = urlparse(url)
    if (
        parsed.scheme != "https"
        or (parsed.hostname or "").lower() != ALLOWED_SOURCE_HOST
        or parsed.username
        or parsed.password
    ):
        raise ValueError(f"Blocked non-allowlisted source URL: {url}")


class AllowlistedRedirectHandler(HTTPRedirectHandler):
    def redirect_request(
        self,
        req: Any,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> Any:
        validate_source_url(newurl)
        return super().redirect_request(
            req,
            fp,
            code,
            msg,
            headers,
            newurl,
        )


SOURCE_OPENER = build_opener(AllowlistedRedirectHandler())


def read_http_response(
    response: Any,
    expected_content_types: tuple[str, ...],
) -> str:
    final_url = response.geturl()
    validate_source_url(final_url)
    content_type = response.headers.get_content_type()
    if content_type and content_type not in expected_content_types:
        raise ValueError(f"Unexpected Content-Type: {content_type}")
    content_length = response.headers.get("Content-Length")
    if content_length:
        try:
            declared_size = int(content_length)
        except ValueError as exc:
            raise ValueError("Invalid Content-Length header") from exc
        if declared_size > MAX_RESPONSE_BYTES:
            raise ValueError("Response exceeds maximum allowed size")
    body = response.read(MAX_RESPONSE_BYTES + 1)
    if len(body) > MAX_RESPONSE_BYTES:
        raise ValueError("Response exceeds maximum allowed size")
    return body.decode("utf-8", errors="strict")


def source_response_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def http_get(url: str, timeout: int = 40) -> str:
    validate_source_url(url)
    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 bangkok-water-data/1.0",
            "Accept": "text/html,application/json;q=0.9,*/*;q=0.8",
        },
    )
    with SOURCE_OPENER.open(request, timeout=timeout) as response:
        return read_http_response(
            response,
            ("text/html", "application/json", "text/plain"),
        )


def http_post_form(url: str, data: dict[str, str], timeout: int = 90) -> str:
    validate_source_url(url)
    encoded = urlencode(data).encode("utf-8")
    request = Request(
        url,
        data=encoded,
        headers={
            "User-Agent": "Mozilla/5.0 bangkok-water-data/1.0",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Accept": "application/json,text/javascript,*/*;q=0.8",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": CATALOG_URL,
        },
        method="POST",
    )
    with SOURCE_OPENER.open(request, timeout=timeout) as response:
        return read_http_response(
            response,
            ("application/json", "text/json", "text/plain", "text/html"),
        )


def load_json_from_file_or_text(value: str) -> Any:
    return json.loads(value)


def find_balanced_array_after(text: str, marker: str) -> str:
    start_marker = text.find(marker)
    if start_marker < 0:
        raise ValueError(f"Cannot find marker: {marker}")

    start = text.find("[", start_marker)
    if start < 0:
        raise ValueError(f"Cannot find array after marker: {marker}")

    depth = 0
    in_string = False
    escape = False
    quote = ""

    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == quote:
                in_string = False
            continue

        if char in ("'", '"'):
            in_string = True
            quote = char
            continue

        if char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]

    raise ValueError(f"Cannot find balanced array end after marker: {marker}")


def parse_catalog_html(html: str) -> list[dict[str, Any]]:
    raw = find_balanced_array_after(html, "const allData")
    return json.loads(raw)


def clean_level(value: Any) -> float | None:
    if value is None:
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if numeric <= -90:
        return None
    return numeric


def clean_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return numeric if math.isfinite(numeric) else None


def clean_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def parse_bangkok_time(value: str | None) -> str | None:
    if not value:
        return None
    for pattern in ("%Y/%m/%d %H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            parsed = datetime.strptime(value, pattern)
            return parsed.replace(tzinfo=BANGKOK_TZ).isoformat()
        except ValueError:
            continue
    return None


def parse_dotnet_date(value: str | None) -> str | None:
    if not value:
        return None
    match = re.search(r"/Date\((\d+)\)/", value)
    if not match:
        return None
    timestamp_ms = int(match.group(1))
    return datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def alert_level(record: dict[str, Any]) -> str:
    priority = clean_int(record.get("priorityStatus"))
    text = str(record.get("txtStatus_en") or record.get("txtStatus") or "").lower()
    if priority == 4 or "critical" in text or "flood" in text or record.get("txtStatus") == "น้ำท่วม":
        return "critical"
    if priority == 3 or "warning" in text or record.get("txtStatus") == "น้ำท่วมขังเล็กน้อย":
        return "warning"
    if priority == 2 or "normal" in text or record.get("txtStatus") == "ปกติ":
        return "normal"
    if priority in (0, 1) or "out of order" in text or "failed" in text or "ขัดข้อง" in str(record.get("txtStatus")):
        return "offline"
    return "unknown"


def station_identity(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "station_id": clean_int(record.get("water_id")),
        "station_code": record.get("water_code"),
        "station_name_th": record.get("water_name"),
        "station_name_en": record.get("water_name_en"),
        "station_short_name_th": record.get("water_shortname"),
        "station_short_name_en": record.get("water_shortname_en"),
        "river_id": clean_int(record.get("river_id")),
        "river_name_th": record.get("river_name"),
        "river_name_en": record.get("river_name_en"),
        "district_id": clean_int(record.get("district_id")),
        "district_name_th": record.get("district_name") or record.get("name"),
        "district_name_en": record.get("district_name_en"),
        "water_system_id": clean_int(record.get("water_system_id")),
        "water_count": clean_int(record.get("water_count")),
        "water_gate_count": clean_int(record.get("water_gate_count")),
        "water_url": record.get("water_url"),
    }


def station_feature_identity(station: dict[str, Any]) -> dict[str, Any]:
    return {
        "station_id": station.get("station_id"),
        "station_code": station.get("station_code"),
        "station_name_th": station.get("station_name_th"),
        "station_name_en": station.get("station_name_en"),
        "station_short_name_th": station.get("station_short_name_th"),
        "station_short_name_en": station.get("station_short_name_en"),
        "river_id": station.get("river_id"),
        "river_name_th": station.get("river_name_th"),
        "river_name_en": station.get("river_name_en"),
        "district_id": station.get("district_id"),
        "district_name_th": station.get("district_name_th"),
        "district_name_en": station.get("district_name_en"),
    }


def normalize_station(record: dict[str, Any]) -> dict[str, Any]:
    station = station_identity(record)
    station.update(
        {
            "location": {
                "latitude": clean_float(record.get("latitude")),
                "longitude": clean_float(record.get("longitude")),
            },
            "levels": {
                "water_min_m_msl": clean_float(record.get("water_min")),
                "water_max_m_msl": clean_float(record.get("water_max")),
                "bed_bank_m_msl": clean_float(record.get("bed_bank")),
                "left_bank_m_msl": clean_float(record.get("left_bank")),
                "right_bank_m_msl": clean_float(record.get("right_bank")),
                "control_m_msl": clean_float(record.get("water_control")),
            },
            "thresholds": {
                "warning_in_m_msl": clean_float(record.get("warning")),
                "critical_in_m_msl": clean_float(record.get("critical")),
                "warning_out01_m_msl": clean_float(record.get("warning_out01")),
                "critical_out01_m_msl": clean_float(record.get("critical_out01")),
                "warning_out02_m_msl": clean_float(record.get("warning_out02")),
                "critical_out02_m_msl": clean_float(record.get("critical_out02")),
            },
            "flags": {
                "station_status": record.get("station_status"),
                "export_dss": record.get("export_dss"),
                "adjust": record.get("adjust"),
                "status": record.get("status"),
            },
        }
    )
    return station


def normalize_measurement(record: dict[str, Any]) -> dict[str, Any]:
    observed_at = parse_bangkok_time(record.get("site_timestampEN"))
    embedded_last = record.get("water_level_last") or {}
    if not observed_at and embedded_last:
        observed_at = parse_bangkok_time(embedded_last.get("site_timestamp"))

    return {
        "station_id": clean_int(record.get("water_id")),
        "observed_at": observed_at,
        "observed_at_utc_from_dotnet": parse_dotnet_date(record.get("site_timestamp")),
        "observed_at_th": record.get("site_timestampTH"),
        "minutes_from_latest_poll": clean_int(record.get("datediffnow")),
        "status": {
            "alert_level": alert_level(record),
            "priority": clean_int(record.get("priorityStatus")),
            "status_code": clean_int(record.get("status")),
            "status_color": record.get("colorStatus") or record.get("statusColor"),
            "status_text_th": record.get("txtStatus"),
            "status_text_en": record.get("txtStatus_en"),
        },
        "water_levels_m_msl": {
            "wl_in": clean_level(record.get("wl_in")),
            "wl_out01": clean_level(record.get("wl_out01")),
            "wl_out02": clean_level(record.get("wl_out02")),
            "wl_level": clean_level(record.get("wl_level")),
        },
        "daily_max_m_msl": {
            "max_in_day": clean_level(record.get("max_in_day")),
            "max_in_yesterday": clean_level(record.get("max_in_yesterday")),
            "max_out01_day": clean_level(record.get("max_out01_day")),
            "max_out01_yesterday": clean_level(record.get("max_out01_yesterday")),
            "max_out02_day": clean_level(record.get("max_out02_day")),
            "max_out02_yesterday": clean_level(record.get("max_out02_yesterday")),
        },
        "gate_opening_m": {
            "gate01": clean_level(record.get("watergate01")),
            "gate02": clean_level(record.get("watergate02")),
            "gate03": clean_level(record.get("watergate03")),
            "gate04": clean_level(record.get("watergate04")),
            "gate05": clean_level(record.get("watergate05")),
            "gate06": clean_level(record.get("watergate06")),
        },
    }


def normalize_latest(records: list[dict[str, Any]], source_url: str = LATEST_URL) -> dict[str, Any]:
    stations = [normalize_station(record) for record in records]
    measurements = [normalize_measurement(record) for record in records]
    by_station_id = {station["station_id"]: station for station in stations}

    features = []
    for station, measurement in zip(stations, measurements):
        lat = station["location"]["latitude"]
        lon = station["location"]["longitude"]
        if lat is None or lon is None:
            continue
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
                "properties": {
                    **station_feature_identity(station),
                    "observed_at": measurement["observed_at"],
                    "alert_level": measurement["status"]["alert_level"],
                    "status_text_th": measurement["status"]["status_text_th"],
                    "status_text_en": measurement["status"]["status_text_en"],
                    "status_color": measurement["status"]["status_color"],
                    "wl_in_m_msl": measurement["water_levels_m_msl"]["wl_in"],
                    "wl_out01_m_msl": measurement["water_levels_m_msl"]["wl_out01"],
                    "wl_out02_m_msl": measurement["water_levels_m_msl"]["wl_out02"],
                    "warning_in_m_msl": station["thresholds"]["warning_in_m_msl"],
                    "critical_in_m_msl": station["thresholds"]["critical_in_m_msl"],
                    "water_system_id": station["water_system_id"],
                },
            }
        )

    return {
        "metadata": {
            "source_url": source_url,
            "scraped_at": now_utc(),
            "recommended_poll_interval_seconds": POLL_INTERVAL_SECONDS,
            "timezone": "Asia/Bangkok",
            "record_count": len(records),
        },
        "summary": summarize(stations, measurements),
        "stations": stations,
        "measurements": measurements,
        "geojson": {"type": "FeatureCollection", "features": features},
        "stations_by_id": {str(key): value for key, value in by_station_id.items() if key is not None},
    }


def summarize(stations: list[dict[str, Any]], measurements: list[dict[str, Any]]) -> dict[str, Any]:
    alert_counter = Counter(m["status"]["alert_level"] for m in measurements)
    status_counter = Counter(m["status"]["status_text_en"] or m["status"]["status_text_th"] or "unknown" for m in measurements)
    system_counter = Counter(str(s["water_system_id"] or "unknown") for s in stations)
    district_counter = Counter(s["district_name_en"] or s["district_name_th"] or "unknown" for s in stations)
    river_counter = Counter(s["river_name_en"] or s["river_name_th"] or "unknown" for s in stations)
    stale_15 = sum(1 for m in measurements if (m["minutes_from_latest_poll"] or 0) >= 15)
    stale_30 = sum(1 for m in measurements if (m["minutes_from_latest_poll"] or 0) >= 30)

    observed_values = [m["observed_at"] for m in measurements if m.get("observed_at")]

    return {
        "total_stations": len(stations),
        "alert_level_counts": dict(sorted(alert_counter.items())),
        "status_counts": dict(status_counter.most_common()),
        "water_system_counts": dict(sorted(system_counter.items())),
        "top_district_counts": dict(district_counter.most_common(20)),
        "top_river_counts": dict(river_counter.most_common(20)),
        "stale_counts": {
            "at_least_15_minutes": stale_15,
            "at_least_30_minutes": stale_30,
        },
        "observed_at_min": min(observed_values) if observed_values else None,
        "observed_at_max": max(observed_values) if observed_values else None,
    }


def parse_latest_json(text: str) -> list[dict[str, Any]]:
    data = json.loads(text)
    if not isinstance(data, list):
        raise ValueError("Latest endpoint did not return a JSON array.")
    validate_station_records(data, "latest")
    return data


def validate_station_records(
    records: list[Any],
    source_kind: str,
) -> None:
    if not records:
        raise ValueError(f"{source_kind} source returned no station records")
    if len(records) > MAX_STATION_RECORDS:
        raise ValueError(f"{source_kind} source returned too many records")
    station_ids = []
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise ValueError(
                f"{source_kind} record {index} is not an object"
            )
        station_id = clean_int(record.get("water_id"))
        if station_id is None or station_id < 1:
            raise ValueError(
                f"{source_kind} record {index} has invalid water_id"
            )
        station_ids.append(station_id)
        raw_latitude = record.get("latitude")
        raw_longitude = record.get("longitude")
        latitude = clean_float(raw_latitude)
        longitude = clean_float(raw_longitude)
        if raw_latitude not in (None, "") and latitude is None:
            raise ValueError(
                f"{source_kind} station {station_id} has invalid latitude"
            )
        if raw_longitude not in (None, "") and longitude is None:
            raise ValueError(
                f"{source_kind} station {station_id} has invalid longitude"
            )
        if latitude is not None and not (-90 <= latitude <= 90):
            raise ValueError(
                f"{source_kind} station {station_id} has invalid latitude"
            )
        if longitude is not None and not (-180 <= longitude <= 180):
            raise ValueError(
                f"{source_kind} station {station_id} has invalid longitude"
            )
    if len(station_ids) != len(set(station_ids)):
        raise ValueError(f"{source_kind} source contains duplicate water_id")


def parse_station_history_html(html: str, station_id: int | None = None) -> dict[str, Any]:
    source_series = []
    series_marker = "series:"
    search_from = 0

    while True:
        marker_index = html.find(series_marker, search_from)
        if marker_index < 0:
            break
        try:
            raw_series = find_balanced_array_after(html[marker_index:], series_marker)
        except ValueError:
            search_from = marker_index + len(series_marker)
            continue
        series_objects = split_top_level_objects(raw_series)
        if series_objects:
            for series_object in series_objects:
                points = parse_date_utc_points(series_object)
                if points:
                    source_series.append((series_object, points))
        else:
            points = parse_date_utc_points(raw_series)
            if points:
                source_series.append((raw_series, points))
        search_from = marker_index + len(series_marker)

    series = []
    seen = set()
    for index, (raw, points) in enumerate(source_series):
        name_expr = None
        name_match = re.search(r"name\s*:\s*([^,\n]+)", raw)
        if name_match:
            name_expr = name_match.group(1).strip().strip("'\"")
        signature = (
            name_expr,
            len(points),
            points[0]["observed_at_utc"],
            points[-1]["observed_at_utc"],
            points[0]["value_m_msl"],
            points[-1]["value_m_msl"],
        )
        if signature in seen:
            continue
        seen.add(signature)
        series.append(
            {
                "series_index": len(series),
                "name_expression": name_expr,
                "unit": "m.MSL",
                "point_count": len(points),
                "points": points,
            }
        )

    return {
        "metadata": {
            "source": "StationDetail HTML Highcharts Date.UTC data",
            "station_id": station_id,
            "scraped_at": now_utc(),
            "timezone_note": "Timestamps are extracted from JavaScript Date.UTC calls and kept as UTC.",
            "series_count": len(series),
        },
        "series": series,
    }


def split_top_level_objects(array_text: str) -> list[str]:
    objects = []
    depth = 0
    in_string = False
    escape = False
    quote = ""
    start = None

    for index, char in enumerate(array_text):
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == quote:
                in_string = False
            continue

        if char in ("'", '"'):
            in_string = True
            quote = char
            continue

        if char == "{":
            if depth == 0:
                start = index
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0 and start is not None:
                objects.append(array_text[start : index + 1])
                start = None

    return objects


def parse_date_utc_points(text: str) -> list[dict[str, Any]]:
    pattern = re.compile(
        r"\[\s*Date\.UTC\(\s*"
        r"(?P<year>\d{4})\s*,\s*(?P<month>\d{1,2})\s*,\s*(?P<day>\d{1,2})\s*,\s*"
        r"(?P<hour>\d{1,2})\s*,\s*(?P<minute>\d{1,2})\s*,\s*(?P<second>\d{1,2})\s*"
        r"\)\s*,\s*(?P<value>-?\d+(?:\.\d+)?)\s*\]"
    )
    points = []
    for match in pattern.finditer(text):
        year = int(match.group("year"))
        month = int(match.group("month")) + 1
        day = int(match.group("day"))
        hour = int(match.group("hour"))
        minute = int(match.group("minute"))
        second = int(match.group("second"))
        observed = datetime(year, month, day, hour, minute, second, tzinfo=timezone.utc)
        points.append(
            {
                "observed_at_utc": observed.isoformat().replace("+00:00", "Z"),
                "value_m_msl": float(match.group("value")),
            }
        )
    return points


def emit_json(data: Any, output: str | None, append: bool = False) -> None:
    write_text(output, json.dumps(data, ensure_ascii=False, indent=None if append else 2), append=append)


def emit_jsonl(records: list[dict[str, Any]], output: str | None, append: bool = False) -> None:
    lines = "\n".join(json.dumps(record, ensure_ascii=False, separators=(",", ":")) for record in records)
    write_text(output, lines, append=append)


def emit_csv(records: list[dict[str, Any]], output: str | None) -> None:
    if not records:
        write_text(output, "")
        return

    rows = [flatten(record) for record in records]
    fieldnames = sorted({key for row in rows for key in row})

    if output is None or output == "-":
        file = sys.stdout
        close = False
    else:
        target = Path(output)
        target.parent.mkdir(parents=True, exist_ok=True)
        file = target.open("w", encoding="utf-8", newline="")
        close = True
    try:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    finally:
        if close:
            file.close()


def flatten(data: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    flat = {}
    for key, value in data.items():
        next_key = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            flat.update(flatten(value, next_key))
        else:
            flat[next_key] = value
    return flat


def output_latest(normalized: dict[str, Any], args: argparse.Namespace) -> None:
    if args.format == "full":
        emit_json(normalized, args.output, append=args.append)
    elif args.format == "measurements-jsonl":
        emit_jsonl(normalized["measurements"], args.output, append=args.append)
    elif args.format == "stations-json":
        emit_json(normalized["stations"], args.output, append=args.append)
    elif args.format == "geojson":
        emit_json(normalized["geojson"], args.output, append=args.append)
    elif args.format == "csv":
        emit_csv(normalized["measurements"], args.output)
    else:
        raise ValueError(f"Unsupported format: {args.format}")


def command_latest(args: argparse.Namespace) -> None:
    if args.input_json:
        text = read_text(args.input_json)
    else:
        text = http_post_form(LATEST_URL, {"payload": POLL_PAYLOAD}, timeout=args.timeout)
    records = parse_latest_json(text)
    normalized = normalize_latest(records)
    normalized["metadata"]["source_response_sha256"] = (
        source_response_sha256(text)
    )
    normalized["metadata"]["source_mode"] = (
        "saved_input" if args.input_json else "https_fetch"
    )
    output_latest(normalized, args)


def command_poll(args: argparse.Namespace) -> None:
    interval = args.interval_seconds
    iterations = args.iterations
    count = 0
    while iterations is None or count < iterations:
        text = http_post_form(LATEST_URL, {"payload": POLL_PAYLOAD}, timeout=args.timeout)
        records = parse_latest_json(text)
        normalized = normalize_latest(records)
        normalized["metadata"]["source_response_sha256"] = (
            source_response_sha256(text)
        )
        normalized["metadata"]["source_mode"] = "https_fetch"
        normalized["metadata"]["poll_iteration"] = count + 1
        output_latest(normalized, args)
        count += 1
        if iterations is not None and count >= iterations:
            break
        time.sleep(interval)


def command_catalog(args: argparse.Namespace) -> None:
    html = read_text(args.input_html) if args.input_html else http_get(CATALOG_URL, timeout=args.timeout)
    records = parse_catalog_html(html)
    validate_station_records(records, "catalog")
    stations = [normalize_station(record) for record in records]
    result = {
        "metadata": {
            "source_url": CATALOG_URL,
            "scraped_at": now_utc(),
            "record_count": len(stations),
            "source_response_sha256": source_response_sha256(html),
            "source_mode": (
                "saved_input" if args.input_html else "https_fetch"
            ),
            "note": "Catalog comes from the JavaScript const allData embedded in /water/.",
        },
        "stations": stations,
    }
    if args.format == "json":
        emit_json(result, args.output)
    elif args.format == "csv":
        emit_csv(stations, args.output)
    else:
        raise ValueError(f"Unsupported format: {args.format}")


def command_station_history(args: argparse.Namespace) -> None:
    if args.input_html:
        html = read_text(args.input_html)
        source_url = None
    else:
        source_url = STATION_DETAIL_URL.format(station_id=args.station_id)
        html = http_get(source_url, timeout=args.timeout)
    result = parse_station_history_html(html, station_id=args.station_id)
    if not result["series"]:
        raise ValueError(
            f"No history series found for station_id={args.station_id}"
        )
    result["metadata"]["source_response_sha256"] = source_response_sha256(
        html
    )
    result["metadata"]["source_mode"] = (
        "saved_input" if args.input_html else "https_fetch"
    )
    if source_url:
        result["metadata"]["source_url"] = source_url
    emit_json(result, args.output)


def existing_history_is_valid(
    path: Path,
    expected_station_id: int | None = None,
) -> bool:
    if not path.exists():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    series = data.get("series")
    metadata = data.get("metadata")
    return (
        isinstance(series, list)
        and bool(series)
        and isinstance(metadata, dict)
        and (
            expected_station_id is None
            or metadata.get("station_id") == expected_station_id
        )
    )


def station_ids_from_catalog(path: str | Path) -> list[int]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    stations = data.get("stations", data if isinstance(data, list) else [])
    station_ids = []
    for station in stations:
        station_id = clean_int(station.get("station_id") or station.get("water_id"))
        if station_id is not None:
            station_ids.append(station_id)
    return sorted(dict.fromkeys(station_ids))


def fetch_one_station_history(
    station_id: int,
    output_dir: Path,
    timeout: int,
    retries: int,
    force: bool,
) -> dict[str, Any]:
    output_path = output_dir / f"{station_id}.json"
    if not force and existing_history_is_valid(output_path, station_id):
        data = json.loads(output_path.read_text(encoding="utf-8"))
        point_count = sum(series.get("point_count", 0) for series in data.get("series", []))
        return {
            "station_id": station_id,
            "status": "skipped",
            "path": str(output_path),
            "series_count": len(data.get("series", [])),
            "point_count": point_count,
            "error": None,
        }

    last_error = None
    url = STATION_DETAIL_URL.format(station_id=station_id)
    for attempt in range(retries + 1):
        try:
            html = http_get(url, timeout=timeout)
            result = parse_station_history_html(html, station_id=station_id)
            if not result["series"]:
                raise ValueError(
                    f"No history series found for station_id={station_id}"
                )
            result["metadata"]["source_url"] = url
            result["metadata"]["source_response_sha256"] = (
                source_response_sha256(html)
            )
            result["metadata"]["source_mode"] = "https_fetch"
            emit_json(result, str(output_path))
            point_count = sum(series.get("point_count", 0) for series in result.get("series", []))
            return {
                "station_id": station_id,
                "status": "fetched",
                "path": str(output_path),
                "series_count": len(result.get("series", [])),
                "point_count": point_count,
                "error": None,
            }
        except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
            last_error = str(exc)
            if attempt < retries:
                time.sleep(1 + attempt)

    return {
        "station_id": station_id,
        "status": "failed",
        "path": str(output_path),
        "series_count": 0,
        "point_count": 0,
        "error": last_error,
    }


def command_station_histories(args: argparse.Namespace) -> None:
    station_ids = station_ids_from_catalog(args.catalog_json)
    if args.limit:
        station_ids = station_ids[: args.limit]

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = Path(args.manifest) if args.manifest else output_dir.parent / "station_histories_manifest.json"

    results = []
    started_at = now_utc()
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = []
        for station_id in station_ids:
            futures.append(
                executor.submit(
                    fetch_one_station_history,
                    station_id,
                    output_dir,
                    args.timeout,
                    args.retries,
                    args.force,
                )
            )
            if args.submit_delay_seconds:
                time.sleep(args.submit_delay_seconds)

        for index, future in enumerate(concurrent.futures.as_completed(futures), start=1):
            result = future.result()
            results.append(result)
            print(
                f"[{index}/{len(futures)}] {result['status']} station_id={result['station_id']} "
                f"series={result['series_count']} points={result['point_count']}",
                file=sys.stderr,
            )

    status_counts = Counter(result["status"] for result in results)
    manifest = {
        "metadata": {
            "source": "StationDetail bulk scrape",
            "catalog_json": args.catalog_json,
            "output_dir": str(output_dir),
            "started_at": started_at,
            "finished_at": now_utc(),
            "requested_count": len(station_ids),
            "workers": args.workers,
            "timeout_seconds": args.timeout,
            "retries": args.retries,
        },
        "summary": {
            "status_counts": dict(sorted(status_counts.items())),
            "files_written_or_valid": sum(1 for result in results if result["status"] in {"fetched", "skipped"}),
            "failed_count": status_counts.get("failed", 0),
            "zero_point_count": sum(1 for result in results if result["status"] != "failed" and result["point_count"] == 0),
            "total_points": sum(result["point_count"] for result in results),
        },
        "results": sorted(results, key=lambda item: item["station_id"]),
    }
    emit_json(manifest, str(manifest_path))
    if status_counts.get("failed", 0):
        raise ValueError(f"{status_counts['failed']} station histories failed. See {manifest_path}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Scrape Bangkok DDS water-level data.")
    sub = parser.add_subparsers(dest="command", required=True)

    latest = sub.add_parser("latest", help="Fetch or parse the latest water-level snapshot.")
    latest.add_argument("--input-json", help="Parse an existing PageMap/GoogleMap JSON file instead of fetching.")
    latest.add_argument("--output", "-o", help="Output path. Defaults to stdout.")
    latest.add_argument("--format", choices=["full", "measurements-jsonl", "stations-json", "geojson", "csv"], default="full")
    latest.add_argument("--append", action="store_true", help="Append output instead of overwriting.")
    latest.add_argument("--timeout", type=int, default=90)
    latest.set_defaults(func=command_latest)

    poll = sub.add_parser("poll", help="Poll latest data every interval and append snapshots.")
    poll.add_argument("--output", "-o", required=True)
    poll.add_argument("--format", choices=["full", "measurements-jsonl", "geojson"], default="full")
    poll.add_argument("--append", action="store_true", default=True)
    poll.add_argument("--interval-seconds", type=int, default=POLL_INTERVAL_SECONDS)
    poll.add_argument("--iterations", type=int, help="Stop after N polls. Omit to run forever.")
    poll.add_argument("--timeout", type=int, default=90)
    poll.set_defaults(func=command_poll)

    catalog = sub.add_parser("catalog", help="Fetch or parse the station catalog from /water/.")
    catalog.add_argument("--input-html", help="Parse an existing /water/ HTML file instead of fetching.")
    catalog.add_argument("--output", "-o", help="Output path. Defaults to stdout.")
    catalog.add_argument("--format", choices=["json", "csv"], default="json")
    catalog.add_argument("--timeout", type=int, default=40)
    catalog.set_defaults(func=command_catalog)

    history = sub.add_parser("station-history", help="Fetch or parse StationDetail Highcharts history.")
    history.add_argument("--station-id", type=int, required=True)
    history.add_argument("--input-html", help="Parse an existing StationDetail HTML file instead of fetching.")
    history.add_argument("--output", "-o", help="Output path. Defaults to stdout.")
    history.add_argument("--timeout", type=int, default=40)
    history.set_defaults(func=command_station_history)

    histories = sub.add_parser("station-histories", help="Bulk fetch StationDetail histories from catalog station ids.")
    histories.add_argument("--catalog-json", required=True)
    histories.add_argument("--output-dir", required=True)
    histories.add_argument("--manifest")
    histories.add_argument("--workers", type=int, default=3)
    histories.add_argument("--timeout", type=int, default=60)
    histories.add_argument("--retries", type=int, default=2)
    histories.add_argument("--limit", type=int)
    histories.add_argument("--submit-delay-seconds", type=float, default=0.15)
    histories.add_argument("--force", action="store_true")
    histories.set_defaults(func=command_station_histories)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.func(args)
        return 0
    except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
