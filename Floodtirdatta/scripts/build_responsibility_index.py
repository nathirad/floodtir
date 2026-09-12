#!/usr/bin/env python3
"""Build a Bangkok flood-response spatial responsibility index.

The output is an operational routing aid. It does not determine legal
liability and deliberately marks every generated assignment as unverified.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
GEOJSON_DIR = ROOT / "data" / "geojson"
WATER_DIR = ROOT / "water-data"
OUTPUT_DIR = ROOT / "data" / "responsibility"
CANDIDATE_DIR = OUTPUT_DIR / "candidate"
INPUT_DIR = OUTPUT_DIR / "inputs"
VERIFIED_DIR = OUTPUT_DIR / "verified"
EVIDENCE_DIR = OUTPUT_DIR / "evidence"
ACQUISITION_DIR = OUTPUT_DIR / "acquisition"
LEGAL_AUTHORITY_DIR = OUTPUT_DIR / "legal_authority"
SCHEMA_DIR = OUTPUT_DIR / "schemas"
REVIEW_DIR = OUTPUT_DIR / "review"
SECURITY_DIR = OUTPUT_DIR / "security"
PREPARED_DIR = OUTPUT_DIR / "prepared"
NORMALIZED_DIR = OUTPUT_DIR / "normalized"
VISUALIZATION_DIR = OUTPUT_DIR / "visualization"
GEOHASH_BASE32 = "0123456789bcdefghjkmnpqrstuvwxyz"
SCHEMA_VERSION = "1.2.0"
ASSET_SAMPLE_METERS = 110.0
NEAREST_ASSET_METERS = 300.0
LEGACY_OUTPUTS = (
    "agency_master.json",
    "district_by_geohash6.json",
    "legal_basis_registry.json",
    "quality_report.json",
    "responsibility_by_geohash7.json",
    "responsibility_hash_index.csv",
    "responsibility_hash_index.jsonl",
)

LEGAL_BASIS_FIELDS = (
    "legal_basis_id",
    "document_title",
    "issuing_authority",
    "document_type",
    "section_or_page",
    "effective_from",
    "effective_to",
    "source_url",
    "document_sha256",
    "verification_status",
    "verified_by",
    "verified_at",
    "approved_by",
    "approved_at",
)

VERIFIED_ASSIGNMENT_FIELDS = (
    "assignment_source_id",
    "entity_type",
    "entity_id",
    "district_code",
    "spatial_hash",
    "spatial_hash_precision",
    "incident_type_code",
    "severity_code",
    "agency_id",
    "responsibility_role",
    "legal_basis_id",
    "effective_from",
    "effective_to",
    "evidence_text",
    "verified_by",
    "verified_at",
    "approved_by",
    "approved_at",
    "change_reason",
)

DISPATCH_AUTHORIZATION_FIELDS = (
    "authorization_source_id",
    "actor_role_code",
    "actor_agency_id",
    "target_agency_id",
    "permitted_action",
    "district_code",
    "incident_type_code",
    "legal_basis_id",
    "effective_from",
    "effective_to",
    "verified_by",
    "verified_at",
    "approved_by",
    "approved_at",
    "change_reason",
)

PERMITTED_DISPATCH_ACTIONS = {
    "view_candidate",
    "route_case",
    "assign_case",
    "approve_dispatch",
    "override_route",
    "verify_assignment",
}

LEGAL_AUTHORITY_ACTIONS = {
    "administer_bma",
    "appoint_disaster_officers",
    "assign_cross_district_work",
    "assist_disaster_director",
    "command_bma_disaster_personnel",
    "command_bma_units_in_district",
    "create_disaster_plan",
    "establish_bma_structure",
    "exercise_delegated_duties",
    "exercise_law_or_order_defined_bureau_duties",
    "exercise_statutory_district_powers",
    "initiate_disaster_response",
    "issue_bma_orders",
    "issue_bma_regulations",
    "maintain_waterways_and_drainage",
    "manage_bureau",
    "manage_district_office",
    "notify_bma_command",
    "perform_disaster_prevention",
    "perform_district_disaster_response",
    "provide_disaster_resources",
    "provide_initial_relief",
    "receive_delegated_authority",
    "request_state_agency_assistance",
    "supervise_bma_disaster_response",
}

ALLOWED_LEGAL_SOURCE_HOSTS = {
    "bangkok.go.th",
    "dds.bangkok.go.th",
    "ratchakitcha.soc.go.th",
    "webportal.bangkok.go.th",
    "www.bangkok.go.th",
    "www.ratchakitcha.soc.go.th",
    "infocenter.oic.go.th",
}

OFFICIAL_SERVICE_AREAS = (
    {
        "agency_id": "bma-dds-canal-development-1",
        "service_area_role": "canal_development_candidate",
        "district_names": (
            "ดุสิต", "ราชเทวี", "พญาไท", "บางซื่อ", "จตุจักร", "บางเขน",
            "หลักสี่", "ดอนเมือง", "ดินแดง", "สายไหม", "ห้วยขวาง", "บึงกุ่ม",
            "บางกะปิ", "มีนบุรี", "คลองสามวา", "ลาดพร้าว", "หนองจอก",
            "สะพานสูง", "วังทองหลาง", "พระโขนง", "สวนหลวง", "ประเวศ",
            "ลาดกระบัง", "บางนา", "วัฒนา", "คลองเตย", "ปทุมวัน", "คันนายาว",
        ),
        "incident_type_codes": (
            "canal_obstruction",
            "canal_overflow",
            "canal_infrastructure",
        ),
        "source_url": "https://dds.bangkok.go.th/about2_7.php",
        "source_locator": "กลุ่มงานพัฒนาระบบคลอง 1; พื้นที่ 28 เขต",
    },
    {
        "agency_id": "bma-dds-canal-development-2",
        "service_area_role": "canal_development_candidate",
        "district_names": (
            "พระนคร", "ป้อมปราบศัตรูพ่าย", "สัมพันธวงศ์", "บางรัก", "ยานนาวา",
            "สาทร", "บางคอแหลม", "คลองสาน", "ธนบุรี", "จอมทอง", "ทุ่งครุ",
            "บางขุนเทียน", "บางบอน", "ราษฎร์บูรณะ", "บางพลัด", "บางกอกน้อย",
            "บางกอกใหญ่", "ตลิ่งชัน", "บางแค", "ภาษีเจริญ", "หนองแขม",
            "ทวีวัฒนา",
        ),
        "incident_type_codes": (
            "canal_obstruction",
            "canal_overflow",
            "canal_infrastructure",
        ),
        "source_url": "https://dds.bangkok.go.th/about2_7.php",
        "source_locator": "กลุ่มงานพัฒนาระบบคลอง 2; พื้นที่ 22 เขต",
    },
    {
        "agency_id": "bma-dds-pipe-maintenance-1",
        "service_area_role": "main_pipe_maintenance_candidate",
        "district_names": (
            "ดุสิต", "พญาไท", "ราชเทวี", "บางซื่อ", "ดินแดง", "ห้วยขวาง",
            "จตุจักร", "บางเขน", "สายไหม", "ดอนเมือง", "หลักสี่", "บึงกุ่ม",
            "วังทองหลาง", "ลาดพร้าว", "บางกะปิ", "มีนบุรี", "คลองสามวา",
            "หนองจอก", "สะพานสูง", "คันนายาว", "สวนหลวง", "ประเวศ",
            "ลาดกระบัง", "บางนา", "พระโขนง",
        ),
        "incident_type_codes": (
            "main_road_pipe_blockage",
            "sump_failure",
            "road_flooding_main_system",
        ),
        "source_url": "https://dds.bangkok.go.th/about2_6.php",
        "source_locator": "กลุ่มงานบำรุงรักษาท่อระบายน้ำ 1; พื้นที่ 25 เขต",
    },
    {
        "agency_id": "bma-dds-pipe-maintenance-2",
        "service_area_role": "main_pipe_maintenance_candidate",
        "district_names": (
            "พระนคร", "ป้อมปราบศัตรูพ่าย", "สัมพันธวงศ์", "ปทุมวัน", "บางรัก",
            "ยานนาวา", "สาทร", "บางคอแหลม", "วัฒนา", "คลองเตย", "คลองสาน",
            "ธนบุรี", "จอมทอง", "ทุ่งครุ", "บางขุนเทียน", "บางบอน",
            "ราษฎร์บูรณะ", "บางพลัด", "บางกอกน้อย", "บางกอกใหญ่", "ตลิ่งชัน",
            "บางแค", "ภาษีเจริญ", "หนองแขม", "ทวีวัฒนา",
        ),
        "incident_type_codes": (
            "main_road_pipe_blockage",
            "sump_failure",
            "road_flooding_main_system",
        ),
        "source_url": "https://dds.bangkok.go.th/about2_6.php",
        "source_locator": "กลุ่มงานบำรุงรักษาท่อระบายน้ำ 2; พื้นที่ 25 เขต",
    },
)

ASSET_LAYERS = {
    "canals": {
        "path": GEOJSON_DIR / "canals.geojson",
        "id_fields": ("objectid", "canal_code"),
        "name_fields": ("canal_name",),
        "district_fields": ("district_t",),
        "owner_fields": ("owner",),
    },
    "floodgates": {
        "path": GEOJSON_DIR / "floodgates.geojson",
        "id_fields": ("gate_code", "objectid"),
        "name_fields": ("gate_name",),
        "district_fields": ("district_t",),
        "owner_fields": ("owner",),
    },
    "pumpstations": {
        "path": GEOJSON_DIR / "pumpstations.geojson",
        "id_fields": ("pump_code", "objectid"),
        "name_fields": ("pump_name",),
        "district_fields": ("district_t",),
        "owner_fields": ("owner",),
    },
    "sumps": {
        "path": GEOJSON_DIR / "sumps.geojson",
        "id_fields": ("objectid", "objectid_1"),
        "name_fields": ("name", "sump_name", "บ่อสูบน้ำ"),
        "district_fields": ("district_t", "district"),
        "owner_fields": ("owner",),
    },
    "tunnels": {
        "path": GEOJSON_DIR / "tunnels.geojson",
        "id_fields": ("objectid", "objectid_1"),
        "name_fields": ("name", "tunnel_name", "tun_name"),
        "district_fields": ("district_t", "district"),
        "owner_fields": ("owner",),
    },
    "protection": {
        "path": GEOJSON_DIR / "protection.geojson",
        "id_fields": ("objectid", "objectid_1"),
        "name_fields": ("name", "project_name", "fd_prevent_name"),
        "district_fields": ("district_t", "district"),
        "owner_fields": ("owner",),
    },
    "pipejack": {
        "path": GEOJSON_DIR / "pipejack.geojson",
        "id_fields": ("objectid", "objectid_1"),
        "name_fields": ("name", "pipe_name", "project_name"),
        "district_fields": ("district_t", "district"),
        "owner_fields": ("owner",),
    },
}

SIGNAL_LAYERS = {
    "official_risk_point": {
        "path": GEOJSON_DIR / "expo473.geojson",
        "id_fields": ("id", "objectid"),
        "name_fields": ("name", "detail"),
        "district_fields": ("district",),
    },
    "road_flood_sensor": {
        "path": GEOJSON_DIR / "roadflood.geojson",
        "id_fields": ("code", "id", "objectid"),
        "name_fields": ("name", "road"),
        "district_fields": ("district",),
    },
    "water_level_station": {
        "path": WATER_DIR / "water_latest_geojson.json",
        "id_fields": ("station_id", "station_code"),
        "name_fields": ("station_name_th", "station_short_name_th"),
        "district_fields": ("district_name_th",),
    },
}


def utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
            for row in rows
        ),
        encoding="utf-8",
    )


def write_csv(
    path: Path,
    rows: list[dict[str, Any]],
    fieldnames: Iterable[str] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(
        fieldnames
        or dict.fromkeys(key for row in rows for key in row)
    )
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=fields,
            extrasaction="ignore",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return [
            {key: (value or "").strip() for key, value in row.items()}
            for row in csv.DictReader(stream)
            if any((value or "").strip() for value in row.values())
        ]


def ensure_csv_template(path: Path, fieldnames: Iterable[str]) -> None:
    if not path.exists() or not read_csv(path):
        write_csv(path, [], fieldnames)


def clean_text(value: Any) -> str | None:
    if value is None:
        return None
    result = re.sub(r"\s+", " ", str(value)).strip()
    return result if result and result not in {"-", "null", "None"} else None


def first_value(properties: dict[str, Any], fields: Iterable[str]) -> str | None:
    for field in fields:
        value = clean_text(properties.get(field))
        if value:
            return value
    return None


def stable_hash(*parts: Any) -> str:
    payload = "|".join("" if part is None else str(part) for part in parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def is_allowed_legal_source_host(host: str) -> bool:
    normalized = host.lower().rstrip(".")
    return (
        normalized in ALLOWED_LEGAL_SOURCE_HOSTS
        or normalized.endswith(".bangkok.go.th")
    )


def encode_geohash(latitude: float, longitude: float, precision: int) -> str:
    lat_interval = [-90.0, 90.0]
    lon_interval = [-180.0, 180.0]
    bits = (16, 8, 4, 2, 1)
    bit = 0
    char = 0
    even = True
    result: list[str] = []
    while len(result) < precision:
        interval = lon_interval if even else lat_interval
        value = longitude if even else latitude
        midpoint = (interval[0] + interval[1]) / 2
        if value >= midpoint:
            char |= bits[bit]
            interval[0] = midpoint
        else:
            interval[1] = midpoint
        even = not even
        if bit < 4:
            bit += 1
        else:
            result.append(GEOHASH_BASE32[char])
            bit = 0
            char = 0
    return "".join(result)


def flatten_points(coordinates: Any) -> list[tuple[float, float]]:
    if not isinstance(coordinates, list):
        return []
    if (
        len(coordinates) >= 2
        and isinstance(coordinates[0], (int, float))
        and isinstance(coordinates[1], (int, float))
    ):
        return [(float(coordinates[0]), float(coordinates[1]))]
    points: list[tuple[float, float]] = []
    for value in coordinates:
        points.extend(flatten_points(value))
    return points


def geometry_center(geometry: dict[str, Any]) -> tuple[float, float] | None:
    points = flatten_points(geometry.get("coordinates"))
    if not points:
        return None
    if geometry.get("type") == "Point":
        return points[0]
    return (
        (min(point[0] for point in points) + max(point[0] for point in points))
        / 2,
        (min(point[1] for point in points) + max(point[1] for point in points))
        / 2,
    )


def haversine_meters(
    first: tuple[float, float], second: tuple[float, float]
) -> float:
    lon1, lat1 = first
    lon2, lat2 = second
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    dlat = lat2_rad - lat1_rad
    dlon = math.radians(lon2 - lon1)
    value = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
    )
    return 6371000.0 * 2 * math.atan2(math.sqrt(value), math.sqrt(1 - value))


def sample_line(
    points: list[tuple[float, float]], interval_meters: float
) -> list[tuple[float, float]]:
    if len(points) < 2:
        return points
    result = [points[0]]
    for start, end in zip(points, points[1:]):
        distance = haversine_meters(start, end)
        steps = max(1, math.ceil(distance / interval_meters))
        for step in range(1, steps + 1):
            ratio = step / steps
            result.append(
                (
                    start[0] + (end[0] - start[0]) * ratio,
                    start[1] + (end[1] - start[1]) * ratio,
                )
            )
    return result


def geometry_lines(geometry: dict[str, Any]) -> list[list[tuple[float, float]]]:
    geometry_type = geometry.get("type")
    coordinates = geometry.get("coordinates") or []
    if geometry_type == "LineString":
        return [[(float(point[0]), float(point[1])) for point in coordinates]]
    if geometry_type == "MultiLineString":
        return [
            [(float(point[0]), float(point[1])) for point in line]
            for line in coordinates
        ]
    if geometry_type == "Polygon":
        return [
            [(float(point[0]), float(point[1])) for point in ring]
            for ring in coordinates
        ]
    if geometry_type == "MultiPolygon":
        return [
            [(float(point[0]), float(point[1])) for point in ring]
            for polygon in coordinates
            for ring in polygon
        ]
    return []


def geometry_samples(geometry: dict[str, Any]) -> list[tuple[float, float]]:
    center = geometry_center(geometry)
    if geometry.get("type") == "Point":
        return [center] if center else []
    samples: list[tuple[float, float]] = []
    for line in geometry_lines(geometry):
        samples.extend(sample_line(line, ASSET_SAMPLE_METERS))
    if center:
        samples.append(center)
    return list(dict.fromkeys(samples))


def point_in_ring(lon: float, lat: float, ring: list[list[float]]) -> bool:
    inside = False
    previous = len(ring) - 1
    for current, point in enumerate(ring):
        x1, y1 = ring[current][:2]
        x2, y2 = ring[previous][:2]
        intersects = (y1 > lat) != (y2 > lat) and lon < (
            (x2 - x1) * (lat - y1) / ((y2 - y1) or 1e-12) + x1
        )
        if intersects:
            inside = not inside
        previous = current
    return inside


def point_in_geometry(lon: float, lat: float, geometry: dict[str, Any]) -> bool:
    geometry_type = geometry.get("type")
    coordinates = geometry.get("coordinates") or []
    polygons = [coordinates] if geometry_type == "Polygon" else coordinates
    if geometry_type not in {"Polygon", "MultiPolygon"}:
        return False
    for polygon in polygons:
        if not polygon or not point_in_ring(lon, lat, polygon[0]):
            continue
        if not any(point_in_ring(lon, lat, hole) for hole in polygon[1:]):
            return True
    return False


class DistrictIndex:
    def __init__(self) -> None:
        source = read_json(GEOJSON_DIR / "districts.geojson")
        self.features: list[dict[str, Any]] = []
        self.by_name: dict[str, dict[str, Any]] = {}
        for feature in source["features"]:
            properties = feature["properties"]
            name = clean_text(properties.get("DISTRICT_N"))
            if not name:
                continue
            row = {
                "district_code": str(properties.get("DISTRICT_I") or ""),
                "district_name_th": name,
                "geometry": feature["geometry"],
            }
            points = flatten_points(feature["geometry"].get("coordinates"))
            row["bbox"] = (
                min(point[0] for point in points),
                min(point[1] for point in points),
                max(point[0] for point in points),
                max(point[1] for point in points),
            )
            self.features.append(row)
            self.by_name[name] = row

    def normalize_name(self, raw: Any) -> str | None:
        value = clean_text(raw)
        if not value:
            return None
        value = re.sub(r"^(สำนักงาน)?เขต", "", value).strip()
        if value in self.by_name:
            return value
        for name in self.by_name:
            if name in value or value in name:
                return name
        return None

    def locate(self, lon: float, lat: float) -> dict[str, Any] | None:
        for row in self.features:
            min_lon, min_lat, max_lon, max_lat = row["bbox"]
            if not (min_lon <= lon <= max_lon and min_lat <= lat <= max_lat):
                continue
            if point_in_geometry(lon, lat, row["geometry"]):
                return row
        return None

    def resolve(
        self,
        raw_name: Any,
        point: tuple[float, float] | None,
        *,
        prefer_spatial: bool = True,
    ) -> dict[str, Any] | None:
        if point and prefer_spatial:
            spatial = self.locate(point[0], point[1])
            if spatial:
                return spatial
        name = self.normalize_name(raw_name)
        if name:
            return self.by_name[name]
        if point:
            return self.locate(point[0], point[1])
        return None

    def conflicts(
        self, raw_name: Any, point: tuple[float, float] | None
    ) -> bool:
        if not point:
            return False
        normalized = self.normalize_name(raw_name)
        spatial = self.locate(point[0], point[1])
        return bool(
            normalized
            and spatial
            and normalized != spatial["district_name_th"]
        )


class AgencyRegistry:
    def __init__(self, districts: DistrictIndex) -> None:
        self.rows: dict[str, dict[str, Any]] = {}
        self.aliases: dict[str, str] = {}
        self.register(
            "bma",
            "กรุงเทพมหานคร",
            "local_government",
            "governance",
            None,
        )
        self.register(
            "bma-dds",
            "สำนักการระบายน้ำ",
            "bma_department",
            "core_flood_operations",
            "bma",
        )
        self.register(
            "bma-dds-water-control",
            "สำนักงานระบบควบคุมน้ำ สำนักการระบายน้ำ",
            "bma_operational_unit",
            "core_flood_operations",
            "bma-dds",
        )
        self.register(
            "bma-dds-development",
            "สำนักพัฒนาระบบระบายน้ำ",
            "bma_operational_unit",
            "core_flood_operations",
            "bma-dds",
        )
        self.register(
            "bma-dds-pipe",
            "กองระบบท่อระบายน้ำ สำนักการระบายน้ำ",
            "bma_operational_unit",
            "core_flood_operations",
            "bma-dds",
        )
        self.register(
            "bma-dds-canal",
            "กองระบบคลอง สำนักการระบายน้ำ",
            "bma_operational_unit",
            "core_flood_operations",
            "bma-dds",
        )
        official_subunits = [
            (
                "bma-dds-canal-development-1",
                "กลุ่มงานพัฒนาระบบคลอง 1",
                "bma-dds-canal",
                "canal_development",
            ),
            (
                "bma-dds-canal-development-2",
                "กลุ่มงานพัฒนาระบบคลอง 2",
                "bma-dds-canal",
                "canal_development",
            ),
            (
                "bma-dds-pipe-maintenance-1",
                "กลุ่มงานบำรุงรักษาท่อระบายน้ำ 1",
                "bma-dds-pipe",
                "main_pipe_maintenance",
            ),
            (
                "bma-dds-pipe-maintenance-2",
                "กลุ่มงานบำรุงรักษาท่อระบายน้ำ 2",
                "bma-dds-pipe",
                "main_pipe_maintenance",
            ),
        ]
        for agency_id, name, parent_id, function in official_subunits:
            self.register(
                agency_id,
                name,
                "bma_operational_subunit",
                "core_flood_operations",
                parent_id,
                operational_function=function,
                source_verification_status="official_page_reference",
            )
        support_agencies = [
            ("bma-ddpm", "สำนักป้องกันและบรรเทาสาธารณภัย", "incident_command"),
            ("bma-traffic", "สำนักการจราจรและขนส่ง", "traffic_support"),
            ("bma-municipal", "สำนักเทศกิจ", "field_support"),
            ("bma-public-works", "สำนักการโยธา", "engineering_support"),
            ("bma-public-relations", "สำนักงานประชาสัมพันธ์", "public_information"),
            ("bma-health", "สำนักอนามัย", "public_health_support"),
            ("bma-medical", "สำนักการแพทย์", "medical_support"),
            ("bma-environment", "สำนักสิ่งแวดล้อม", "environment_support"),
            ("bma-finance", "สำนักการคลัง", "relief_support"),
            ("bma-budget", "สำนักงบประมาณกรุงเทพมหานคร", "budget_support"),
        ]
        for agency_id, name, function in support_agencies:
            self.register(
                agency_id,
                name,
                "bma_support_department",
                "conditional_flood_support",
                "bma",
                operational_function=function,
            )
        for district in districts.features:
            self.register(
                f"bma-district-{district['district_code']}",
                f"สำนักงานเขต{district['district_name_th']}",
                "bma_district_office",
                "core_flood_operations",
                "bma",
                district_code=district["district_code"],
                district_name_th=district["district_name_th"],
                operational_function="district_flood_response",
            )

    def register(
        self,
        agency_id: str,
        name: str,
        category: str,
        response_tier: str,
        parent_agency_id: str | None,
        **extra: Any,
    ) -> str:
        self.rows[agency_id] = {
            "agency_id": agency_id,
            "agency_name_th": name,
            "agency_category": category,
            "response_tier": response_tier,
            "parent_agency_id": parent_agency_id,
            "legal_verification_status": "unverified",
            **extra,
        }
        self.aliases[name] = agency_id
        return agency_id

    def district_agency(self, district: dict[str, Any] | None) -> str | None:
        if not district:
            return None
        return f"bma-district-{district['district_code']}"

    def owner_agency(
        self, owner: Any, district: dict[str, Any] | None
    ) -> tuple[str | None, str]:
        value = clean_text(owner)
        if not value:
            return None, "missing_owner"
        if value == "สำนักงานเขต":
            return self.district_agency(district), "generic_district_owner"
        if district and value == district["district_name_th"]:
            return self.district_agency(district), "district_name_owner"
        if value == "สำนักการระบายน้ำ":
            return "bma-dds", "explicit_owner"
        if value in {"สำนักงานระบบควบคุมน้ำ"}:
            return "bma-dds-water-control", "explicit_owner"
        if value in {"สำนักพัฒนาระบบระบายน้ำ"}:
            return "bma-dds-development", "explicit_owner"
        if value in {"กองระบบท่อระบายน้ำ"}:
            return "bma-dds-pipe", "explicit_owner"
        if value in {"กองระบบคลอง"}:
            return "bma-dds-canal", "explicit_owner"
        if any(
            token in value
            for token in ("อาคารบังคับน้ำ", "อุโมงค์ธนบุรี", "อุโมงค์พระนคร", "กลุ่มงานตะวันออก")
        ):
            return "bma-dds-water-control", "normalized_dds_unit_owner"
        for row in self.rows.values():
            district_name = row.get("district_name_th")
            if district_name and district_name == value:
                return row["agency_id"], "district_name_owner"
        return None, "unmapped_owner"

    def name(self, agency_id: str | None) -> str | None:
        return self.rows.get(agency_id or "", {}).get("agency_name_th")


def entity_id(
    layer: str, properties: dict[str, Any], fields: Iterable[str], index: int
) -> str:
    value = first_value(properties, fields) or str(index)
    return f"{layer}:{value}"


def add_assignment(
    assignments: list[dict[str, Any]],
    *,
    entity_type: str,
    entity_id_value: str,
    entity_name: str | None,
    source_layer: str,
    geohash7: str,
    district: dict[str, Any] | None,
    agency_id: str,
    agencies: AgencyRegistry,
    responsibility_role: str,
    assignment_method: str,
    confidence: float,
    evidence_text: str,
    source_path: str,
    responsible_unit: str | None = None,
    nearest_asset_id: str | None = None,
    nearest_asset_distance_m: float | None = None,
) -> None:
    digest = stable_hash(
        SCHEMA_VERSION,
        entity_type,
        entity_id_value,
        agency_id,
        responsibility_role,
        assignment_method,
    )
    assignments.append(
        {
            "responsibility_hash_sha256": digest,
            "entity_type": entity_type,
            "entity_id": entity_id_value,
            "entity_name_th": entity_name,
            "source_layer": source_layer,
            "spatial_hash_geohash7": geohash7,
            "district_code": district["district_code"] if district else None,
            "district_name_th": district["district_name_th"] if district else None,
            "agency_id": agency_id,
            "agency_name_th": agencies.name(agency_id),
            "responsibility_role": responsibility_role,
            "responsible_unit_th": responsible_unit,
            "assignment_method": assignment_method,
            "confidence": round(confidence, 3),
            "evidence_text": evidence_text,
            "source_path": source_path,
            "nearest_asset_id": nearest_asset_id,
            "nearest_asset_distance_m": (
                round(nearest_asset_distance_m, 1)
                if nearest_asset_distance_m is not None
                else None
            ),
            "legal_basis_id": None,
            "verification_status": "candidate_unverified",
            "is_official_legal_assignment": False,
            "requires_human_approval": True,
        }
    )


def spatial_bucket(point: tuple[float, float]) -> tuple[int, int]:
    return (math.floor(point[0] * 100), math.floor(point[1] * 100))


def nearest_asset(
    point: tuple[float, float],
    buckets: dict[tuple[int, int], list[dict[str, Any]]],
) -> tuple[dict[str, Any] | None, float | None]:
    base_lon, base_lat = spatial_bucket(point)
    best: dict[str, Any] | None = None
    best_distance = float("inf")
    for lon_offset in range(-1, 2):
        for lat_offset in range(-1, 2):
            for candidate in buckets.get(
                (base_lon + lon_offset, base_lat + lat_offset), []
            ):
                distance = haversine_meters(point, candidate["point"])
                if distance < best_distance:
                    best = candidate
                    best_distance = distance
    if best is None or best_distance > NEAREST_ASSET_METERS:
        return None, None
    return best, best_distance


def build_district_hash(
    districts: DistrictIndex, agencies: AgencyRegistry
) -> dict[str, Any]:
    cells: dict[str, set[str]] = defaultdict(set)
    step = 0.003
    for district in districts.features:
        min_lon, min_lat, max_lon, max_lat = district["bbox"]
        lat = min_lat
        while lat <= max_lat:
            lon = min_lon
            while lon <= max_lon:
                if point_in_geometry(lon, lat, district["geometry"]):
                    cells[encode_geohash(lat, lon, 6)].add(
                        agencies.district_agency(district) or ""
                    )
                lon += step
            lat += step
        center = geometry_center(district["geometry"])
        if center:
            cells[encode_geohash(center[1], center[0], 6)].add(
                agencies.district_agency(district) or ""
            )
    return {
        "metadata": {
            "schema_version": SCHEMA_VERSION,
            "generated_at": utc_now(),
            "precision": 6,
            "use": "district jurisdiction fallback for a new report coordinate",
            "legal_notice": "Operational routing candidate, not legal liability.",
        },
        "cells": {
            cell: sorted(agency_id for agency_id in agency_ids if agency_id)
            for cell, agency_ids in sorted(cells.items())
        },
    }


def build_service_area_index(
    districts: DistrictIndex, agencies: AgencyRegistry
) -> tuple[list[dict[str, Any]], dict[str, list[str]]]:
    rows: list[dict[str, Any]] = []
    by_district: dict[str, list[str]] = defaultdict(list)
    for definition in OFFICIAL_SERVICE_AREAS:
        agency_id = definition["agency_id"]
        if agency_id not in agencies.rows:
            raise RuntimeError(f"Unknown service-area agency: {agency_id}")
        for district_name in definition["district_names"]:
            district = districts.by_name.get(district_name)
            if not district:
                raise RuntimeError(
                    f"Unknown service-area district: {district_name}"
                )
            digest = stable_hash(
                SCHEMA_VERSION,
                "official_service_area_candidate",
                agency_id,
                district["district_code"],
                definition["service_area_role"],
                definition["source_url"],
            )
            row = {
                "service_area_hash_sha256": digest,
                "district_code": district["district_code"],
                "district_name_th": district_name,
                "district_agency_id": agencies.district_agency(district),
                "agency_id": agency_id,
                "agency_name_th": agencies.name(agency_id),
                "service_area_role": definition["service_area_role"],
                "incident_type_codes": list(
                    definition["incident_type_codes"]
                ),
                "source_url": definition["source_url"],
                "source_locator": definition["source_locator"],
                "verification_status": "official_reference_unverified",
                "is_official_legal_assignment": False,
                "requires_human_approval": True,
            }
            rows.append(row)
            by_district[district["district_code"]].append(digest)
    rows.sort(
        key=lambda row: (
            row["district_code"],
            row["service_area_role"],
            row["agency_id"],
        )
    )
    return rows, {
        district_code: sorted(hashes)
        for district_code, hashes in sorted(by_district.items())
    }


def build_agency_incident_capability_index(
    service_area_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, list[str]]]:
    rows: list[dict[str, Any]] = []
    by_district_incident: dict[str, list[str]] = defaultdict(list)
    for service_area in service_area_rows:
        legal_reference_id = (
            "dds-canal-division-duties"
            if service_area["service_area_role"]
            == "canal_development_candidate"
            else "dds-pipe-division-duties"
        )
        for incident_type_code in service_area["incident_type_codes"]:
            digest = stable_hash(
                SCHEMA_VERSION,
                "agency_incident_capability_candidate",
                service_area["district_code"],
                incident_type_code,
                service_area["agency_id"],
                service_area["service_area_role"],
                legal_reference_id,
            )
            row = {
                "capability_hash_sha256": digest,
                "district_code": service_area["district_code"],
                "district_name_th": service_area["district_name_th"],
                "incident_type_code": incident_type_code,
                "agency_id": service_area["agency_id"],
                "agency_name_th": service_area["agency_name_th"],
                "capability_role": service_area["service_area_role"],
                "legal_basis_reference_id": legal_reference_id,
                "source_service_area_hash_sha256": service_area[
                    "service_area_hash_sha256"
                ],
                "source_url": service_area["source_url"],
                "source_locator": service_area["source_locator"],
                "verification_status": "official_reference_unverified",
                "is_official_legal_assignment": False,
                "requires_human_approval": True,
            }
            rows.append(row)
            key = (
                f"{service_area['district_code']}:{incident_type_code}"
            )
            by_district_incident[key].append(digest)
    rows.sort(
        key=lambda row: (
            row["district_code"],
            row["incident_type_code"],
            row["agency_id"],
        )
    )
    return rows, {
        key: sorted(hashes)
        for key, hashes in sorted(by_district_incident.items())
    }


def build_legal_reference_hash_index(
    legal_sources: dict[str, Any],
) -> list[dict[str, Any]]:
    rows = []
    for source in legal_sources["sources"]:
        row = {
            "legal_reference_hash_sha256": stable_hash(
                SCHEMA_VERSION,
                "legal_reference",
                source["legal_basis_id"],
                source["url"],
                source["source_class"],
            ),
            **source,
            "is_document_content_hash": False,
            "requires_document_download_and_review": True,
        }
        rows.append(row)
    return sorted(rows, key=lambda row: row["legal_basis_id"])


def build_district_agency_responsibility_index(
    districts: DistrictIndex,
    agencies: AgencyRegistry,
    assignments: list[dict[str, Any]],
    service_area_rows: list[dict[str, Any]],
    capability_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    grouped: dict[tuple[str, str, str, str, str], dict[str, Any]] = {}

    def add_record(
        *,
        district_code: str,
        district_name_th: str,
        agency_id: str,
        responsibility_scope: str,
        responsibility_role: str,
        source_hash: str,
        verification_status: str,
        incident_type_code: str | None = None,
        related_incident_types: Iterable[str] = (),
        legal_basis_reference_id: str | None = None,
        source_url: str | None = None,
    ) -> None:
        key = (
            district_code,
            agency_id,
            responsibility_scope,
            responsibility_role,
            incident_type_code or "",
        )
        record = grouped.setdefault(
            key,
            {
                "district_code": district_code,
                "district_name_th": district_name_th,
                "agency_id": agency_id,
                "agency_name_th": agencies.name(agency_id),
                "responsibility_scope": responsibility_scope,
                "responsibility_role": responsibility_role,
                "incident_type_code": incident_type_code,
                "related_incident_type_codes": set(),
                "source_hashes_sha256": set(),
                "legal_basis_reference_ids": set(),
                "source_urls": set(),
                "verification_status": verification_status,
            },
        )
        record["source_hashes_sha256"].add(source_hash)
        record["related_incident_type_codes"].update(
            related_incident_types
        )
        if incident_type_code:
            record["related_incident_type_codes"].add(incident_type_code)
        if legal_basis_reference_id:
            record["legal_basis_reference_ids"].add(
                legal_basis_reference_id
            )
        if source_url:
            record["source_urls"].add(source_url)

    for row in assignments:
        add_record(
            district_code=row["district_code"],
            district_name_th=row["district_name_th"],
            agency_id=row["agency_id"],
            responsibility_scope="entity_assignment",
            responsibility_role=row["responsibility_role"],
            source_hash=row["responsibility_hash_sha256"],
            verification_status=row["verification_status"],
        )
    for row in service_area_rows:
        add_record(
            district_code=row["district_code"],
            district_name_th=row["district_name_th"],
            agency_id=row["agency_id"],
            responsibility_scope="service_area",
            responsibility_role=row["service_area_role"],
            source_hash=row["service_area_hash_sha256"],
            verification_status=row["verification_status"],
            related_incident_types=row["incident_type_codes"],
            source_url=row["source_url"],
        )
    for row in capability_rows:
        add_record(
            district_code=row["district_code"],
            district_name_th=row["district_name_th"],
            agency_id=row["agency_id"],
            responsibility_scope="incident_capability",
            responsibility_role=row["capability_role"],
            source_hash=row["capability_hash_sha256"],
            verification_status=row["verification_status"],
            incident_type_code=row["incident_type_code"],
            legal_basis_reference_id=row[
                "legal_basis_reference_id"
            ],
            source_url=row["source_url"],
        )

    rows: list[dict[str, Any]] = []
    for key, record in sorted(grouped.items()):
        digest = stable_hash(
            SCHEMA_VERSION,
            "district_agency_responsibility_summary",
            *key,
        )
        source_hashes = sorted(record["source_hashes_sha256"])
        rows.append(
            {
                "district_agency_responsibility_hash_sha256": digest,
                "district_code": record["district_code"],
                "district_name_th": record["district_name_th"],
                "agency_id": record["agency_id"],
                "agency_name_th": record["agency_name_th"],
                "responsibility_scope": record[
                    "responsibility_scope"
                ],
                "responsibility_role": record["responsibility_role"],
                "incident_type_code": record["incident_type_code"],
                "related_incident_type_codes": sorted(
                    record["related_incident_type_codes"]
                ),
                "source_record_count": len(source_hashes),
                "source_hashes_sha256": source_hashes,
                "legal_basis_reference_ids": sorted(
                    record["legal_basis_reference_ids"]
                ),
                "source_urls": sorted(record["source_urls"]),
                "verification_status": record["verification_status"],
                "is_official_legal_assignment": False,
                "requires_human_approval": True,
            }
        )

    rows_by_district: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        rows_by_district[row["district_code"]].append(row)
    profiles: list[dict[str, Any]] = []
    for district in sorted(
        districts.features, key=lambda row: row["district_code"]
    ):
        agency_profiles: dict[str, dict[str, Any]] = {}
        district_rows = rows_by_district[district["district_code"]]
        for row in district_rows:
            agency = agencies.rows[row["agency_id"]]
            profile = agency_profiles.setdefault(
                row["agency_id"],
                {
                    "agency_id": row["agency_id"],
                    "agency_name_th": row["agency_name_th"],
                    "agency_category": agency["agency_category"],
                    "response_tier": agency["response_tier"],
                    "responsibility_roles": set(),
                    "incident_type_codes": set(),
                    "summary_hashes_sha256": [],
                    "source_record_count": 0,
                    "verification_statuses": set(),
                },
            )
            profile["responsibility_roles"].add(
                row["responsibility_role"]
            )
            profile["incident_type_codes"].update(
                row["related_incident_type_codes"]
            )
            profile["summary_hashes_sha256"].append(
                row["district_agency_responsibility_hash_sha256"]
            )
            profile["source_record_count"] += row[
                "source_record_count"
            ]
            profile["verification_statuses"].add(
                row["verification_status"]
            )
        normalized_profiles = []
        for profile in agency_profiles.values():
            normalized_profiles.append(
                {
                    **profile,
                    "responsibility_roles": sorted(
                        profile["responsibility_roles"]
                    ),
                    "incident_type_codes": sorted(
                        profile["incident_type_codes"]
                    ),
                    "summary_hashes_sha256": sorted(
                        profile["summary_hashes_sha256"]
                    ),
                    "verification_statuses": sorted(
                        profile["verification_statuses"]
                    ),
                }
            )
        district_agency_id = agencies.district_agency(district)
        profiles.append(
            {
                "district_code": district["district_code"],
                "district_name_th": district["district_name_th"],
                "district_agency_id": district_agency_id,
                "district_agency_name_th": agencies.name(
                    district_agency_id
                ),
                "candidate_agency_count": len(normalized_profiles),
                "summary_hash_count": len(district_rows),
                "source_record_count": sum(
                    row["source_record_count"] for row in district_rows
                ),
                "agencies": sorted(
                    normalized_profiles,
                    key=lambda row: row["agency_id"],
                ),
                "verification_status": "candidate_unverified",
                "requires_human_approval": True,
            }
        )
    return rows, profiles


def write_hash_index_catalog(
    *,
    assignments: list[dict[str, Any]],
    service_area_rows: list[dict[str, Any]],
    capability_rows: list[dict[str, Any]],
    legal_reference_rows: list[dict[str, Any]],
    district_agency_rows: list[dict[str, Any]],
    document_evidence_rows: list[dict[str, Any]],
    mission_duty_rows: list[dict[str, Any]],
    sop_process_rows: list[dict[str, Any]],
    district_process_rows: list[dict[str, Any]],
    data_source_rows: list[dict[str, Any]],
    unresolved_asset_owners: list[dict[str, Any]],
    spatial_conflicts: list[dict[str, Any]],
    acquisition: dict[str, Any],
    legal_authority: dict[str, Any],
    verified_quality: dict[str, Any],
) -> None:
    role_counts = Counter(
        row["responsibility_role"] for row in assignments
    )
    datasets = [
        {
            "dataset_id": "candidate-responsibility-assignments",
            "path": "candidate/all_assignments.jsonl",
            "csv_path": "candidate/all_assignments.csv",
            "hash_field": "responsibility_hash_sha256",
            "record_count": len(assignments),
            "record_kind": "canonical",
            "verification_status": "candidate_unverified",
        },
        {
            "dataset_id": "candidate-geographic-jurisdiction",
            "path": "candidate/geographic_jurisdiction_hash_index.jsonl",
            "hash_field": "responsibility_hash_sha256",
            "record_count": role_counts[
                "geographic_jurisdiction_candidate"
            ],
            "record_kind": "materialized_view",
            "verification_status": "candidate_unverified",
        },
        {
            "dataset_id": "candidate-asset-owner",
            "path": "candidate/asset_owner_hash_index.jsonl",
            "hash_field": "responsibility_hash_sha256",
            "record_count": role_counts["asset_owner_candidate"],
            "record_kind": "materialized_view",
            "verification_status": "candidate_unverified",
        },
        {
            "dataset_id": "candidate-flood-signal-routing",
            "path": "candidate/flood_signal_routing_hash_index.jsonl",
            "hash_field": "responsibility_hash_sha256",
            "record_count": (
                role_counts["primary_response_candidate"]
                + role_counts["support_response_candidate"]
            ),
            "record_kind": "materialized_view",
            "verification_status": "candidate_unverified",
        },
        {
            "dataset_id": "candidate-data-custodian",
            "path": "candidate/data_custodian_hash_index.jsonl",
            "hash_field": "responsibility_hash_sha256",
            "record_count": role_counts["data_custodian"],
            "record_kind": "materialized_view",
            "verification_status": "candidate_unverified",
        },
        {
            "dataset_id": "candidate-agency-service-area",
            "path": "candidate/agency_service_area_hash_index.jsonl",
            "hash_field": "service_area_hash_sha256",
            "record_count": len(service_area_rows),
            "record_kind": "canonical",
            "verification_status": "official_reference_unverified",
        },
        {
            "dataset_id": "candidate-agency-incident-capability",
            "path": (
                "candidate/"
                "agency_incident_capability_hash_index.jsonl"
            ),
            "hash_field": "capability_hash_sha256",
            "record_count": len(capability_rows),
            "record_kind": "canonical",
            "verification_status": "official_reference_unverified",
        },
        {
            "dataset_id": "candidate-legal-reference",
            "path": "candidate/legal_reference_hash_index.jsonl",
            "hash_field": "legal_reference_hash_sha256",
            "record_count": len(legal_reference_rows),
            "record_kind": "canonical_reference_identity",
            "verification_status": "reference_not_legal_reviewed",
        },
        {
            "dataset_id": "candidate-district-agency-summary",
            "path": (
                "candidate/"
                "district_agency_responsibility_hash_index.jsonl"
            ),
            "hash_field": (
                "district_agency_responsibility_hash_sha256"
            ),
            "record_count": len(district_agency_rows),
            "record_kind": "derived_summary",
            "verification_status": "candidate_unverified",
        },
        {
            "dataset_id": "evidence-official-document-registry",
            "path": "evidence/official_document_registry.json",
            "hash_field": "document_evidence_hash_sha256",
            "record_count": len(document_evidence_rows),
            "record_kind": "official_document_evidence",
            "verification_status": "pending_legal_review",
        },
        {
            "dataset_id": "evidence-mission-duty",
            "path": "evidence/mission_duty_evidence_hash_index.jsonl",
            "hash_field": "mission_duty_hash_sha256",
            "record_count": len(mission_duty_rows),
            "record_kind": "official_document_extraction",
            "verification_status": "pending_legal_review",
        },
        {
            "dataset_id": "evidence-sop-process",
            "path": "evidence/sop_process_evidence_hash_index.jsonl",
            "hash_field": "sop_process_hash_sha256",
            "record_count": len(sop_process_rows),
            "record_kind": "official_document_extraction",
            "verification_status": "pending_legal_review",
        },
        {
            "dataset_id": "evidence-district-office-flood-process",
            "path": (
                "evidence/"
                "district_office_flood_process_hash_index.jsonl"
            ),
            "hash_field": "district_process_hash_sha256",
            "record_count": len(district_process_rows),
            "record_kind": "derived_common_process_candidate",
            "verification_status": "pending_district_confirmation",
        },
        {
            "dataset_id": "evidence-data-source-registry",
            "path": "evidence/data_source_registry_hash_index.jsonl",
            "hash_field": "data_source_hash_sha256",
            "record_count": len(data_source_rows),
            "record_kind": "source_lineage",
            "verification_status": "mixed_see_record",
        },
        {
            "dataset_id": "review-unresolved-asset-owner",
            "path": "review/unresolved_asset_owners.jsonl",
            "hash_field": "review_hash_sha256",
            "record_count": len(unresolved_asset_owners),
            "record_kind": "manual_review",
            "verification_status": "unresolved",
        },
        {
            "dataset_id": "review-spatial-conflict",
            "path": "review/spatial_conflicts.jsonl",
            "hash_field": "review_hash_sha256",
            "record_count": len(spatial_conflicts),
            "record_kind": "manual_review",
            "verification_status": "unresolved",
        },
        {
            "dataset_id": "acquisition-source-evidence",
            "path": "acquisition/source_evidence_hash_index.jsonl",
            "hash_field": "acquired_source_hash_sha256",
            "record_count": len(acquisition["sources"]),
            "record_kind": "official_public_source_evidence",
            "verification_status": "mixed_see_record",
        },
        {
            "dataset_id": "acquisition-asset-owner-status",
            "path": "acquisition/asset_owner_resolution_status.jsonl",
            "hash_field": "acquisition_resolution_hash_sha256",
            "record_count": len(acquisition["owner_statuses"]),
            "record_kind": "gap_resolution_status",
            "verification_status": "requires_agency_confirmation",
        },
        {
            "dataset_id": "acquisition-spatial-conflict-status",
            "path": "acquisition/spatial_conflict_resolution_status.jsonl",
            "hash_field": "acquisition_resolution_hash_sha256",
            "record_count": len(acquisition["spatial_statuses"]),
            "record_kind": "gap_resolution_status",
            "verification_status": "mixed_see_record",
        },
        {
            "dataset_id": "acquisition-district-sop-availability",
            "path": "acquisition/district_sop_availability.jsonl",
            "hash_field": "district_sop_availability_hash_sha256",
            "record_count": len(acquisition["district_sop_rows"]),
            "record_kind": "district_sop_availability",
            "verification_status": "mixed_see_record",
        },
        {
            "dataset_id": "acquisition-gap-resolution",
            "path": "acquisition/gap_resolution_registry.jsonl",
            "hash_field": "gap_resolution_hash_sha256",
            "record_count": len(acquisition["gap_rows"]),
            "record_kind": "gap_resolution_summary",
            "verification_status": "mixed_see_record",
        },
        {
            "dataset_id": "legal-authority-source-registry",
            "path": "legal_authority/source_registry.json",
            "hash_field": "legal_source_hash_sha256",
            "record_count": len(legal_authority["sources"]),
            "record_kind": "checked_in_official_legal_document",
            "verification_status": "pending_legal_review",
        },
        {
            "dataset_id": "legal-authority-provisions",
            "path": (
                "legal_authority/"
                "authority_provisions_hash_index.jsonl"
            ),
            "hash_field": "authority_hash_sha256",
            "record_count": len(legal_authority["provisions"]),
            "record_kind": "curated_statutory_evidence",
            "verification_status": "pending_legal_review",
        },
        {
            "dataset_id": "legal-authority-district-candidates",
            "path": (
                "legal_authority/"
                "district_authority_candidates.jsonl"
            ),
            "hash_field": "district_authority_hash_sha256",
            "record_count": len(
                legal_authority["district_candidates"]
            ),
            "record_kind": "district_statutory_role_candidate",
            "verification_status": "pending_legal_review",
        },
        {
            "dataset_id": "legal-authority-review-queue",
            "path": "legal_authority/legal_review_queue.jsonl",
            "hash_field": "legal_review_hash_sha256",
            "record_count": len(legal_authority["review_queue"]),
            "record_kind": "legal_review_task",
            "verification_status": "open",
        },
        {
            "dataset_id": "verified-legal-responsibility",
            "path": "verified/legal_responsibility_hash_index.jsonl",
            "csv_path": (
                "verified/legal_responsibility_hash_index.csv"
            ),
            "hash_field": "responsibility_hash_sha256",
            "record_count": verified_quality["metadata"][
                "assignment_count"
            ],
            "record_kind": "verified",
            "verification_status": verified_quality["metadata"][
                "status"
            ],
        },
        {
            "dataset_id": "verified-dispatch-authorization",
            "path": (
                "verified/dispatch_authorization_hash_index.jsonl"
            ),
            "csv_path": (
                "verified/dispatch_authorization_hash_index.csv"
            ),
            "hash_field": "authorization_hash_sha256",
            "record_count": verified_quality["metadata"][
                "dispatch_authorization_count"
            ],
            "record_kind": "verified",
            "verification_status": verified_quality["metadata"][
                "status"
            ],
        },
    ]
    write_json(
        OUTPUT_DIR / "hash_index_catalog.json",
        {
            "metadata": {
                "schema_version": SCHEMA_VERSION,
                "generated_at": utc_now(),
                "scope": "All responsibility hash datasets in this PR",
                "notice": (
                    "Canonical, derived, review, and verified counts are "
                    "reported separately to avoid double counting."
                ),
            },
            "totals": {
                "canonical_candidate_hash_count": (
                    len(assignments)
                    + len(service_area_rows)
                    + len(capability_rows)
                    + len(legal_reference_rows)
                ),
                "derived_district_agency_summary_hash_count": len(
                    district_agency_rows
                ),
                "manual_review_hash_count": (
                    len(unresolved_asset_owners)
                    + len(spatial_conflicts)
                ),
                "verified_hash_count": (
                    verified_quality["metadata"]["assignment_count"]
                    + verified_quality["metadata"][
                        "dispatch_authorization_count"
                    ]
                ),
                "official_evidence_hash_count": (
                    len(document_evidence_rows)
                    + len(mission_duty_rows)
                    + len(sop_process_rows)
                ),
                "district_process_candidate_hash_count": len(
                    district_process_rows
                ),
                "provenance_source_hash_count": len(data_source_rows),
                "acquisition_source_hash_count": len(
                    acquisition["sources"]
                ),
                "acquisition_gap_status_hash_count": (
                    len(acquisition["owner_statuses"])
                    + len(acquisition["spatial_statuses"])
                    + len(acquisition["district_sop_rows"])
                    + len(acquisition["gap_rows"])
                ),
                "legal_authority_evidence_hash_count": (
                    len(legal_authority["sources"])
                    + len(legal_authority["provisions"])
                ),
                "district_legal_authority_candidate_hash_count": len(
                    legal_authority["district_candidates"]
                ),
                "legal_authority_review_hash_count": len(
                    legal_authority["review_queue"]
                ),
            },
            "datasets": datasets,
        },
    )


def build_incident_type_registry() -> dict[str, Any]:
    definitions = [
        (
            "road_flooding_local_system",
            "น้ำท่วมถนนหรือซอยในระบบระบายน้ำท้องถิ่น",
            "district_polygon_then_asset_owner",
        ),
        (
            "road_flooding_main_system",
            "น้ำท่วมถนนสายหลักหรือระบบท่อระบายน้ำหลัก",
            "pipe_service_area_then_asset_owner",
        ),
        (
            "main_road_pipe_blockage",
            "ท่อระบายน้ำถนนสายหลักอุดตันหรือระบายผิดปกติ",
            "pipe_service_area_then_asset_owner",
        ),
        (
            "sump_failure",
            "บ่อสูบน้ำหรือระบบปลายท่อขัดข้อง",
            "asset_owner_then_pipe_service_area",
        ),
        (
            "canal_obstruction",
            "คลองอุดตัน มีขยะ วัชพืช หรือสิ่งกีดขวาง",
            "canal_service_area_then_asset_owner",
        ),
        (
            "canal_overflow",
            "น้ำล้นคลองหรือระดับคลองกระทบพื้นที่",
            "canal_service_area_then_water_control",
        ),
        (
            "canal_infrastructure",
            "เขื่อนริมคลองหรือโครงสร้างคลองชำรุด",
            "asset_owner_then_canal_service_area",
        ),
        (
            "pump_gate_tunnel_failure",
            "สถานีสูบน้ำ ประตูระบายน้ำ หรืออุโมงค์ขัดข้อง",
            "asset_owner_then_water_control",
        ),
        (
            "high_tide_or_external_water",
            "น้ำทะเลหนุน น้ำเหนือ หรือน้ำภายนอกพื้นที่",
            "water_control_then_district_coordination",
        ),
        (
            "life_safety_rescue",
            "เหตุช่วยชีวิตหรืออพยพประชาชนจากน้ำท่วม",
            "incident_command_requires_verified_raci",
        ),
    ]
    rows = [
        {
            "incident_type_hash_sha256": stable_hash(
                SCHEMA_VERSION, "incident_type", code
            ),
            "incident_type_code": code,
            "incident_type_name_th": name,
            "candidate_lookup_strategy": strategy,
            "routing_status": "requires_verified_raci",
            "is_official_legal_assignment": False,
        }
        for code, name, strategy in definitions
    ]
    return {
        "metadata": {
            "schema_version": SCHEMA_VERSION,
            "generated_at": utc_now(),
            "notice": (
                "Incident types support deterministic lookup only. "
                "They do not assign legal responsibility."
            ),
        },
        "incident_types": rows,
    }


def build_official_document_evidence(
    agency_ids: set[str],
) -> dict[str, Any]:
    source_path = INPUT_DIR / "official_document_evidence.json"
    payload = read_json(source_path)
    documents = payload.get("documents", [])
    mission_duties = payload.get("mission_duties", [])
    sop_processes = payload.get("sop_processes", [])
    errors: list[str] = []
    document_rows: list[dict[str, Any]] = []
    document_by_id: dict[str, dict[str, Any]] = {}
    sha_pattern = re.compile(r"^[0-9a-f]{64}$")

    for source in documents:
        row = dict(source)
        document_id = clean_text(row.get("document_id"))
        source_url = clean_text(row.get("source_url"))
        access_status = clean_text(row.get("source_access_status"))
        if not document_id or document_id in document_by_id:
            errors.append(f"invalid or duplicate document_id: {document_id}")
            continue
        parsed = urlparse(source_url or "")
        if (
            parsed.scheme != "https"
            or not is_allowed_legal_source_host(parsed.hostname or "")
        ):
            errors.append(f"{document_id}: source URL host is not allowed")
        if access_status == "downloaded":
            if not sha_pattern.fullmatch(
                clean_text(row.get("document_sha256")) or ""
            ):
                errors.append(f"{document_id}: invalid document SHA-256")
            if not isinstance(row.get("page_count"), int) or (
                row["page_count"] < 1
            ):
                errors.append(f"{document_id}: invalid page_count")
            if not isinstance(row.get("file_size_bytes"), int) or (
                row["file_size_bytes"] < 1
            ):
                errors.append(f"{document_id}: invalid file_size_bytes")
        elif access_status == "blocked_http_418":
            if row.get("document_sha256") is not None:
                errors.append(
                    f"{document_id}: blocked document must not claim a hash"
                )
        else:
            errors.append(f"{document_id}: invalid source_access_status")
        if row.get("local_binary_committed") is not False:
            errors.append(
                f"{document_id}: local_binary_committed must be false"
            )
        row.update(
            {
                "document_evidence_hash_sha256": stable_hash(
                    SCHEMA_VERSION,
                    "official_document_evidence",
                    document_id,
                    source_url,
                    access_status,
                    row.get("document_sha256"),
                ),
                "verification_status": "pending_legal_review",
                "is_official_legal_assignment": False,
                "requires_human_approval": True,
                "is_document_evidence_hash": True,
                "is_document_content_hash": False,
            }
        )
        document_by_id[document_id] = row
        document_rows.append(row)

    def validate_pages(
        record_id: str,
        source_document_id: str,
        pages: Any,
    ) -> None:
        document = document_by_id.get(source_document_id)
        if not document:
            errors.append(f"{record_id}: unknown source_document_id")
            return
        if document.get("source_access_status") != "downloaded":
            errors.append(f"{record_id}: source document was not downloaded")
            return
        if not isinstance(pages, list) or not pages:
            errors.append(f"{record_id}: source_pdf_pages are required")
            return
        page_count = document["page_count"]
        if any(
            not isinstance(page, int) or page < 1 or page > page_count
            for page in pages
        ):
            errors.append(f"{record_id}: source_pdf_pages out of range")

    mission_rows: list[dict[str, Any]] = []
    for source in mission_duties:
        row = dict(source)
        record_id = clean_text(row.get("mission_duty_id")) or ""
        document_id = clean_text(row.get("source_document_id")) or ""
        validate_pages(record_id, document_id, row.get("source_pdf_pages"))
        agency_id = clean_text(row.get("agency_id"))
        agency_selector = clean_text(row.get("agency_selector"))
        if agency_id and agency_id not in agency_ids:
            errors.append(f"{record_id}: unknown agency_id")
        if not agency_id and agency_selector != "bma-district-*":
            errors.append(f"{record_id}: agency_id or district selector required")
        if not isinstance(row.get("mission_items_th"), list) or not row[
            "mission_items_th"
        ]:
            errors.append(f"{record_id}: mission_items_th are required")
        document = document_by_id.get(document_id, {})
        row.update(
            {
                "mission_duty_hash_sha256": stable_hash(
                    SCHEMA_VERSION,
                    "mission_duty_evidence",
                    record_id,
                    document.get("document_sha256"),
                    canonical_json(row.get("source_pdf_pages")),
                    agency_id or agency_selector,
                    canonical_json(row.get("mission_items_th")),
                ),
                "verification_status": "pending_legal_review",
                "is_official_legal_assignment": False,
                "requires_human_approval": True,
                "contains_personal_data": False,
            }
        )
        mission_rows.append(row)

    sop_rows: list[dict[str, Any]] = []
    for source in sop_processes:
        row = dict(source)
        record_id = clean_text(row.get("sop_process_id")) or ""
        document_id = clean_text(row.get("source_document_id")) or ""
        validate_pages(record_id, document_id, row.get("source_pdf_pages"))
        owner_ids = row.get("owner_agency_ids", [])
        if not isinstance(owner_ids, list) or any(
            agency_id not in agency_ids for agency_id in owner_ids
        ):
            errors.append(f"{record_id}: invalid owner_agency_ids")
        if (
            not owner_ids
            and clean_text(row.get("owner_agency_selector"))
            != "bma-district-*"
        ):
            errors.append(
                f"{record_id}: owner agency or district selector required"
            )
        if not isinstance(row.get("steps"), list) or not row["steps"]:
            errors.append(f"{record_id}: SOP steps are required")
        document = document_by_id.get(document_id, {})
        row.update(
            {
                "sop_process_hash_sha256": stable_hash(
                    SCHEMA_VERSION,
                    "sop_process_evidence",
                    record_id,
                    document.get("document_sha256"),
                    canonical_json(row.get("source_pdf_pages")),
                    canonical_json(owner_ids),
                    row.get("owner_agency_selector"),
                    canonical_json(row.get("steps")),
                ),
                "verification_status": "pending_legal_review",
                "is_official_legal_assignment": False,
                "requires_human_approval": True,
                "contains_personal_data": False,
            }
        )
        sop_rows.append(row)

    checks = {
        "document_ids_unique": len(document_rows)
        == len({row["document_id"] for row in document_rows}),
        "document_evidence_hashes_unique": len(document_rows)
        == len(
            {
                row["document_evidence_hash_sha256"]
                for row in document_rows
            }
        ),
        "downloaded_documents_have_content_hash": all(
            sha_pattern.fullmatch(row["document_sha256"])
            for row in document_rows
            if row["source_access_status"] == "downloaded"
        ),
        "mission_duty_count_is_11": len(mission_rows) == 11,
        "mission_duty_ids_unique": len(mission_rows)
        == len({row["mission_duty_id"] for row in mission_rows}),
        "mission_duty_hashes_unique": len(mission_rows)
        == len(
            {row["mission_duty_hash_sha256"] for row in mission_rows}
        ),
        "sop_process_count_is_7": len(sop_rows) == 7,
        "sop_process_ids_unique": len(sop_rows)
        == len({row["sop_process_id"] for row in sop_rows}),
        "sop_process_hashes_unique": len(sop_rows)
        == len({row["sop_process_hash_sha256"] for row in sop_rows}),
        "all_records_pending_legal_review": all(
            row["verification_status"] == "pending_legal_review"
            and row["is_official_legal_assignment"] is False
            and row["requires_human_approval"] is True
            for row in document_rows + mission_rows + sop_rows
        ),
        "no_personal_data_in_extractions": all(
            row["contains_personal_data"] is False
            for row in mission_rows + sop_rows
        ),
        "input_validation_has_no_errors": not errors,
    }
    quality = {
        "metadata": {
            "schema_version": SCHEMA_VERSION,
            "generated_at": utc_now(),
            "status": "official_document_evidence_pending_legal_review",
            "document_count": len(document_rows),
            "downloaded_document_count": sum(
                row["source_access_status"] == "downloaded"
                for row in document_rows
            ),
            "mission_duty_count": len(mission_rows),
            "sop_process_count": len(sop_rows),
        },
        "checks": checks,
        "validation_errors": errors,
        "passed": all(checks.values()),
        "notice": (
            "Extracted duties and SOP steps are traceable official-document "
            "evidence, not verified legal assignments or dispatch authority."
        ),
    }
    write_json(
        EVIDENCE_DIR / "official_document_registry.json",
        {
            "metadata": payload.get("metadata", {}),
            "documents": document_rows,
        },
    )
    write_jsonl(
        EVIDENCE_DIR / "mission_duty_evidence_hash_index.jsonl",
        mission_rows,
    )
    write_jsonl(
        EVIDENCE_DIR / "sop_process_evidence_hash_index.jsonl",
        sop_rows,
    )
    write_json(EVIDENCE_DIR / "quality_report.json", quality)
    if not quality["passed"]:
        raise RuntimeError(
            "Official document evidence validation failed: "
            + "; ".join(errors)
        )
    return {
        "documents": document_rows,
        "mission_duties": mission_rows,
        "sop_processes": sop_rows,
        "quality": quality,
    }


def build_acquired_source_evidence(
    districts: "DistrictIndex",
    unresolved_asset_owners: list[dict[str, Any]],
    spatial_conflicts: list[dict[str, Any]],
) -> dict[str, Any]:
    payload = read_json(INPUT_DIR / "acquired_source_evidence.json")
    allowed_statuses = {
        "resolved",
        "candidate",
        "not_publicly_available",
        "requires_agency_confirmation",
    }
    errors: list[str] = []
    source_rows: list[dict[str, Any]] = []

    for source in payload.get("sources", []):
        row = dict(source)
        source_id = clean_text(row.get("source_id"))
        source_url = clean_text(row.get("source_url"))
        status = clean_text(row.get("evidence_status"))
        if not source_id:
            errors.append("acquired source is missing source_id")
            continue
        if not source_url or urlparse(source_url).scheme != "https":
            errors.append(f"{source_id}: source_url must use HTTPS")
        if status not in allowed_statuses:
            errors.append(f"{source_id}: invalid evidence_status")
        local_path = clean_text(row.get("local_path"))
        if local_path:
            path = ROOT / local_path
            if not path.is_file():
                errors.append(f"{source_id}: local_path does not exist")
            else:
                expected_hash = clean_text(row.get("local_file_sha256"))
                if expected_hash != file_sha256(path):
                    errors.append(f"{source_id}: local SHA-256 mismatch")
                if row.get("local_file_size_bytes") != path.stat().st_size:
                    errors.append(f"{source_id}: local file size mismatch")
        extracted_csv_path = clean_text(row.get("extracted_csv_path"))
        if extracted_csv_path:
            csv_path = ROOT / extracted_csv_path
            if not csv_path.is_file():
                errors.append(
                    f"{source_id}: extracted_csv_path does not exist"
                )
            else:
                if row.get("extracted_csv_sha256") != file_sha256(
                    csv_path
                ):
                    errors.append(
                        f"{source_id}: extracted CSV SHA-256 mismatch"
                    )
                if (
                    row.get("extracted_csv_size_bytes")
                    != csv_path.stat().st_size
                ):
                    errors.append(
                        f"{source_id}: extracted CSV size mismatch"
                    )
                with csv_path.open(
                    "r",
                    encoding="utf-8-sig",
                    newline="",
                ) as stream:
                    csv_rows = list(csv.DictReader(stream))
                if row.get("record_count") != len(csv_rows):
                    errors.append(
                        f"{source_id}: extracted CSV record count mismatch"
                    )
                date_like_width = re.compile(
                    r"(?:[A-Z][a-z]{2}|[0-9]{1,2}-[A-Z][a-z]{2}|"
                    r"[A-Z][a-z]{2}-[0-9]{1,2})"
                )
                anomaly_count = sum(
                    bool(
                        date_like_width.fullmatch(
                            clean_text(item.get("k_width")) or ""
                        )
                    )
                    for item in csv_rows
                )
                if row.get("date_like_width_value_count") != anomaly_count:
                    errors.append(
                        f"{source_id}: k_width anomaly count mismatch"
                    )
        row["acquired_source_hash_sha256"] = stable_hash(
            SCHEMA_VERSION,
            "acquired_source_evidence",
            source_id,
            source_url,
            row.get("local_file_sha256"),
            row.get("document_sha256"),
            status,
        )
        row["is_asset_ownership_certificate"] = False
        row["is_dispatch_authorization"] = False
        row["requires_human_review"] = status != "resolved"
        source_rows.append(row)

    source_rows.sort(key=lambda row: row["source_id"])
    write_jsonl(
        ACQUISITION_DIR / "source_evidence_hash_index.jsonl",
        source_rows,
    )

    source_hashes = {
        row["source_id"]: row["acquired_source_hash_sha256"]
        for row in source_rows
    }
    owner_rows = []
    for review in unresolved_asset_owners:
        row = {
            "review_hash_sha256": review["review_hash_sha256"],
            "entity_id": review["entity_id"],
            "entity_name_th": review.get("entity_name_th"),
            "district_code": review["district_code"],
            "district_name_th": review["district_name_th"],
            "spatial_hash_geohash7": review["spatial_hash_geohash7"],
            "source_owner_value": review.get("source_owner_value"),
            "resolution_status": "requires_agency_confirmation",
            "asset_owner_agency_id": None,
            "candidate_operational_agency_id": (
                f"bma-district-{review['district_code']}"
            ),
            "candidate_role": "geographic_jurisdiction_only",
            "public_source_result": (
                "Official public canal datasets contain identity, district, "
                "and custodian-type fields but no per-asset ownership "
                "certificate for this unnamed source feature."
            ),
            "required_evidence": (
                "Agency-issued asset register, transfer record, or certified "
                "custodian statement tied to the source entity or geometry."
            ),
            "supporting_source_hashes_sha256": sorted(source_hashes.values()),
            "is_placeholder": False,
            "may_auto_dispatch": False,
        }
        row["acquisition_resolution_hash_sha256"] = stable_hash(
            SCHEMA_VERSION,
            "asset_owner_resolution_status",
            row["review_hash_sha256"],
            row["resolution_status"],
            canonical_json(row["supporting_source_hashes_sha256"]),
        )
        owner_rows.append(row)
    write_jsonl(
        ACQUISITION_DIR / "asset_owner_resolution_status.jsonl",
        owner_rows,
    )

    conflict_rows = []
    for review in spatial_conflicts:
        polygon_code = review.get("polygon_district_code")
        status = "candidate" if polygon_code else "requires_agency_confirmation"
        row = {
            "review_hash_sha256": review["review_hash_sha256"],
            "entity_id": review["entity_id"],
            "entity_name_th": review.get("entity_name_th"),
            "source_layer": review["source_layer"],
            "source_district_value": review.get("source_district_value"),
            "selected_district_code": review["selected_district_code"],
            "selected_district_name_th": review[
                "selected_district_name_th"
            ],
            "polygon_district_code": polygon_code,
            "polygon_district_name_th": review.get(
                "polygon_district_name_th"
            ),
            "resolution_status": status,
            "candidate_district_code": (
                polygon_code or review["selected_district_code"]
            ),
            "candidate_method": (
                "authoritative_polygon_candidate"
                if polygon_code
                else "source_district_candidate_no_polygon_match"
            ),
            "required_evidence": (
                "Authoritative boundary version and source-owner confirmation "
                "for boundary, cross-district, or no-polygon cases."
            ),
            "is_placeholder": False,
            "may_auto_dispatch": False,
        }
        row["acquisition_resolution_hash_sha256"] = stable_hash(
            SCHEMA_VERSION,
            "spatial_conflict_resolution_status",
            row["review_hash_sha256"],
            status,
            row["candidate_district_code"],
        )
        conflict_rows.append(row)
    write_jsonl(
        ACQUISITION_DIR / "spatial_conflict_resolution_status.jsonl",
        conflict_rows,
    )

    district_sop_rows = []
    for district in sorted(
        districts.features,
        key=lambda item: item["district_code"],
    ):
        code = district["district_code"]
        is_bang_kho_laem = code == "1031"
        row = {
            "district_code": code,
            "district_name_th": district["district_name_th"],
            "district_agency_id": f"bma-district-{code}",
            "plan_existence_period": "2566",
            "plan_existence_source_document_id": (
                "bma-integrated-flood-inspection-report-2566-pdf"
            ),
            "plan_existence_source_pdf_pages": [16],
            "public_district_sop_document_id": (
                "bang-kho-laem-flood-response-plan-2563-pdf"
                if is_bang_kho_laem
                else None
            ),
            "public_district_sop_period": (
                "2563" if is_bang_kho_laem else None
            ),
            "resolution_status": (
                "candidate"
                if is_bang_kho_laem
                else "requires_agency_confirmation"
            ),
            "current_sop_verified": False,
            "current_order_number": None,
            "current_effective_from": None,
            "current_effective_to": None,
            "required_evidence": (
                "Current district flood plan/order, approval date, effective "
                "period, role-based RACI, escalation, and revocation status."
            ),
            "is_placeholder": False,
            "may_auto_dispatch": False,
        }
        row["district_sop_availability_hash_sha256"] = stable_hash(
            SCHEMA_VERSION,
            "district_sop_availability",
            code,
            row["public_district_sop_document_id"],
            row["resolution_status"],
        )
        district_sop_rows.append(row)
    write_jsonl(
        ACQUISITION_DIR / "district_sop_availability.jsonl",
        district_sop_rows,
    )

    gap_rows = [
        {
            "gap_id": "GAP-ASSET-OWNER-247",
            "subject": "Per-asset ownership or certified custody",
            "record_count": len(owner_rows),
            "resolution_status": "requires_agency_confirmation",
            "result": "No public source acquired contains a certificate tied to the 247 unnamed canal features.",
            "operational_effect": "Geographic routing remains candidate-only.",
        },
        {
            "gap_id": "GAP-SPATIAL-CANDIDATE-103",
            "subject": "Source district conflicts with a polygon match",
            "record_count": sum(
                row["resolution_status"] == "candidate"
                for row in conflict_rows
            ),
            "resolution_status": "candidate",
            "result": "A polygon district candidate exists but the source conflict is retained.",
            "operational_effect": "Human review is required before dispatch.",
        },
        {
            "gap_id": "GAP-SPATIAL-NO-POLYGON-68",
            "subject": "Source district conflicts without a polygon match",
            "record_count": sum(
                row["resolution_status"]
                == "requires_agency_confirmation"
                for row in conflict_rows
            ),
            "resolution_status": "requires_agency_confirmation",
            "result": "No authoritative polygon candidate was available for these records.",
            "operational_effect": "Use the source district only as a review candidate.",
        },
        {
            "gap_id": "GAP-SEDGIS-ITEM-IDENTITY",
            "subject": "Exact SEDGIS item and service identity",
            "record_count": 2,
            "resolution_status": "candidate",
            "result": "Exact public item, proxy, upstream service URLs, and item timestamps were acquired.",
            "operational_effect": "The checked-in GeoJSON still lacks an upstream export hash proving byte-level lineage.",
        },
        {
            "gap_id": "GAP-SEDGIS-FORMAL-LICENSE",
            "subject": "Formal machine-readable SEDGIS license",
            "record_count": 1,
            "resolution_status": "not_publicly_available",
            "result": "ArcGIS licenseInfo and the BMA Open Data catalog license are not specified; a metadata PDF says use freely.",
            "operational_effect": "Retain the usage statement but request a formal license before redistribution decisions.",
        },
        {
            "gap_id": "GAP-CANAL-CSV-WIDTH-COERCION",
            "subject": "Canal-width values coerced to date-like CSV text",
            "record_count": 1481,
            "resolution_status": "requires_agency_confirmation",
            "result": "The official CSV contains date-like k_width values such as 6-Apr in 1,481 of 1,770 records.",
            "operational_effect": "Do not parse those values as width ranges; request a non-coerced source export or authoritative correction.",
        },
        {
            "gap_id": "GAP-DISTRICT-SOP-CURRENT",
            "subject": "Current district-specific SOP and order",
            "record_count": 50,
            "resolution_status": "requires_agency_confirmation",
            "result": "An official report confirms all 50 plans existed in 2566; one historical district SOP was acquired.",
            "operational_effect": "No district is promoted to current verified SOP status.",
        },
        {
            "gap_id": "GAP-DISPATCH-RACI",
            "subject": "Action-specific RACI and dispatch authorization",
            "record_count": 50,
            "resolution_status": "requires_agency_confirmation",
            "result": "General legal and plan roles exist, but target-agency/action permissions and current approvals are not public for every district.",
            "operational_effect": "The system may recommend agencies but must not auto-dispatch.",
        },
        {
            "gap_id": "GAP-INTEGRITY-SIGNATURE",
            "subject": "Project integrity-manifest signature",
            "record_count": 1,
            "resolution_status": "not_publicly_available",
            "result": "A valid signature cannot be scraped; it must be issued by the project CI/KMS/Cosign identity.",
            "operational_effect": "Checksums detect changes but do not authenticate the publisher.",
        },
    ]
    for row in gap_rows:
        row["gap_resolution_hash_sha256"] = stable_hash(
            SCHEMA_VERSION,
            "gap_resolution",
            row["gap_id"],
            row["resolution_status"],
            row["record_count"],
            row["result"],
        )
    write_jsonl(
        ACQUISITION_DIR / "gap_resolution_registry.jsonl",
        gap_rows,
    )

    request_rows = [
        {
            "request_id": "REQ-ASSET-OWNER",
            "request_to_role": "กองระบบคลอง สำนักการระบายน้ำ และสำนักงานเขตที่เกี่ยวข้อง",
            "requested_dataset": "ทะเบียนเจ้าของหรือผู้ดูแลทรัพย์สินสำหรับคลอง 247 รายการ",
            "required_join_keys": "entity_id, canal_code, geometry, district_code",
            "required_evidence": "เลขทะเบียนทรัพย์สิน หนังสือโอน/มอบหมาย หน่วยงานผู้ดูแล วันที่มีผล",
            "contains_personal_data_required": False,
            "current_status": "requires_agency_confirmation",
        },
        {
            "request_id": "REQ-SPATIAL-CONFLICT",
            "request_to_role": "กองสารสนเทศภูมิศาสตร์ กรุงเทพมหานคร",
            "requested_dataset": "ขอบเขต 50 เขตฉบับอ้างอิงและผลวินิจฉัย 171 จุดขัดแย้ง",
            "required_join_keys": "entity_id, geometry, boundary_version",
            "required_evidence": "service item, export timestamp, version, CRS, geometry hash",
            "contains_personal_data_required": False,
            "current_status": "requires_agency_confirmation",
        },
        {
            "request_id": "REQ-SEDGIS-LICENSE",
            "request_to_role": "กองสารสนเทศภูมิศาสตร์ กรุงเทพมหานคร",
            "requested_dataset": "หนังสือหรือ URL สัญญาอนุญาตของ SEDGIS",
            "required_join_keys": "arcgis_item_id, service_url",
            "required_evidence": "license name/version, permitted use, redistribution, attribution",
            "contains_personal_data_required": False,
            "current_status": "not_publicly_available",
        },
        {
            "request_id": "REQ-CANAL-NATIVE-EXPORT",
            "request_to_role": "กองระบบคลอง สำนักการระบายน้ำ และกองสารสนเทศภูมิศาสตร์",
            "requested_dataset": "Native export ของตารางคลองที่ไม่แปลง k_width เป็นรูปแบบวันที่",
            "required_join_keys": "k_code, k_name, khet_name, k_type",
            "required_evidence": "CSV/GeoPackage พร้อม schema, export timestamp, version และ SHA-256",
            "contains_personal_data_required": False,
            "current_status": "requires_agency_confirmation",
        },
        {
            "request_id": "REQ-DISTRICT-SOP",
            "request_to_role": "สำนักงานเขตทั้ง 50 เขต",
            "requested_dataset": "แผน/คำสั่งป้องกันและแก้ไขน้ำท่วมฉบับปัจจุบัน",
            "required_join_keys": "district_code, order_number, effective_from",
            "required_evidence": "PDF ฉบับอนุมัติ RACI escalation SLA และสถานะยกเลิก",
            "contains_personal_data_required": False,
            "current_status": "requires_agency_confirmation",
        },
        {
            "request_id": "REQ-DISPATCH-RACI",
            "request_to_role": "สำนักป้องกันและบรรเทาสาธารณภัย สำนักการระบายน้ำ และสำนักงานเขต",
            "requested_dataset": "สิทธิ์สั่งการและ dispatch แบบ role-based",
            "required_join_keys": "actor_role, target_agency, action, district_code, severity",
            "required_evidence": "ฐานกฎหมาย คำสั่ง วันที่มีผล ผู้ตรวจและผู้อนุมัติ",
            "contains_personal_data_required": False,
            "current_status": "requires_agency_confirmation",
        },
        {
            "request_id": "REQ-INTEGRITY-SIGNATURE",
            "request_to_role": "เจ้าของโครงการและผู้ดูแล CI/KMS",
            "requested_dataset": "Cosign identity และ release signing policy",
            "required_join_keys": "repository, workflow, commit_sha, artifact_digest",
            "required_evidence": "OIDC issuer, certificate identity, Rekor entry or KMS key policy",
            "contains_personal_data_required": False,
            "current_status": "not_publicly_available",
        },
    ]
    write_csv(
        ACQUISITION_DIR / "agency_data_request_packet.csv",
        request_rows,
    )

    status_values = {
        row["resolution_status"]
        for row in owner_rows
        + conflict_rows
        + district_sop_rows
        + gap_rows
    }
    checks = {
        "input_validation_has_no_errors": not errors,
        "source_ids_unique": len(source_rows)
        == len({row["source_id"] for row in source_rows}),
        "source_hashes_unique": len(source_rows)
        == len(
            {
                row["acquired_source_hash_sha256"]
                for row in source_rows
            }
        ),
        "owner_review_count_preserved": len(owner_rows)
        == len(unresolved_asset_owners)
        == 247,
        "no_owner_record_falsely_resolved": not any(
            row["resolution_status"] == "resolved"
            or row["asset_owner_agency_id"] is not None
            for row in owner_rows
        ),
        "spatial_conflict_count_preserved": len(conflict_rows)
        == len(spatial_conflicts)
        == 171,
        "district_sop_covers_all_50_districts": len(district_sop_rows)
        == 50,
        "all_resolution_statuses_allowed": status_values
        <= allowed_statuses,
        "no_placeholder_records": not any(
            row.get("is_placeholder")
            for row in owner_rows + conflict_rows + district_sop_rows
        ),
        "request_packet_requires_no_personal_data": not any(
            row["contains_personal_data_required"]
            for row in request_rows
        ),
    }
    report = {
        "metadata": {
            "schema_version": SCHEMA_VERSION,
            "generated_at": utc_now(),
            "scope": "Official-source acquisition and unresolved-gap status",
            "operational_use": False,
        },
        "counts": {
            "source_evidence": len(source_rows),
            "asset_owner_status": len(owner_rows),
            "spatial_conflict_status": len(conflict_rows),
            "district_sop_availability": len(district_sop_rows),
            "gap_resolution": len(gap_rows),
            "agency_data_requests": len(request_rows),
        },
        "status_counts": dict(
            sorted(
                Counter(
                    row["resolution_status"]
                    for row in owner_rows
                    + conflict_rows
                    + district_sop_rows
                    + gap_rows
                ).items()
            )
        ),
        "checks": checks,
        "validation_errors": errors,
        "passed": all(checks.values()),
        "notice": (
            "Acquired public evidence reduces provenance gaps but does not "
            "create asset ownership certificates, current district approval, "
            "dispatch authority, or a project signing identity."
        ),
    }
    write_json(ACQUISITION_DIR / "quality_report.json", report)
    if not report["passed"]:
        raise RuntimeError(
            "Acquired source evidence validation failed: "
            + "; ".join(errors)
        )
    return {
        "sources": source_rows,
        "owner_statuses": owner_rows,
        "spatial_statuses": conflict_rows,
        "district_sop_rows": district_sop_rows,
        "gap_rows": gap_rows,
        "request_rows": request_rows,
        "quality": report,
    }


def build_district_office_flood_process_index(
    districts: "DistrictIndex",
    service_area_rows: list[dict[str, Any]],
    evidence: dict[str, Any],
) -> list[dict[str, Any]]:
    mission = next(
        row
        for row in evidence["mission_duties"]
        if row.get("agency_selector") == "bma-district-*"
    )
    common_district_sops = sorted(
        (
            row
            for row in evidence["sop_processes"]
            if row.get("owner_agency_selector") == "bma-district-*"
        ),
        key=lambda row: row["sop_process_id"],
    )
    district_specific_sops: dict[str, list[dict[str, Any]]] = defaultdict(
        list
    )
    for row in evidence["sop_processes"]:
        district_code = clean_text(row.get("district_code"))
        if district_code:
            district_specific_sops[district_code].append(row)
    service_areas_by_district: dict[str, list[dict[str, Any]]] = defaultdict(
        list
    )
    for row in service_area_rows:
        service_areas_by_district[row["district_code"]].append(row)

    rows = []
    for district in sorted(
        districts.features,
        key=lambda row: row["district_code"],
    ):
        district_code = district["district_code"]
        district_services = sorted(
            service_areas_by_district[district_code],
            key=lambda row: row["agency_id"],
        )
        specific_sops = sorted(
            district_specific_sops.get(district_code, []),
            key=lambda row: row["sop_process_id"],
        )
        applicable_sops = [*common_district_sops, *specific_sops]
        source_hashes = [
            mission["mission_duty_hash_sha256"],
            *(
                row["sop_process_hash_sha256"]
                for row in applicable_sops
            ),
            *(
                row["service_area_hash_sha256"]
                for row in district_services
            ),
        ]
        process_stages = [
            {
                "sequence": 1,
                "stage_code": "monitor_receive_report",
                "action_th": (
                    "ติดตามฝน จุดเสี่ยง รับแจ้งเหตุ และรายงานสถานการณ์"
                ),
                "owner_role_th": "เจ้าหน้าที่สำนักงานเขต",
            },
            {
                "sequence": 2,
                "stage_code": "district_command",
                "action_th": (
                    "ผู้อำนวยการเขตสั่งการ และจัดตั้งศูนย์บัญชาการ"
                    "เมื่อเข้าเงื่อนไขสาธารณภัย"
                ),
                "owner_role_th": "ผู้อำนวยการเขต",
            },
            {
                "sequence": 3,
                "stage_code": "public_works_inspection",
                "action_th": "ฝ่ายโยธาสำรวจและตรวจสอบพื้นที่",
                "owner_role_th": "ฝ่ายโยธา/กลุ่มงานระบายน้ำ",
                "manual_document_duration_days": 2,
            },
            {
                "sequence": 4,
                "stage_code": "resource_preparation",
                "action_th": "เตรียมกำลัง วัสดุ อุปกรณ์ และเครื่องสูบน้ำ",
                "owner_role_th": "ฝ่ายโยธาและหน่วยสนับสนุน",
                "manual_document_duration_days": 2,
            },
            {
                "sequence": 5,
                "stage_code": "operate_coordinate_report",
                "action_th": (
                    "ดำเนินการแก้ไข ประสาน DDS/หน่วยสนับสนุน "
                    "และรายงานผล"
                ),
                "owner_role_th": "สำนักงานเขตและหน่วยงานที่เกี่ยวข้อง",
                "manual_document_duration_days": 3,
            },
            {
                "sequence": 6,
                "stage_code": "damage_recovery_close",
                "action_th": (
                    "สำรวจความเสียหาย ช่วยเหลือ ฟื้นฟู และสรุปรายงาน"
                ),
                "owner_role_th": "ศูนย์บัญชาการเหตุการณ์สำนักงานเขต",
            },
        ]
        row = {
            "district_code": district_code,
            "district_name_th": district["district_name_th"],
            "district_agency_id": f"bma-district-{district_code}",
            "district_agency_name_th": (
                f"สำนักงานเขต{district['district_name_th']}"
            ),
            "process_scope": "common_bma_district_flood_process_candidate",
            "process_stages": process_stages,
            "mission_duty_hash_sha256": mission[
                "mission_duty_hash_sha256"
            ],
            "sop_process_hashes_sha256": [
                row["sop_process_hash_sha256"] for row in applicable_sops
            ],
            "district_specific_sop_hashes_sha256": [
                row["sop_process_hash_sha256"] for row in specific_sops
            ],
            "service_area_candidate_agency_ids": [
                row["agency_id"] for row in district_services
            ],
            "service_area_hashes_sha256": [
                row["service_area_hash_sha256"]
                for row in district_services
            ],
            "source_hashes_sha256": source_hashes,
            "district_specific_order_available": bool(specific_sops),
            "district_specific_sop_verified": False,
            "district_specific_sop_status": (
                "candidate_historical_public_document"
                if specific_sops
                else "requires_agency_confirmation"
            ),
            "timing_is_emergency_response_sla": False,
            "timing_notice": (
                "Durations are transcribed from the common public-works "
                "manual workflow and must not be treated as emergency "
                "dispatch or life-safety SLA."
            ),
            "applicability_note": (
                "A public district-specific historical SOP was found, but "
                "its current validity has not been confirmed."
                if specific_sops
                else (
                    "Materialized from common BMA plans/manuals for lookup. "
                    "No district-specific order for this district has been "
                    "verified."
                )
            ),
            "verification_status": "pending_district_confirmation",
            "is_official_legal_assignment": False,
            "requires_district_confirmation": True,
            "requires_human_approval": True,
        }
        row["district_process_hash_sha256"] = stable_hash(
            SCHEMA_VERSION,
            "district_office_flood_process",
            district_code,
            canonical_json(source_hashes),
            canonical_json(process_stages),
        )
        rows.append(row)
    write_jsonl(
        EVIDENCE_DIR
        / "district_office_flood_process_hash_index.jsonl",
        rows,
    )
    return rows


def build_data_source_registry(
    legal_sources: dict[str, Any],
    evidence: dict[str, Any],
    acquired_sources: list[dict[str, Any]],
    legal_authority_sources: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    local_sources: dict[str, dict[str, Any]] = {
        "districts": {
            "path": GEOJSON_DIR / "districts.geojson",
            "source_category": "administrative_boundary",
        }
    }
    for layer, config in {**ASSET_LAYERS, **SIGNAL_LAYERS}.items():
        local_sources.setdefault(
            layer,
            {
                "path": config["path"],
                "source_category": (
                    "water_telemetry_snapshot"
                    if layer == "water_level_station"
                    else "bma_spatial_operational_data"
                ),
            },
        )

    rows: list[dict[str, Any]] = []
    seen_paths: set[Path] = set()
    for source_id, source in local_sources.items():
        path = source["path"]
        if path in seen_paths:
            continue
        seen_paths.add(path)
        is_telemetry = path == WATER_DIR / "water_latest_geojson.json"
        is_canal_layer = source_id == "canals"
        row = {
            "source_id": f"local-{source_id}",
            "source_kind": "checked_in_normalized_dataset",
            "source_category": source["source_category"],
            "publisher_th": "กรุงเทพมหานคร",
            "local_path": path.relative_to(ROOT).as_posix(),
            "local_file_sha256": file_sha256(path),
            "local_file_size_bytes": path.stat().st_size,
            "source_url": (
                "https://weather.bangkok.go.th/water/PageMap/GoogleMap"
                if is_telemetry
                else (
                    "https://bmagis.bangkok.go.th/portal/sharing/rest/"
                    "content/items/3915f994743647fe899ab4944dc0e2c6"
                    "?f=pjson"
                    if is_canal_layer
                    else "https://bmasedgis.bangkok.go.th/"
                )
            ),
            "source_url_precision": (
                "exact_endpoint"
                if is_telemetry
                else (
                    "exact_item_candidate_not_verified_export"
                    if is_canal_layer
                    else "generic_portal_missing_export_url"
                )
            ),
            "upstream_content_hash_available": False,
            "provenance_status": (
                "partial_missing_raw_response_hash"
                if is_telemetry
                else (
                    "partial_exact_item_candidate_missing_matching_"
                    "export_hash_and_formal_license"
                    if is_canal_layer
                    else (
                        "incomplete_missing_exact_export_url_fetch_time_"
                        "version_and_license"
                    )
                )
            ),
            "used_by_hash_datasets": [
                "candidate-responsibility-assignments"
            ],
        }
        rows.append(row)

    for source in legal_sources["sources"]:
        used_by = ["candidate-legal-reference"]
        if source["legal_basis_id"] in {
            "dds-pipe-division-duties",
            "dds-canal-division-duties",
        }:
            used_by.extend(
                [
                    "candidate-agency-service-area",
                    "candidate-agency-incident-capability",
                ]
            )
        rows.append(
            {
                "source_id": f"web-{source['legal_basis_id']}",
                "source_kind": "official_web_reference",
                "source_category": source["source_class"],
                "publisher_th": "กรุงเทพมหานคร",
                "local_path": None,
                "local_file_sha256": None,
                "source_url": source["url"],
                "source_url_precision": "exact_reference_url",
                "upstream_content_hash_available": False,
                "provenance_status": "reference_identity_only",
                "used_by_hash_datasets": used_by,
            }
        )

    mission_document_ids = {
        row["source_document_id"] for row in evidence["mission_duties"]
    }
    sop_document_ids = {
        row["source_document_id"] for row in evidence["sop_processes"]
    }
    district_document_ids = {
        row["source_document_id"]
        for row in evidence["mission_duties"]
        if row.get("agency_selector") == "bma-district-*"
    } | {
        row["source_document_id"]
        for row in evidence["sop_processes"]
        if row.get("owner_agency_selector") == "bma-district-*"
    }
    for document in evidence["documents"]:
        used_by = ["evidence-data-source-registry"]
        if document["document_id"] in mission_document_ids:
            used_by.append("evidence-mission-duty")
        if document["document_id"] in sop_document_ids:
            used_by.append("evidence-sop-process")
        if document["document_id"] in district_document_ids:
            used_by.append("evidence-district-office-flood-process")
        rows.append(
            {
                "source_id": f"document-{document['document_id']}",
                "source_kind": "official_document",
                "source_category": document["document_type"],
                "publisher_th": document["publisher_th"],
                "local_path": None,
                "local_file_sha256": None,
                "source_url": document["source_url"],
                "source_url_precision": "exact_document_url",
                "upstream_content_hash_available": bool(
                    document.get("document_sha256")
                ),
                "upstream_document_sha256": document.get(
                    "document_sha256"
                ),
                "provenance_status": (
                    "content_hash_captured_pending_legal_review"
                    if document["source_access_status"] == "downloaded"
                    else "source_access_blocked_no_content_hash"
                ),
                "used_by_hash_datasets": used_by,
            }
        )

    for source in legal_authority_sources:
        rows.append(
            {
                "source_id": (
                    f"legal-authority-{source['source_id']}"
                ),
                "source_kind": "checked_in_official_legal_document",
                "source_category": source["document_type"],
                "publisher_th": (
                    "สำนักงานกฎหมายและคดี กรุงเทพมหานคร"
                ),
                "local_path": source["local_path"],
                "local_file_sha256": source["actual_sha256"],
                "local_file_size_bytes": source[
                    "local_file_size_bytes"
                ],
                "source_url": source["source_url"],
                "source_url_precision": "exact_official_document_url",
                "upstream_content_hash_available": True,
                "upstream_document_sha256": source["actual_sha256"],
                "provenance_status": (
                    "official_copy_checked_in_pending_gazette_"
                    "currency_and_legal_review"
                ),
                "used_by_hash_datasets": [
                    "legal-authority-source-registry",
                    "legal-authority-provisions",
                    "legal-authority-district-candidates",
                ],
            }
        )

    for source in acquired_sources:
        rows.append(
            {
                "source_id": f"acquired-{source['source_id']}",
                "source_kind": source["source_kind"],
                "source_category": "gap_resolution_evidence",
                "publisher_th": source["publisher_th"],
                "local_path": source.get("local_path"),
                "local_file_sha256": source.get("local_file_sha256"),
                "local_file_size_bytes": source.get(
                    "local_file_size_bytes"
                ),
                "source_url": source["source_url"],
                "source_url_precision": "exact_acquired_source_url",
                "upstream_content_hash_available": bool(
                    source.get("document_sha256")
                    or source.get("local_file_sha256")
                ),
                "upstream_document_sha256": source.get(
                    "document_sha256"
                ),
                "formal_license_status": source.get(
                    "formal_license_status"
                ),
                "provenance_status": (
                    f"acquired_{source['evidence_status']}"
                ),
                "used_by_hash_datasets": [
                    "acquisition-source-evidence",
                    "acquisition-gap-resolution",
                ],
            }
        )

    for row in rows:
        row["data_source_hash_sha256"] = stable_hash(
            SCHEMA_VERSION,
            "data_source_registry",
            row["source_id"],
            row["source_url"],
            row.get("local_file_sha256"),
            row.get("upstream_document_sha256"),
            row["provenance_status"],
        )
    rows.sort(key=lambda row: row["source_id"])
    write_jsonl(
        EVIDENCE_DIR / "data_source_registry_hash_index.jsonl",
        rows,
    )
    return rows


def write_ingestion_risk_report(
    data_source_rows: list[dict[str, Any]],
    unresolved_asset_owners: list[dict[str, Any]],
    spatial_conflicts: list[dict[str, Any]],
) -> None:
    findings = [
        {
            "finding_id": "ING-001",
            "severity": "critical",
            "status": "fixed",
            "title": "TLS certificate verification was disabled",
            "evidence": "scripts/run_scraper.py changed to secure defaults",
            "control": (
                "Use system CA validation; never install an unverified "
                "global SSL context."
            ),
        },
        {
            "finding_id": "ING-002",
            "severity": "high",
            "status": "fixed",
            "title": "Redirect and response origin were not validated",
            "evidence": (
                "Scraper validates HTTPS/exact host before following a "
                "redirect and rechecks the final URL"
            ),
            "control": "Validate requested and final URL against allowlist.",
        },
        {
            "finding_id": "ING-003",
            "severity": "high",
            "status": "partially_resolved",
            "title": "SEDGIS layer provenance is partially resolved",
            "evidence": (
                "Exact canal item, service, and source URLs plus item "
                "timestamps were acquired. The checked-in GeoJSON still "
                "lacks a matching upstream export checksum and a formal "
                "published license."
            ),
            "control": (
                "Re-export each layer with an immutable raw manifest and "
                "obtain a formal license statement before production use."
            ),
        },
        {
            "finding_id": "ING-004",
            "severity": "high",
            "status": "open",
            "title": "Asset owner values remain unresolved",
            "evidence": (
                f"{len(unresolved_asset_owners)} source records require "
                "manual owner review."
            ),
            "control": "Obtain certified asset owner/custodian registry.",
        },
        {
            "finding_id": "ING-005",
            "severity": "high",
            "status": "open",
            "title": "Source district text conflicts with polygon",
            "evidence": (
                f"{len(spatial_conflicts)} records have spatial conflicts."
            ),
            "control": "Resolve against authoritative district geometry.",
        },
        {
            "finding_id": "ING-006",
            "severity": "medium",
            "status": "fixed_for_future_fetches",
            "title": "Raw source response integrity was not recorded",
            "evidence": (
                "New scraper outputs source_response_sha256; existing "
                "snapshots predate this control."
            ),
            "control": "Retain raw response hash and fetched timestamp.",
        },
        {
            "finding_id": "ING-007",
            "severity": "medium",
            "status": "fixed",
            "title": "Response size, MIME, and UTF-8 were not strict",
            "evidence": (
                "Scraper now limits response bytes and validates content "
                "type and strict UTF-8."
            ),
            "control": "Fail closed on malformed or oversized responses.",
        },
        {
            "finding_id": "ING-008",
            "severity": "medium",
            "status": "fixed",
            "title": "Empty history parse could be treated as success",
            "evidence": (
                "Zero-series history and mismatched cached station IDs now "
                "fail validation."
            ),
            "control": "Quarantine parser-empty histories as source errors.",
        },
        {
            "finding_id": "ING-009",
            "severity": "medium",
            "status": "open",
            "title": "Official mission evidence is not legal approval",
            "evidence": (
                "Mission/SOP evidence and district processes remain pending "
                "legal and district confirmation."
            ),
            "control": "Two-person legal review before verified promotion.",
        },
        {
            "finding_id": "ING-010",
            "severity": "medium",
            "status": "open",
            "title": "Integrity manifest is unsigned",
            "evidence": "signature_status is unsigned",
            "control": "Sign releases with a managed key or CI attestation.",
        },
    ]
    write_json(
        SECURITY_DIR / "ingestion_risk_report.json",
        {
            "metadata": {
                "schema_version": SCHEMA_VERSION,
                "generated_at": utc_now(),
                "scope": "Scraping, source lineage, and hash ingestion",
                "data_source_count": len(data_source_rows),
            },
            "summary": {
                "finding_count": len(findings),
                "open_count": sum(
                    row["status"] == "open" for row in findings
                ),
                "fixed_count": sum(
                    row["status"] == "fixed" for row in findings
                ),
                "partial_count": sum(
                    row["status"]
                    in {
                        "fixed_for_future_fetches",
                        "partially_resolved",
                    }
                    for row in findings
                ),
            },
            "findings": findings,
        },
    )


def write_security_policy() -> None:
    write_json(
        SECURITY_DIR / "security_policy.json",
        {
            "metadata": {
                "schema_version": SCHEMA_VERSION,
                "generated_at": utc_now(),
                "scope": "Responsibility hash-index artifacts only",
            },
            "classifications": {
                "acquisition": "public_official_evidence_mixed_status",
                "candidate": "internal_operational_unverified",
                "evidence": "public_official_document_pending_review",
                "inputs": "restricted_review_input",
                "prepared": "derived_analytical_unverified",
                "normalized": "derived_analytical_unverified",
                "review": "internal_manual_review",
                "verified": "controlled_operational_verified",
                "visualization": "static_analytical_non_operational",
            },
            "promotion_controls": {
                "candidate_auto_promote": False,
                "verified_requires_legal_basis": True,
                "verified_requires_document_sha256": True,
                "verified_requires_two_person_review": True,
                "verifier_must_differ_from_approver": True,
                "dispatch_authorization_requires_verified_legal_basis": True,
                "dispatch_authorization_is_role_based_not_person_name": True,
                "invalid_input_behavior": "fail_closed_empty_verified_output",
            },
            "prohibited_index_fields": [
                "reporter_name",
                "reporter_phone",
                "reporter_email",
                "citizen_id",
                "home_address",
                "device_identifier",
                "raw_complaint_text",
                "official_signatory_name",
                "official_signature_image",
            ],
            "runtime_requirements": [
                "Server-side spatial lookup; do not trust client-selected agency.",
                "RBAC for create, review, approve, override, and dispatch.",
                "Immutable audit log for import, approval, override, and query.",
                "Rate limits, request size limits, TLS, and secret management.",
                "Human approval before dispatch from an unverified candidate.",
            ],
            "ingestion_requirements": [
                "HTTPS source allowlist and redirect validation.",
                "Timeout, size, MIME, schema, coordinate, and geometry checks.",
                "Quarantine invalid or conflicting source records.",
                "Record requested URL, final URL, fetched time, and SHA-256.",
            ],
        },
    )


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def pdf_page_count(path: Path) -> int:
    return len(
        re.findall(
            rb"/Type\s*/Page(?!s)\b",
            path.read_bytes(),
        )
    )


def build_legal_authority_evidence(
    districts: DistrictIndex,
    agencies: AgencyRegistry,
) -> dict[str, Any]:
    input_path = LEGAL_AUTHORITY_DIR / "source_material.json"
    material = read_json(input_path)
    errors: list[str] = []
    raw_root = (LEGAL_AUTHORITY_DIR / "raw").resolve()
    source_rows: list[dict[str, Any]] = []
    sources_by_id: dict[str, dict[str, Any]] = {}
    required_source_fields = {
        "source_id",
        "title_th",
        "document_type",
        "issuing_authority",
        "official_landing_url",
        "source_url",
        "local_path",
        "expected_sha256",
        "expected_page_count",
        "source_copy_status",
        "currency_status",
        "contains_personal_data",
    }
    for index, source in enumerate(material.get("sources", []), start=1):
        missing = sorted(
            field
            for field in required_source_fields
            if source.get(field) in {None, ""}
        )
        if missing:
            errors.append(
                f"source_material.sources[{index}]: missing "
                + ", ".join(missing)
            )
            continue
        source_id = source["source_id"]
        if source_id in sources_by_id:
            errors.append(f"duplicate legal source_id: {source_id}")
            continue
        for url_field in ("official_landing_url", "source_url"):
            parsed = urlparse(source[url_field])
            if (
                parsed.scheme != "https"
                or not is_allowed_legal_source_host(parsed.hostname or "")
            ):
                errors.append(
                    f"{source_id}: {url_field} is not an allowlisted HTTPS URL"
                )
        expected_hash = source["expected_sha256"]
        if not re.fullmatch(r"[0-9a-f]{64}", expected_hash):
            errors.append(f"{source_id}: invalid expected_sha256")
        relative_path = Path(source["local_path"])
        local_path = (ROOT / relative_path).resolve()
        if raw_root not in local_path.parents:
            errors.append(f"{source_id}: local_path escapes legal raw directory")
            continue
        if not local_path.exists() or not local_path.is_file():
            errors.append(f"{source_id}: local PDF is missing")
            continue
        if local_path.is_symlink():
            errors.append(f"{source_id}: symbolic links are not accepted")
            continue
        size_bytes = local_path.stat().st_size
        if size_bytes > 10 * 1024 * 1024:
            errors.append(f"{source_id}: PDF exceeds 10 MiB limit")
        with local_path.open("rb") as stream:
            if stream.read(5) != b"%PDF-":
                errors.append(f"{source_id}: file is not a PDF")
        actual_hash = file_sha256(local_path)
        if actual_hash != expected_hash:
            errors.append(f"{source_id}: PDF SHA-256 mismatch")
        actual_page_count = pdf_page_count(local_path)
        if actual_page_count != source["expected_page_count"]:
            errors.append(f"{source_id}: PDF page count mismatch")
        if source["currency_status"] != "requires_legal_review":
            errors.append(
                f"{source_id}: currency_status must require legal review"
            )
        if source["contains_personal_data"] is not False:
            errors.append(f"{source_id}: personal data is prohibited")
        row = {
            **source,
            "actual_sha256": actual_hash,
            "actual_page_count": actual_page_count,
            "local_file_size_bytes": size_bytes,
            "verification_status": "pending_legal_review",
            "is_official_legal_assignment": False,
            "may_auto_dispatch": False,
        }
        row["legal_source_hash_sha256"] = stable_hash(
            SCHEMA_VERSION,
            "legal_authority_source",
            source_id,
            source["source_url"],
            actual_hash,
            actual_page_count,
            source["currency_status"],
        )
        source_rows.append(row)
        sources_by_id[source_id] = row
    if errors:
        raise RuntimeError(
            "Legal authority source validation failed:\n"
            + "\n".join(errors)
        )

    roles = material.get("roles", [])
    roles_by_code: dict[str, dict[str, Any]] = {}
    for index, role in enumerate(roles, start=1):
        role_code = clean_text(role.get("actor_role_code"))
        if not role_code:
            errors.append(f"roles[{index}]: missing actor_role_code")
            continue
        if role_code in roles_by_code:
            errors.append(f"duplicate actor_role_code: {role_code}")
            continue
        agency_id = role.get("agency_id")
        if agency_id is not None and agency_id not in agencies.rows:
            errors.append(f"{role_code}: unknown agency_id {agency_id}")
        roles_by_code[role_code] = role
    if errors:
        raise RuntimeError(
            "Legal authority role validation failed:\n"
            + "\n".join(errors)
        )

    provision_rows: list[dict[str, Any]] = []
    provisions_by_id: dict[str, dict[str, Any]] = {}
    required_provision_fields = {
        "provision_id",
        "source_id",
        "section",
        "source_pdf_page",
        "actor_role_code",
        "authority_type",
        "authority_scope",
        "action_codes",
        "evidence_excerpt_th",
        "legal_effect_candidate",
        "requires_action_specific_order",
        "review_questions",
    }
    for index, provision in enumerate(
        material.get("provisions", []),
        start=1,
    ):
        missing = sorted(
            field
            for field in required_provision_fields
            if provision.get(field) is None
            or provision.get(field) == ""
            or provision.get(field) == []
        )
        if missing:
            errors.append(
                f"provisions[{index}]: missing " + ", ".join(missing)
            )
            continue
        provision_id = provision["provision_id"]
        if provision_id in provisions_by_id:
            errors.append(f"duplicate provision_id: {provision_id}")
            continue
        source = sources_by_id.get(provision["source_id"])
        if not source:
            errors.append(
                f"{provision_id}: unknown source_id "
                f"{provision['source_id']}"
            )
            continue
        if provision["actor_role_code"] not in roles_by_code:
            errors.append(
                f"{provision_id}: unknown actor_role_code "
                f"{provision['actor_role_code']}"
            )
        page = provision["source_pdf_page"]
        if not isinstance(page, int) or not 1 <= page <= source[
            "actual_page_count"
        ]:
            errors.append(f"{provision_id}: source_pdf_page out of range")
        actions = provision["action_codes"]
        if (
            not isinstance(actions, list)
            or not actions
            or any(action not in LEGAL_AUTHORITY_ACTIONS for action in actions)
        ):
            errors.append(f"{provision_id}: invalid action_codes")
        if provision["requires_action_specific_order"] is not True:
            errors.append(
                f"{provision_id}: action-specific order guardrail is required"
            )
        row = {
            **provision,
            "source_document_sha256": source["actual_sha256"],
            "source_url": source["source_url"],
            "verification_status": "pending_legal_review",
            "is_official_legal_assignment": False,
            "is_official_dispatch_authorization": False,
            "requires_human_approval": True,
            "may_auto_dispatch": False,
            "contains_personal_data": False,
        }
        row["authority_hash_sha256"] = stable_hash(
            SCHEMA_VERSION,
            "legal_authority_provision",
            provision_id,
            source["actual_sha256"],
            provision["section"],
            page,
            provision["actor_role_code"],
            provision["authority_type"],
            provision["authority_scope"],
            canonical_json(sorted(actions)),
            provision["evidence_excerpt_th"],
        )
        provision_rows.append(row)
        provisions_by_id[provision_id] = row
    if errors:
        raise RuntimeError(
            "Legal authority provision validation failed:\n"
            + "\n".join(errors)
        )
    provision_rows.sort(key=lambda row: row["provision_id"])

    role_rows: list[dict[str, Any]] = []
    for role in roles:
        provision_hashes = sorted(
            row["authority_hash_sha256"]
            for row in provision_rows
            if row["actor_role_code"] == role["actor_role_code"]
        )
        action_codes = sorted(
            {
                action
                for row in provision_rows
                if row["actor_role_code"] == role["actor_role_code"]
                for action in row["action_codes"]
            }
        )
        row = {
            **role,
            "authority_provision_hashes_sha256": provision_hashes,
            "action_codes": action_codes,
            "verification_status": "pending_legal_review",
            "requires_human_approval": True,
            "may_auto_dispatch": False,
        }
        row["authority_role_hash_sha256"] = stable_hash(
            SCHEMA_VERSION,
            "legal_authority_role",
            role["actor_role_code"],
            role.get("agency_id"),
            canonical_json(provision_hashes),
            canonical_json(action_codes),
        )
        role_rows.append(row)
    role_rows.sort(key=lambda row: row["actor_role_code"])

    district_basis_ids = (
        "dpa2550-s36-p1",
        "dpa2550-s36-p2",
        "dpa2550-s37",
        "bma2528-s68",
        "bma2528-s69",
    )
    district_basis_hashes = [
        provisions_by_id[provision_id]["authority_hash_sha256"]
        for provision_id in district_basis_ids
    ]
    district_rows: list[dict[str, Any]] = []
    for district in sorted(
        districts.features,
        key=lambda item: item["district_code"],
    ):
        agency_id = agencies.district_agency(district)
        row = {
            "district_code": district["district_code"],
            "district_name_th": district["district_name_th"],
            "district_agency_id": agency_id,
            "actor_role_code": (
                "bma_district_director_assistant_disaster_director"
            ),
            "authority_scope": "district_polygon",
            "authority_provision_ids": list(district_basis_ids),
            "authority_provision_hashes_sha256": district_basis_hashes,
            "current_district_order_status": "not_supplied",
            "district_specific_legal_review_status": "not_reviewed",
            "verification_status": "pending_legal_review",
            "is_official_legal_assignment": False,
            "is_official_dispatch_authorization": False,
            "requires_current_district_order": True,
            "requires_human_approval": True,
            "may_auto_dispatch": False,
            "contains_personal_data": False,
        }
        row["district_authority_hash_sha256"] = stable_hash(
            SCHEMA_VERSION,
            "district_legal_authority_candidate",
            district["district_code"],
            agency_id,
            canonical_json(district_basis_hashes),
            row["current_district_order_status"],
        )
        district_rows.append(row)

    review_rows: list[dict[str, Any]] = []
    for source in source_rows:
        row = {
            "review_type": "gazette_currency_and_amendment_check",
            "source_id": source["source_id"],
            "provision_id": None,
            "review_question": (
                "Cross-check the Gazette original, amendments, repeals, "
                "effective date, and current legal text."
            ),
            "review_status": "open",
            "required_reviewer_role": "legal_reviewer",
            "is_placeholder": False,
        }
        row["legal_review_hash_sha256"] = stable_hash(
            SCHEMA_VERSION,
            "legal_authority_review",
            row["review_type"],
            row["source_id"],
            row["review_question"],
        )
        review_rows.append(row)
    for provision in provision_rows:
        row = {
            "review_type": "legal_effect_and_action_scope_review",
            "source_id": provision["source_id"],
            "provision_id": provision["provision_id"],
            "review_question": (
                "Confirm actor, conditions, territorial scope, delegation "
                "chain, and whether an action-specific order is required."
            ),
            "review_status": "open",
            "required_reviewer_role": "legal_reviewer",
            "is_placeholder": False,
        }
        row["legal_review_hash_sha256"] = stable_hash(
            SCHEMA_VERSION,
            "legal_authority_review",
            row["review_type"],
            row["source_id"],
            row["provision_id"],
            row["review_question"],
        )
        review_rows.append(row)
    review_rows.sort(
        key=lambda row: (
            row["source_id"],
            row.get("provision_id") or "",
            row["review_type"],
        )
    )

    guardrails = {
        "metadata": {
            "schema_version": SCHEMA_VERSION,
            "generated_at": utc_now(),
            "scope": "Legal-authority decision support",
        },
        "allowed_before_legal_approval": [
            "display_candidate_authority",
            "prepare_review_packet",
            "propose_human_routing",
            "record_source_provenance",
        ],
        "prohibited_without_verified_action_specific_authorization": [
            "auto_dispatch",
            "close_road",
            "enter_private_property",
            "evacuate_people",
            "operate_drainage_asset",
            "override_incident_command",
            "spend_emergency_funds",
        ],
        "rules": {
            "candidate_never_implies_legal_liability": True,
            "statutory_role_never_implies_application_permission": True,
            "district_match_never_proves_asset_ownership": True,
            "person_name_not_required_for_role_authority": True,
            "verified_layer_requires_two_person_approval": True,
            "automatic_promotion_to_verified": False,
        },
    }
    guardrails["guardrail_hash_sha256"] = stable_hash(
        SCHEMA_VERSION,
        "legal_authority_guardrails",
        canonical_json(guardrails["allowed_before_legal_approval"]),
        canonical_json(
            guardrails[
                "prohibited_without_verified_action_specific_authorization"
            ]
        ),
        canonical_json(guardrails["rules"]),
    )

    checks = {
        "source_material_schema_matches": (
            material.get("metadata", {}).get("schema_version")
            == SCHEMA_VERSION
        ),
        "source_count_is_2": len(source_rows) == 2,
        "all_source_hashes_match": all(
            row["actual_sha256"] == row["expected_sha256"]
            for row in source_rows
        ),
        "all_sources_are_allowlisted_https": all(
            is_allowed_legal_source_host(
                urlparse(row["source_url"]).hostname or ""
            )
            and row["source_url"].startswith("https://")
            for row in source_rows
        ),
        "all_source_pages_match": all(
            row["actual_page_count"] == row["expected_page_count"]
            for row in source_rows
        ),
        "provision_hashes_unique": len(provision_rows)
        == len(
            {
                row["authority_hash_sha256"]
                for row in provision_rows
            }
        ),
        "all_provisions_pending_legal_review": all(
            row["verification_status"] == "pending_legal_review"
            and row["is_official_legal_assignment"] is False
            and row["is_official_dispatch_authorization"] is False
            and row["may_auto_dispatch"] is False
            for row in provision_rows
        ),
        "district_candidates_cover_50_districts": len(district_rows) == 50
        and len({row["district_code"] for row in district_rows}) == 50,
        "all_district_candidates_require_current_order": all(
            row["requires_current_district_order"] is True
            and row["current_district_order_status"] == "not_supplied"
            and row["may_auto_dispatch"] is False
            for row in district_rows
        ),
        "review_queue_has_no_placeholders": all(
            row["is_placeholder"] is False for row in review_rows
        ),
        "no_personal_data": all(
            row["contains_personal_data"] is False for row in source_rows
        )
        and all(
            row["contains_personal_data"] is False
            for row in provision_rows + district_rows
        ),
    }
    quality = {
        "metadata": {
            "schema_version": SCHEMA_VERSION,
            "generated_at": utc_now(),
            "scope": "Bangkok flood legal-authority evidence",
            "status": "public_statutory_evidence_pending_legal_review",
            "operational_use": False,
        },
        "counts": {
            "sources": len(source_rows),
            "roles": len(role_rows),
            "authority_provisions": len(provision_rows),
            "district_authority_candidates": len(district_rows),
            "legal_review_queue": len(review_rows),
            "verified_legal_assignments": 0,
            "verified_dispatch_authorizations": 0,
        },
        "checks": checks,
        "validation_errors": [],
        "passed": all(checks.values()),
        "notice": (
            "This layer supports legal review and human routing only. "
            "It does not grant application permissions or automatic dispatch."
        ),
    }
    write_json(
        LEGAL_AUTHORITY_DIR / "source_registry.json",
        {
            "metadata": {
                "schema_version": SCHEMA_VERSION,
                "generated_at": utc_now(),
                "source_count": len(source_rows),
            },
            "sources": source_rows,
        },
    )
    write_jsonl(
        LEGAL_AUTHORITY_DIR / "authority_provisions_hash_index.jsonl",
        provision_rows,
    )
    write_json(
        LEGAL_AUTHORITY_DIR / "authority_by_role.json",
        {
            "metadata": {
                "schema_version": SCHEMA_VERSION,
                "generated_at": utc_now(),
                "role_count": len(role_rows),
            },
            "roles": role_rows,
        },
    )
    write_jsonl(
        LEGAL_AUTHORITY_DIR / "district_authority_candidates.jsonl",
        district_rows,
    )
    write_jsonl(
        LEGAL_AUTHORITY_DIR / "legal_review_queue.jsonl",
        review_rows,
    )
    write_json(
        LEGAL_AUTHORITY_DIR / "dispatch_guardrails.json",
        guardrails,
    )
    write_json(LEGAL_AUTHORITY_DIR / "quality_report.json", quality)
    if not quality["passed"]:
        raise RuntimeError("Legal authority evidence validation failed")
    return {
        "sources": source_rows,
        "roles": role_rows,
        "provisions": provision_rows,
        "district_candidates": district_rows,
        "review_queue": review_rows,
        "guardrails": guardrails,
        "quality": quality,
    }


def write_integrity_manifest() -> None:
    excluded = {
        SECURITY_DIR / "integrity_manifest.json",
        SECURITY_DIR / "checksums.sha256",
    }
    entries = []
    for path in sorted(OUTPUT_DIR.rglob("*")):
        if not path.is_file() or path in excluded or path.name == ".DS_Store":
            continue
        relative = path.relative_to(OUTPUT_DIR)
        entries.append(
            {
                "path": relative.as_posix(),
                "size_bytes": path.stat().st_size,
                "sha256": file_sha256(path),
            }
        )
    write_json(
        SECURITY_DIR / "integrity_manifest.json",
        {
            "metadata": {
                "schema_version": SCHEMA_VERSION,
                "generated_at": utc_now(),
                "artifact_count": len(entries),
                "signature_status": "unsigned",
                "notice": (
                    "Checksums detect accidental or post-build changes but "
                    "do not authenticate the publisher. Sign this manifest "
                    "with a managed key before production use."
                ),
            },
            "artifacts": entries,
        },
    )
    (SECURITY_DIR / "checksums.sha256").write_text(
        "".join(
            f"{entry['sha256']}  {entry['path']}\n"
            for entry in entries
        ),
        encoding="utf-8",
    )


def remove_legacy_outputs() -> None:
    for name in LEGACY_OUTPUTS:
        (OUTPUT_DIR / name).unlink(missing_ok=True)


def write_input_templates() -> None:
    ensure_csv_template(INPUT_DIR / "legal_basis.csv", LEGAL_BASIS_FIELDS)
    ensure_csv_template(
        INPUT_DIR / "verified_responsibility_assignments.csv",
        VERIFIED_ASSIGNMENT_FIELDS,
    )
    ensure_csv_template(
        INPUT_DIR / "verified_dispatch_authorizations.csv",
        DISPATCH_AUTHORIZATION_FIELDS,
    )
    ensure_csv_template(
        INPUT_DIR / "asset_owner_evidence.csv",
        (
            "asset_type",
            "asset_id",
            "agency_id",
            "source_document",
            "section_or_page",
            "source_url",
            "document_sha256",
            "verified_by",
            "verified_at",
            "approved_by",
            "approved_at",
        ),
    )
    ensure_csv_template(
        INPUT_DIR / "incident_responsibility_matrix.csv",
        (
            "incident_type_code",
            "severity_code",
            "responsibility_role",
            "agency_id",
            "legal_basis_id",
            "effective_from",
            "effective_to",
            "verified_by",
            "verified_at",
            "approved_by",
            "approved_at",
            "change_reason",
        ),
    )


def write_schemas() -> None:
    common_hash = {
        "type": "string",
        "pattern": "^[0-9a-f]{64}$",
    }
    write_json(
        SCHEMA_DIR / "candidate_assignment.schema.json",
        {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "title": "Candidate flood responsibility assignment",
            "type": "object",
            "required": [
                "responsibility_hash_sha256",
                "entity_type",
                "entity_id",
                "spatial_hash_geohash7",
                "agency_id",
                "responsibility_role",
                "verification_status",
                "is_official_legal_assignment",
                "requires_human_approval",
            ],
            "properties": {
                "responsibility_hash_sha256": common_hash,
                "verification_status": {"const": "candidate_unverified"},
                "is_official_legal_assignment": {"const": False},
                "requires_human_approval": {"const": True},
            },
        },
    )
    write_json(
        SCHEMA_DIR / "legal_basis.schema.json",
        {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "title": "Verified legal basis input",
            "type": "object",
            "required": list(LEGAL_BASIS_FIELDS),
            "properties": {
                "legal_basis_id": {"type": "string", "minLength": 1},
                "section_or_page": {"type": "string", "minLength": 1},
                "source_url": {"type": "string", "pattern": "^https://"},
                "document_sha256": common_hash,
                "verification_status": {"const": "verified"},
                "verified_by": {"type": "string", "minLength": 1},
                "verified_at": {"type": "string", "minLength": 1},
                "approved_by": {"type": "string", "minLength": 1},
                "approved_at": {"type": "string", "minLength": 1},
            },
        },
    )
    write_json(
        SCHEMA_DIR / "verified_assignment.schema.json",
        {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "title": "Verified flood responsibility assignment",
            "type": "object",
            "required": [
                "responsibility_hash_sha256",
                *VERIFIED_ASSIGNMENT_FIELDS,
                "verification_status",
                "is_official_legal_assignment",
            ],
            "properties": {
                "responsibility_hash_sha256": common_hash,
                "spatial_hash": {
                    "type": "string",
                    "pattern": f"^[{GEOHASH_BASE32}]{{6,7}}$",
                },
                "spatial_hash_precision": {"enum": [6, 7]},
                "verification_status": {"const": "verified"},
                "is_official_legal_assignment": {"const": True},
            },
        },
    )
    write_json(
        SCHEMA_DIR / "service_area_candidate.schema.json",
        {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "title": "Official-page service-area candidate",
            "type": "object",
            "required": [
                "service_area_hash_sha256",
                "district_code",
                "agency_id",
                "service_area_role",
                "source_url",
                "source_locator",
                "verification_status",
                "is_official_legal_assignment",
            ],
            "properties": {
                "service_area_hash_sha256": common_hash,
                "source_url": {"type": "string", "pattern": "^https://"},
                "verification_status": {
                    "const": "official_reference_unverified"
                },
                "is_official_legal_assignment": {"const": False},
            },
        },
    )
    write_json(
        SCHEMA_DIR / "review_record.schema.json",
        {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "title": "Responsibility data review record",
            "type": "object",
            "required": [
                "review_hash_sha256",
                "review_type",
                "entity_id",
                "source_path",
                "review_status",
                "requires_manual_review",
            ],
            "properties": {
                "review_hash_sha256": common_hash,
                "review_status": {"const": "unresolved"},
                "requires_manual_review": {"const": True},
                "is_placeholder": {"const": False},
            },
        },
    )
    write_json(
        SCHEMA_DIR / "agency_incident_capability.schema.json",
        {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "title": "Agency incident capability candidate",
            "type": "object",
            "required": [
                "capability_hash_sha256",
                "district_code",
                "incident_type_code",
                "agency_id",
                "legal_basis_reference_id",
                "verification_status",
            ],
            "properties": {
                "capability_hash_sha256": common_hash,
                "verification_status": {
                    "const": "official_reference_unverified"
                },
                "is_official_legal_assignment": {"const": False},
            },
        },
    )
    write_json(
        SCHEMA_DIR
        / "district_agency_responsibility_summary.schema.json",
        {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "title": "District and agency responsibility summary",
            "type": "object",
            "required": [
                "district_agency_responsibility_hash_sha256",
                "district_code",
                "agency_id",
                "responsibility_scope",
                "responsibility_role",
                "source_record_count",
                "source_hashes_sha256",
                "verification_status",
                "is_official_legal_assignment",
                "requires_human_approval",
            ],
            "properties": {
                "district_agency_responsibility_hash_sha256": (
                    common_hash
                ),
                "source_hashes_sha256": {
                    "type": "array",
                    "items": common_hash,
                    "minItems": 1,
                    "uniqueItems": True,
                },
                "is_official_legal_assignment": {"const": False},
                "requires_human_approval": {"const": True},
            },
        },
    )
    write_json(
        SCHEMA_DIR / "legal_reference.schema.json",
        {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "title": "Legal and operational reference identity",
            "type": "object",
            "required": [
                "legal_reference_hash_sha256",
                "legal_basis_id",
                "url",
                "source_class",
                "verification_status",
            ],
            "properties": {
                "legal_reference_hash_sha256": common_hash,
                "url": {"type": "string", "pattern": "^https://"},
                "is_document_content_hash": {"const": False},
            },
        },
    )
    write_json(
        SCHEMA_DIR / "dispatch_authorization.schema.json",
        {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "title": "Verified dispatch authorization",
            "type": "object",
            "required": [
                "authorization_hash_sha256",
                *DISPATCH_AUTHORIZATION_FIELDS,
                "verification_status",
                "is_official_authorization",
            ],
            "properties": {
                "authorization_hash_sha256": common_hash,
                "permitted_action": {
                    "enum": sorted(PERMITTED_DISPATCH_ACTIONS)
                },
                "verification_status": {"const": "verified"},
                "is_official_authorization": {"const": True},
            },
        },
    )
    write_json(
        SCHEMA_DIR / "official_document_evidence.schema.json",
        {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "title": "Official document evidence registry record",
            "type": "object",
            "required": [
                "document_evidence_hash_sha256",
                "document_id",
                "source_url",
                "source_access_status",
                "verification_status",
                "is_official_legal_assignment",
            ],
            "properties": {
                "document_evidence_hash_sha256": common_hash,
                "document_sha256": {
                    "oneOf": [common_hash, {"type": "null"}]
                },
                "source_url": {"type": "string", "pattern": "^https://"},
                "verification_status": {
                    "const": "pending_legal_review"
                },
                "is_official_legal_assignment": {"const": False},
            },
        },
    )
    write_json(
        SCHEMA_DIR / "mission_duty_evidence.schema.json",
        {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "title": "Agency mission duty extracted from official document",
            "type": "object",
            "required": [
                "mission_duty_hash_sha256",
                "mission_duty_id",
                "source_document_id",
                "source_pdf_pages",
                "mission_items_th",
                "verification_status",
            ],
            "properties": {
                "mission_duty_hash_sha256": common_hash,
                "verification_status": {
                    "const": "pending_legal_review"
                },
                "is_official_legal_assignment": {"const": False},
                "contains_personal_data": {"const": False},
            },
        },
    )
    write_json(
        SCHEMA_DIR / "sop_process_evidence.schema.json",
        {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "title": "SOP process extracted from official document",
            "type": "object",
            "required": [
                "sop_process_hash_sha256",
                "sop_process_id",
                "source_document_id",
                "source_pdf_pages",
                "steps",
                "verification_status",
            ],
            "properties": {
                "sop_process_hash_sha256": common_hash,
                "verification_status": {
                    "const": "pending_legal_review"
                },
                "is_official_legal_assignment": {"const": False},
                "contains_personal_data": {"const": False},
            },
        },
    )
    write_json(
        SCHEMA_DIR / "district_office_flood_process.schema.json",
        {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "title": "District office common flood process candidate",
            "type": "object",
            "required": [
                "district_process_hash_sha256",
                "district_code",
                "district_agency_id",
                "process_stages",
                "source_hashes_sha256",
                "verification_status",
                "requires_district_confirmation",
            ],
            "properties": {
                "district_process_hash_sha256": common_hash,
                "source_hashes_sha256": {
                    "type": "array",
                    "items": common_hash,
                    "minItems": 3,
                    "uniqueItems": True,
                },
                "verification_status": {
                    "const": "pending_district_confirmation"
                },
                "district_specific_order_available": {"const": False},
                "district_specific_sop_verified": {"const": False},
                "requires_district_confirmation": {"const": True},
                "is_official_legal_assignment": {"const": False},
            },
        },
    )
    write_json(
        SCHEMA_DIR / "data_source_registry.schema.json",
        {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "title": "Hash-index data source lineage record",
            "type": "object",
            "required": [
                "data_source_hash_sha256",
                "source_id",
                "source_kind",
                "source_url",
                "provenance_status",
                "used_by_hash_datasets",
            ],
            "properties": {
                "data_source_hash_sha256": common_hash,
                "source_url": {"type": "string", "pattern": "^https://"},
                "local_file_sha256": {
                    "oneOf": [common_hash, {"type": "null"}]
                },
                "used_by_hash_datasets": {
                    "type": "array",
                    "items": {"type": "string", "minLength": 1},
                    "minItems": 1,
                },
            },
        },
    )
    write_json(
        SCHEMA_DIR / "legal_authority_source.schema.json",
        {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "title": "Legal authority source evidence",
            "type": "object",
            "required": [
                "legal_source_hash_sha256",
                "source_id",
                "source_url",
                "local_path",
                "actual_sha256",
                "actual_page_count",
                "currency_status",
                "verification_status",
                "may_auto_dispatch",
            ],
            "properties": {
                "legal_source_hash_sha256": common_hash,
                "actual_sha256": common_hash,
                "source_url": {"type": "string", "pattern": "^https://"},
                "currency_status": {"const": "requires_legal_review"},
                "verification_status": {
                    "const": "pending_legal_review"
                },
                "is_official_legal_assignment": {"const": False},
                "may_auto_dispatch": {"const": False},
                "contains_personal_data": {"const": False},
            },
        },
    )
    write_json(
        SCHEMA_DIR / "legal_authority_provision.schema.json",
        {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "title": "Curated statutory authority provision",
            "type": "object",
            "required": [
                "authority_hash_sha256",
                "provision_id",
                "source_id",
                "source_document_sha256",
                "section",
                "source_pdf_page",
                "actor_role_code",
                "authority_type",
                "authority_scope",
                "action_codes",
                "verification_status",
                "requires_action_specific_order",
                "may_auto_dispatch",
            ],
            "properties": {
                "authority_hash_sha256": common_hash,
                "source_document_sha256": common_hash,
                "source_url": {"type": "string", "pattern": "^https://"},
                "action_codes": {
                    "type": "array",
                    "items": {
                        "enum": sorted(LEGAL_AUTHORITY_ACTIONS)
                    },
                    "minItems": 1,
                    "uniqueItems": True,
                },
                "verification_status": {
                    "const": "pending_legal_review"
                },
                "is_official_legal_assignment": {"const": False},
                "is_official_dispatch_authorization": {"const": False},
                "requires_action_specific_order": {"const": True},
                "requires_human_approval": {"const": True},
                "may_auto_dispatch": {"const": False},
                "contains_personal_data": {"const": False},
            },
        },
    )
    write_json(
        SCHEMA_DIR / "district_authority_candidate.schema.json",
        {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "title": "District statutory authority candidate",
            "type": "object",
            "required": [
                "district_authority_hash_sha256",
                "district_code",
                "district_agency_id",
                "actor_role_code",
                "authority_provision_hashes_sha256",
                "current_district_order_status",
                "verification_status",
                "requires_current_district_order",
                "may_auto_dispatch",
            ],
            "properties": {
                "district_authority_hash_sha256": common_hash,
                "authority_provision_hashes_sha256": {
                    "type": "array",
                    "items": common_hash,
                    "minItems": 1,
                    "uniqueItems": True,
                },
                "current_district_order_status": {
                    "const": "not_supplied"
                },
                "verification_status": {
                    "const": "pending_legal_review"
                },
                "is_official_legal_assignment": {"const": False},
                "is_official_dispatch_authorization": {"const": False},
                "requires_current_district_order": {"const": True},
                "requires_human_approval": {"const": True},
                "may_auto_dispatch": {"const": False},
                "contains_personal_data": {"const": False},
            },
        },
    )
    write_json(
        SCHEMA_DIR / "legal_authority_review.schema.json",
        {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "title": "Legal authority review task",
            "type": "object",
            "required": [
                "legal_review_hash_sha256",
                "review_type",
                "source_id",
                "review_question",
                "review_status",
                "required_reviewer_role",
                "is_placeholder",
            ],
            "properties": {
                "legal_review_hash_sha256": common_hash,
                "review_status": {"const": "open"},
                "required_reviewer_role": {"const": "legal_reviewer"},
                "is_placeholder": {"const": False},
            },
        },
    )


def build_verified_index(
    agency_ids: set[str],
    district_codes: set[str] | None = None,
) -> dict[str, Any]:
    legal_rows = read_csv(INPUT_DIR / "legal_basis.csv")
    assignment_rows = read_csv(
        INPUT_DIR / "verified_responsibility_assignments.csv"
    )
    authorization_rows = read_csv(
        INPUT_DIR / "verified_dispatch_authorizations.csv"
    )
    valid_incident_types = {
        row["incident_type_code"]
        for row in build_incident_type_registry()["incident_types"]
    }
    errors: list[str] = []
    legal_by_id: dict[str, dict[str, str]] = {}
    sha256_pattern = re.compile(r"^[0-9a-fA-F]{64}$")

    for row_number, row in enumerate(legal_rows, start=2):
        row_errors: list[str] = []
        missing = [
            field
            for field in (
                "legal_basis_id",
                "document_title",
                "issuing_authority",
                "document_type",
                "section_or_page",
                "effective_from",
                "source_url",
                "document_sha256",
                "verification_status",
                "verified_by",
                "verified_at",
                "approved_by",
                "approved_at",
            )
            if not row.get(field)
        ]
        if missing:
            row_errors.append(
                f"legal_basis.csv:{row_number}: missing {', '.join(missing)}"
            )
        if row.get("verification_status") != "verified":
            row_errors.append(
                f"legal_basis.csv:{row_number}: verification_status must be verified"
            )
        if not row.get("source_url", "").startswith("https://"):
            row_errors.append(
                f"legal_basis.csv:{row_number}: source_url must use HTTPS"
            )
        source_host = (
            urlparse(row.get("source_url", "")).hostname or ""
        ).lower()
        if not is_allowed_legal_source_host(source_host):
            row_errors.append(
                f"legal_basis.csv:{row_number}: source host is not allowlisted"
            )
        if not sha256_pattern.fullmatch(row.get("document_sha256", "")):
            row_errors.append(
                f"legal_basis.csv:{row_number}: invalid document_sha256"
            )
        legal_basis_id = row.get("legal_basis_id", "")
        if legal_basis_id in legal_by_id:
            row_errors.append(
                f"legal_basis.csv:{row_number}: duplicate legal_basis_id"
            )
        if row.get("verified_by", "").casefold() == row.get(
            "approved_by", ""
        ).casefold():
            row_errors.append(
                f"legal_basis.csv:{row_number}: verifier and approver must differ"
            )
        errors.extend(row_errors)
        if not row_errors:
            legal_by_id[legal_basis_id] = row

    verified: list[dict[str, Any]] = []
    for row_number, row in enumerate(assignment_rows, start=2):
        row_errors = []
        missing = [
            field
            for field in (
                "assignment_source_id",
                "entity_type",
                "agency_id",
                "responsibility_role",
                "legal_basis_id",
                "effective_from",
                "evidence_text",
                "verified_by",
                "verified_at",
                "approved_by",
                "approved_at",
                "change_reason",
            )
            if not row.get(field)
        ]
        if missing:
            row_errors.append(
                "verified_responsibility_assignments.csv:"
                f"{row_number}: missing {', '.join(missing)}"
            )
        if row.get("agency_id") not in agency_ids:
            row_errors.append(
                "verified_responsibility_assignments.csv:"
                f"{row_number}: unknown agency_id {row.get('agency_id', '')}"
            )
        if row.get("legal_basis_id") not in legal_by_id:
            row_errors.append(
                "verified_responsibility_assignments.csv:"
                f"{row_number}: legal_basis_id is not verified"
            )
        spatial_hash = row.get("spatial_hash", "").lower()
        precision_raw = row.get("spatial_hash_precision", "")
        try:
            precision = int(precision_raw)
        except ValueError:
            precision = 0
        if spatial_hash:
            if (
                precision not in {6, 7}
                or len(spatial_hash) != precision
                or any(character not in GEOHASH_BASE32 for character in spatial_hash)
            ):
                row_errors.append(
                    "verified_responsibility_assignments.csv:"
                    f"{row_number}: invalid spatial_hash or precision"
                )
        elif precision_raw:
            row_errors.append(
                "verified_responsibility_assignments.csv:"
                f"{row_number}: precision supplied without spatial_hash"
            )
        if row.get("verified_by", "").casefold() == row.get(
            "approved_by", ""
        ).casefold():
            row_errors.append(
                "verified_responsibility_assignments.csv:"
                f"{row_number}: verifier and approver must differ"
            )
        errors.extend(row_errors)
        if row_errors:
            continue
        digest = stable_hash(
            SCHEMA_VERSION,
            row["assignment_source_id"],
            row["entity_type"],
            row.get("entity_id"),
            spatial_hash,
            row["agency_id"],
            row["responsibility_role"],
            row["legal_basis_id"],
            row.get("effective_from"),
        )
        verified.append(
            {
                "responsibility_hash_sha256": digest,
                **row,
                "spatial_hash": spatial_hash,
                "spatial_hash_precision": precision or None,
                "verification_status": "verified",
                "is_official_legal_assignment": True,
                "requires_human_approval": False,
            }
        )

    duplicate_hashes = [
        value
        for value, count in Counter(
            row["responsibility_hash_sha256"] for row in verified
        ).items()
        if count > 1
    ]
    if duplicate_hashes:
        errors.append("verified assignments contain duplicate hashes")

    verified_authorizations: list[dict[str, Any]] = []
    for row_number, row in enumerate(authorization_rows, start=2):
        row_errors = []
        missing = [
            field
            for field in DISPATCH_AUTHORIZATION_FIELDS
            if field != "effective_to" and not row.get(field)
        ]
        if missing:
            row_errors.append(
                "verified_dispatch_authorizations.csv:"
                f"{row_number}: missing {', '.join(missing)}"
            )
        for agency_field in ("actor_agency_id", "target_agency_id"):
            if row.get(agency_field) not in agency_ids:
                row_errors.append(
                    "verified_dispatch_authorizations.csv:"
                    f"{row_number}: unknown {agency_field} "
                    f"{row.get(agency_field, '')}"
                )
        if (
            row.get("permitted_action")
            not in PERMITTED_DISPATCH_ACTIONS
        ):
            row_errors.append(
                "verified_dispatch_authorizations.csv:"
                f"{row_number}: invalid permitted_action"
            )
        if district_codes is not None and row.get(
            "district_code"
        ) not in district_codes:
            row_errors.append(
                "verified_dispatch_authorizations.csv:"
                f"{row_number}: unknown district_code"
            )
        if row.get("incident_type_code") not in valid_incident_types:
            row_errors.append(
                "verified_dispatch_authorizations.csv:"
                f"{row_number}: unknown incident_type_code"
            )
        if row.get("legal_basis_id") not in legal_by_id:
            row_errors.append(
                "verified_dispatch_authorizations.csv:"
                f"{row_number}: legal_basis_id is not verified"
            )
        if row.get("verified_by", "").casefold() == row.get(
            "approved_by", ""
        ).casefold():
            row_errors.append(
                "verified_dispatch_authorizations.csv:"
                f"{row_number}: verifier and approver must differ"
            )
        errors.extend(row_errors)
        if row_errors:
            continue
        digest = stable_hash(
            SCHEMA_VERSION,
            "dispatch_authorization",
            row["authorization_source_id"],
            row["actor_role_code"],
            row["actor_agency_id"],
            row["target_agency_id"],
            row["permitted_action"],
            row["district_code"],
            row["incident_type_code"],
            row["legal_basis_id"],
            row["effective_from"],
        )
        verified_authorizations.append(
            {
                "authorization_hash_sha256": digest,
                **row,
                "verification_status": "verified",
                "is_official_authorization": True,
                "requires_human_approval": False,
            }
        )
    authorization_hashes = [
        row["authorization_hash_sha256"]
        for row in verified_authorizations
    ]
    if len(authorization_hashes) != len(set(authorization_hashes)):
        errors.append("verified authorizations contain duplicate hashes")
    if errors:
        verified = []
        verified_authorizations = []
    verified = sorted(
        verified,
        key=lambda row: (
            row["spatial_hash"],
            row["agency_id"],
            row["responsibility_role"],
            row["responsibility_hash_sha256"],
        ),
    )
    verified_authorizations.sort(
        key=lambda row: (
            row["actor_role_code"],
            row["district_code"],
            row["incident_type_code"],
            row["target_agency_id"],
            row["permitted_action"],
        )
    )
    by_spatial_hash: dict[str, list[str]] = defaultdict(list)
    for row in verified:
        if row["spatial_hash"]:
            key = f"{row['spatial_hash_precision']}:{row['spatial_hash']}"
            by_spatial_hash[key].append(row["responsibility_hash_sha256"])

    status = (
        "invalid_inputs"
        if errors
        else "ready"
        if verified or verified_authorizations
        else "awaiting_verified_legal_inputs"
    )
    metadata = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_now(),
        "status": status,
        "assignment_count": len(verified),
        "dispatch_authorization_count": len(verified_authorizations),
        "legal_basis_count": len(legal_by_id),
        "notice": (
            "This layer is never populated from candidate assignments. "
            "It requires independently verified legal inputs."
        ),
    }
    quality = {
        "metadata": metadata,
        "passed": not errors,
        "errors": errors,
        "checks": {
            "all_agencies_known": all(
                row["agency_id"] in agency_ids for row in verified
            ),
            "all_legal_bases_verified": all(
                row["legal_basis_id"] in legal_by_id for row in verified
            ),
            "all_hashes_unique": len(verified)
            == len(
                {
                    row["responsibility_hash_sha256"]
                    for row in verified
                }
            ),
            "all_authorization_hashes_unique": (
                len(verified_authorizations)
                == len(
                    {
                        row["authorization_hash_sha256"]
                        for row in verified_authorizations
                    }
                )
            ),
        },
    }
    write_jsonl(
        VERIFIED_DIR / "legal_responsibility_hash_index.jsonl",
        verified,
    )
    verified_csv_fields = (
        "responsibility_hash_sha256",
        *VERIFIED_ASSIGNMENT_FIELDS,
        "verification_status",
        "is_official_legal_assignment",
        "requires_human_approval",
    )
    write_csv(
        VERIFIED_DIR / "legal_responsibility_hash_index.csv",
        verified,
        verified_csv_fields,
    )
    write_json(
        VERIFIED_DIR / "by_spatial_hash.json",
        {"metadata": metadata, "cells": dict(sorted(by_spatial_hash.items()))},
    )
    write_jsonl(
        VERIFIED_DIR / "dispatch_authorization_hash_index.jsonl",
        verified_authorizations,
    )
    dispatch_csv_fields = (
        "authorization_hash_sha256",
        *DISPATCH_AUTHORIZATION_FIELDS,
        "verification_status",
        "is_official_authorization",
        "requires_human_approval",
    )
    write_csv(
        VERIFIED_DIR / "dispatch_authorization_hash_index.csv",
        verified_authorizations,
        dispatch_csv_fields,
    )
    by_actor_role: dict[str, list[str]] = defaultdict(list)
    for row in verified_authorizations:
        by_actor_role[row["actor_role_code"]].append(
            row["authorization_hash_sha256"]
        )
    write_json(
        VERIFIED_DIR / "authorization_by_actor_role.json",
        {
            "metadata": metadata,
            "actor_roles": dict(sorted(by_actor_role.items())),
        },
    )
    write_json(VERIFIED_DIR / "quality_report.json", quality)
    if errors:
        raise RuntimeError(
            "Verified responsibility input validation failed:\n"
            + "\n".join(errors)
        )
    return quality


def build() -> dict[str, Any]:
    remove_legacy_outputs()
    write_input_templates()
    write_schemas()
    districts = DistrictIndex()
    agencies = AgencyRegistry(districts)
    legal_authority = build_legal_authority_evidence(
        districts,
        agencies,
    )
    assignments: list[dict[str, Any]] = []
    asset_buckets: dict[tuple[int, int], list[dict[str, Any]]] = defaultdict(list)
    asset_cells: dict[str, dict[str, Any]] = {}
    signal_cells: dict[str, dict[str, Any]] = {}
    source_counts: Counter[str] = Counter()
    source_input_counts: Counter[str] = Counter()
    out_of_scope_counts: Counter[str] = Counter()
    owner_counts: Counter[str] = Counter()
    unmapped_owners: Counter[str] = Counter()
    ignored_mitigation_fields: Counter[str] = Counter()
    district_field_conflicts: Counter[str] = Counter()
    unresolved_asset_owners: list[dict[str, Any]] = []
    spatial_conflicts: list[dict[str, Any]] = []

    for layer, config in ASSET_LAYERS.items():
        source = read_json(config["path"])
        for index, feature in enumerate(source.get("features", []), start=1):
            source_input_counts[layer] += 1
            geometry = feature.get("geometry") or {}
            properties = feature.get("properties") or {}
            center = geometry_center(geometry)
            if not center:
                out_of_scope_counts[f"{layer}:missing_geometry"] += 1
                continue
            raw_district = first_value(properties, config["district_fields"])
            has_district_conflict = districts.conflicts(
                raw_district, center
            )
            if has_district_conflict:
                district_field_conflicts[layer] += 1
            district = districts.resolve(
                raw_district, center, prefer_spatial=False
            )
            if not district:
                out_of_scope_counts[f"{layer}:outside_bangkok"] += 1
                continue
            owner = first_value(properties, config["owner_fields"])
            owner_counts[owner or "missing"] += 1
            agency_id, owner_method = agencies.owner_agency(owner, district)
            if owner and not agency_id:
                unmapped_owners[owner] += 1
            item_id = entity_id(layer, properties, config["id_fields"], index)
            item_name = first_value(properties, config["name_fields"])
            geohash7 = encode_geohash(center[1], center[0], 7)
            source_path = str(config["path"].relative_to(ROOT))
            if not agency_id:
                unresolved_asset_owners.append(
                    {
                        "review_hash_sha256": stable_hash(
                            SCHEMA_VERSION,
                            "unresolved_asset_owner",
                            item_id,
                            owner,
                            source_path,
                        ),
                        "review_type": "unresolved_asset_owner",
                        "entity_type": "drainage_asset",
                        "entity_id": item_id,
                        "entity_name_th": item_name,
                        "source_layer": layer,
                        "source_path": source_path,
                        "spatial_hash_geohash7": geohash7,
                        "district_code": district["district_code"],
                        "district_name_th": district["district_name_th"],
                        "source_owner_value": owner,
                        "owner_resolution_method": owner_method,
                        "review_status": "unresolved",
                        "requires_manual_review": True,
                        "is_placeholder": False,
                    }
                )
            if has_district_conflict:
                spatial_district = districts.locate(center[0], center[1])
                spatial_conflicts.append(
                    {
                        "review_hash_sha256": stable_hash(
                            SCHEMA_VERSION,
                            "district_spatial_conflict",
                            item_id,
                            raw_district,
                            (
                                spatial_district["district_code"]
                                if spatial_district
                                else None
                            ),
                        ),
                        "review_type": "district_spatial_conflict",
                        "entity_type": "drainage_asset",
                        "entity_id": item_id,
                        "entity_name_th": item_name,
                        "source_layer": layer,
                        "source_path": source_path,
                        "spatial_hash_geohash7": geohash7,
                        "source_district_value": raw_district,
                        "selected_district_code": district["district_code"],
                        "selected_district_name_th": district[
                            "district_name_th"
                        ],
                        "polygon_district_code": (
                            spatial_district["district_code"]
                            if spatial_district
                            else None
                        ),
                        "polygon_district_name_th": (
                            spatial_district["district_name_th"]
                            if spatial_district
                            else None
                        ),
                        "review_status": "unresolved",
                        "requires_manual_review": True,
                        "is_placeholder": False,
                    }
                )
            if agency_id:
                add_assignment(
                    assignments,
                    entity_type="drainage_asset",
                    entity_id_value=item_id,
                    entity_name=item_name,
                    source_layer=layer,
                    geohash7=geohash7,
                    district=district,
                    agency_id=agency_id,
                    agencies=agencies,
                    responsibility_role="asset_owner_candidate",
                    assignment_method=owner_method,
                    confidence=0.9 if owner_method == "explicit_owner" else 0.78,
                    evidence_text=f"owner={owner}",
                    source_path=source_path,
                )
            district_agency = agencies.district_agency(district)
            if district_agency:
                add_assignment(
                    assignments,
                    entity_type="drainage_asset",
                    entity_id_value=item_id,
                    entity_name=item_name,
                    source_layer=layer,
                    geohash7=geohash7,
                    district=district,
                    agency_id=district_agency,
                    agencies=agencies,
                    responsibility_role="geographic_jurisdiction_candidate",
                    assignment_method="district_field_or_spatial_join",
                    confidence=0.82,
                    evidence_text=f"district={district['district_name_th']}",
                    source_path=source_path,
                    responsible_unit="ฝ่ายโยธา",
                )
            for point in geometry_samples(geometry):
                cell = encode_geohash(point[1], point[0], 7)
                cell_row = asset_cells.setdefault(
                    cell,
                    {"asset_refs": set(), "agency_ids": set()},
                )
                cell_row["asset_refs"].add(item_id)
                if agency_id:
                    cell_row["agency_ids"].add(agency_id)
                if district_agency:
                    cell_row["agency_ids"].add(district_agency)
                if agency_id:
                    asset_buckets[spatial_bucket(point)].append(
                        {
                            "point": point,
                            "entity_id": item_id,
                            "agency_id": agency_id,
                            "district": district,
                            "layer": layer,
                        }
                    )
            source_counts[layer] += 1

    for signal_type, config in SIGNAL_LAYERS.items():
        source = read_json(config["path"])
        for index, feature in enumerate(source.get("features", []), start=1):
            source_input_counts[signal_type] += 1
            geometry = feature.get("geometry") or {}
            properties = feature.get("properties") or {}
            center = geometry_center(geometry)
            if not center:
                out_of_scope_counts[f"{signal_type}:missing_geometry"] += 1
                continue
            raw_district = first_value(properties, config["district_fields"])
            has_district_conflict = districts.conflicts(
                raw_district, center
            )
            if has_district_conflict:
                district_field_conflicts[signal_type] += 1
            district = districts.resolve(raw_district, center)
            if not district:
                out_of_scope_counts[f"{signal_type}:outside_bangkok"] += 1
                continue
            district_agency = agencies.district_agency(district)
            item_id = entity_id(
                signal_type, properties, config["id_fields"], index
            )
            item_name = first_value(properties, config["name_fields"])
            geohash7 = encode_geohash(center[1], center[0], 7)
            source_path = str(config["path"].relative_to(ROOT))
            if has_district_conflict:
                source_district_name = districts.normalize_name(raw_district)
                source_district = (
                    districts.by_name.get(source_district_name)
                    if source_district_name
                    else None
                )
                spatial_conflicts.append(
                    {
                        "review_hash_sha256": stable_hash(
                            SCHEMA_VERSION,
                            "district_spatial_conflict",
                            item_id,
                            raw_district,
                            district["district_code"],
                        ),
                        "review_type": "district_spatial_conflict",
                        "entity_type": (
                            "monitoring_location"
                            if signal_type == "water_level_station"
                            else "flood_signal"
                        ),
                        "entity_id": item_id,
                        "entity_name_th": item_name,
                        "source_layer": signal_type,
                        "source_path": source_path,
                        "spatial_hash_geohash7": geohash7,
                        "source_district_value": raw_district,
                        "selected_district_code": district["district_code"],
                        "selected_district_name_th": district[
                            "district_name_th"
                        ],
                        "source_district_code": (
                            source_district["district_code"]
                            if source_district
                            else None
                        ),
                        "review_status": "unresolved",
                        "requires_manual_review": True,
                        "is_placeholder": False,
                    }
                )
            cell_row = signal_cells.setdefault(
                geohash7,
                {"signal_refs": set(), "agency_ids": set()},
            )
            cell_row["signal_refs"].add(item_id)

            if signal_type == "water_level_station":
                add_assignment(
                    assignments,
                    entity_type="monitoring_location",
                    entity_id_value=item_id,
                    entity_name=item_name,
                    source_layer=signal_type,
                    geohash7=geohash7,
                    district=district,
                    agency_id="bma-dds",
                    agencies=agencies,
                    responsibility_role="data_custodian",
                    assignment_method="official_source_owner",
                    confidence=0.9,
                    evidence_text="Bangkok DDS water-level source",
                    source_path=source_path,
                )
                cell_row["agency_ids"].add("bma-dds")
            else:
                nearest, distance = nearest_asset(center, asset_buckets)
                primary_agency = (
                    nearest["agency_id"] if nearest and distance is not None else district_agency
                )
                method = (
                    "nearest_explicit_asset_owner"
                    if nearest and distance is not None
                    else "district_fallback"
                )
                confidence = (
                    max(0.58, 0.88 - (distance or 0) / 1000)
                    if nearest and distance is not None
                    else 0.7
                )
                if primary_agency:
                    add_assignment(
                        assignments,
                        entity_type="flood_signal",
                        entity_id_value=item_id,
                        entity_name=item_name,
                        source_layer=signal_type,
                        geohash7=geohash7,
                        district=district,
                        agency_id=primary_agency,
                        agencies=agencies,
                        responsibility_role="primary_response_candidate",
                        assignment_method=method,
                        confidence=confidence,
                        evidence_text=(
                            f"nearest_asset={nearest['entity_id']}; distance_m={distance:.1f}"
                            if nearest and distance is not None
                            else f"district={district['district_name_th'] if district else 'unknown'}"
                        ),
                        source_path=source_path,
                        responsible_unit=(
                            "ฝ่ายโยธา" if primary_agency == district_agency else None
                        ),
                        nearest_asset_id=nearest["entity_id"] if nearest else None,
                        nearest_asset_distance_m=distance,
                    )
                    cell_row["agency_ids"].add(primary_agency)
                support_agency = (
                    district_agency
                    if primary_agency and primary_agency.startswith("bma-dds")
                    else "bma-dds"
                )
                if support_agency and support_agency != primary_agency:
                    add_assignment(
                        assignments,
                        entity_type="flood_signal",
                        entity_id_value=item_id,
                        entity_name=item_name,
                        source_layer=signal_type,
                        geohash7=geohash7,
                        district=district,
                        agency_id=support_agency,
                        agencies=agencies,
                        responsibility_role="support_response_candidate",
                        assignment_method="flood_response_support_rule",
                        confidence=0.6,
                        evidence_text="District and DDS coordinate flood response.",
                        source_path=source_path,
                        responsible_unit=(
                            "ฝ่ายโยธา" if support_agency == district_agency else None
                        ),
                    )
                    cell_row["agency_ids"].add(support_agency)
                if signal_type == "official_risk_point":
                    for field in ("สพน", "กรท", "สคน", "กรบ"):
                        if clean_text(properties.get(field)):
                            ignored_mitigation_fields[field] += 1

            if district_agency:
                add_assignment(
                    assignments,
                    entity_type=(
                        "monitoring_location"
                        if signal_type == "water_level_station"
                        else "flood_signal"
                    ),
                    entity_id_value=item_id,
                    entity_name=item_name,
                    source_layer=signal_type,
                    geohash7=geohash7,
                    district=district,
                    agency_id=district_agency,
                    agencies=agencies,
                    responsibility_role="geographic_jurisdiction_candidate",
                    assignment_method="district_field_or_spatial_join",
                    confidence=0.82,
                    evidence_text=f"district={district['district_name_th']}",
                    source_path=source_path,
                    responsible_unit="ฝ่ายโยธา",
                )
                cell_row["agency_ids"].add(district_agency)
            source_counts[signal_type] += 1

    deduplicated = {
        row["responsibility_hash_sha256"]: row for row in assignments
    }
    assignments = sorted(
        deduplicated.values(),
        key=lambda row: (
            row["spatial_hash_geohash7"],
            row["entity_type"],
            row["entity_id"],
            row["responsibility_role"],
            row["agency_id"],
        ),
    )
    district_hash = build_district_hash(districts, agencies)
    service_area_rows, service_areas_by_district = (
        build_service_area_index(districts, agencies)
    )
    capability_rows, capabilities_by_district_incident = (
        build_agency_incident_capability_index(service_area_rows)
    )
    district_agency_rows, district_agency_profiles = (
        build_district_agency_responsibility_index(
            districts,
            agencies,
            assignments,
            service_area_rows,
            capability_rows,
        )
    )
    unresolved_asset_owners.sort(
        key=lambda row: (row["source_layer"], row["entity_id"])
    )
    spatial_conflicts.sort(
        key=lambda row: (row["source_layer"], row["entity_id"])
    )
    all_cells: dict[str, dict[str, Any]] = {}
    for cell in sorted(set(asset_cells) | set(signal_cells)):
        asset = asset_cells.get(cell, {})
        signal = signal_cells.get(cell, {})
        all_cells[cell] = {
            "asset_refs": sorted(asset.get("asset_refs", set())),
            "signal_refs": sorted(signal.get("signal_refs", set())),
            "agency_ids": sorted(
                set(asset.get("agency_ids", set()))
                | set(signal.get("agency_ids", set()))
            ),
        }

    legal_sources = {
        "metadata": {
            "schema_version": SCHEMA_VERSION,
            "generated_at": utc_now(),
            "notice": "References require legal review before an assignment may be marked verified.",
        },
        "sources": [
            {
                "legal_basis_id": "dds-official-duties",
                "title_th": "ภารกิจหน้าที่ของสำนักการระบายน้ำ",
                "url": "https://dds.bangkok.go.th/about3.php",
                "source_class": "official_operational_mandate",
                "verification_status": "reference_not_legal_reviewed",
            },
            {
                "legal_basis_id": "bma-flood-plan-2569",
                "title_th": "แผนปฏิบัติการป้องกันและแก้ไขปัญหาน้ำท่วมกรุงเทพมหานคร ประจำปี 2569",
                "url": "https://dds.bangkok.go.th/content/doc3/index.php",
                "source_class": "official_operational_plan",
                "verification_status": "reference_not_legal_reviewed",
            },
            {
                "legal_basis_id": "bma-disaster-plan-2564-2570",
                "title_th": "แผนการป้องกันและบรรเทาสาธารณภัยกรุงเทพมหานคร พ.ศ. 2564-2570",
                "url": "https://budget.bangkok.go.th/main/topic.php?topic_id=3151",
                "source_class": "official_disaster_plan",
                "verification_status": "reference_not_legal_reviewed",
            },
            {
                "legal_basis_id": "dds-water-control-duties",
                "title_th": "ภารกิจสำนักงานระบบควบคุมน้ำ",
                "url": "https://dds.bangkok.go.th/about2_5.php",
                "source_class": "official_operational_mandate",
                "verification_status": "reference_not_legal_reviewed",
            },
            {
                "legal_basis_id": "dds-pipe-division-duties",
                "title_th": "ภารกิจกองระบบท่อระบายน้ำ",
                "url": "https://dds.bangkok.go.th/about2_6.php",
                "source_class": "official_operational_mandate",
                "verification_status": "reference_not_legal_reviewed",
            },
            {
                "legal_basis_id": "dds-canal-division-duties",
                "title_th": "ภารกิจกองระบบคลอง",
                "url": "https://dds.bangkok.go.th/about2_7.php",
                "source_class": "official_operational_mandate",
                "verification_status": "reference_not_legal_reviewed",
            },
            {
                "legal_basis_id": "bma-district-public-works-duties",
                "title_th": "ภารกิจฝ่ายโยธา สำนักงานเขต",
                "url": "https://webportal.bangkok.go.th/pranakorn/page/sub/2846/",
                "source_class": "official_district_operational_mandate",
                "verification_status": "reference_not_legal_reviewed",
            },
            {
                "legal_basis_id": "bma-organization-authority-index",
                "title_th": "กฎหมายจัดตั้งองค์กรและการบริหารงาน กรุงเทพมหานคร",
                "url": "https://webportal.bangkok.go.th/law/page/sub/22566",
                "source_class": "official_legal_document_index",
                "verification_status": "reference_not_legal_reviewed",
            },
        ],
    }
    legal_reference_rows = build_legal_reference_hash_index(
        legal_sources
    )

    metadata = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_now(),
        "scope": "Bangkok flood-response operational routing",
        "geohash_precision": 7,
        "district_fallback_precision": 6,
        "assignment_count": len(assignments),
        "agency_count": len(agencies.rows),
        "service_area_candidate_count": len(service_area_rows),
        "agency_incident_capability_count": len(capability_rows),
        "district_agency_responsibility_summary_count": len(
            district_agency_rows
        ),
        "legal_reference_count": len(legal_reference_rows),
        "manual_review_count": (
            len(unresolved_asset_owners) + len(spatial_conflicts)
        ),
        "source_input_counts": dict(sorted(source_input_counts.items())),
        "source_feature_counts": dict(sorted(source_counts.items())),
        "out_of_scope_counts": dict(sorted(out_of_scope_counts.items())),
        "legal_notice": (
            "All assignments are candidates. This index does not determine "
            "legal liability and requires human verification."
        ),
    }
    role_files = {
        "geographic_jurisdiction_hash_index.jsonl": {
            "geographic_jurisdiction_candidate"
        },
        "asset_owner_hash_index.jsonl": {"asset_owner_candidate"},
        "flood_signal_routing_hash_index.jsonl": {
            "primary_response_candidate",
            "support_response_candidate",
        },
        "data_custodian_hash_index.jsonl": {"data_custodian"},
    }
    write_json(
        CANDIDATE_DIR / "agency_master.json",
        {
            "metadata": metadata,
            "agencies": sorted(
                agencies.rows.values(), key=lambda row: row["agency_id"]
            ),
        },
    )
    write_jsonl(CANDIDATE_DIR / "all_assignments.jsonl", assignments)
    write_csv(CANDIDATE_DIR / "all_assignments.csv", assignments)
    for file_name, roles in role_files.items():
        write_jsonl(
            CANDIDATE_DIR / file_name,
            [
                row
                for row in assignments
                if row["responsibility_role"] in roles
            ],
        )
    write_json(
        CANDIDATE_DIR / "responsibility_by_geohash7.json",
        {"metadata": metadata, "cells": all_cells},
    )
    write_json(CANDIDATE_DIR / "district_by_geohash6.json", district_hash)
    write_json(
        CANDIDATE_DIR / "legal_basis_references.json",
        legal_sources,
    )
    write_jsonl(
        CANDIDATE_DIR / "legal_reference_hash_index.jsonl",
        legal_reference_rows,
    )
    write_jsonl(
        CANDIDATE_DIR / "agency_service_area_hash_index.jsonl",
        service_area_rows,
    )
    write_json(
        CANDIDATE_DIR / "agency_service_areas_by_district.json",
        {
            "metadata": {
                **metadata,
                "notice": (
                    "Official web-page references, not verified legal "
                    "assignments."
                ),
            },
            "districts": service_areas_by_district,
        },
    )
    write_json(
        CANDIDATE_DIR / "incident_type_registry.json",
        build_incident_type_registry(),
    )
    write_jsonl(
        CANDIDATE_DIR / "agency_incident_capability_hash_index.jsonl",
        capability_rows,
    )
    write_json(
        CANDIDATE_DIR
        / "agency_capabilities_by_district_incident.json",
        {
            "metadata": {
                **metadata,
                "notice": (
                    "Capability candidates are derived from official "
                    "service-area references and require human approval."
                ),
            },
            "district_incidents": capabilities_by_district_incident,
        },
    )
    write_jsonl(
        CANDIDATE_DIR
        / "district_agency_responsibility_hash_index.jsonl",
        district_agency_rows,
    )
    write_json(
        CANDIDATE_DIR / "responsible_agencies_by_district.json",
        {
            "metadata": {
                **metadata,
                "notice": (
                    "Complete district-level candidate summary assembled "
                    "from entity assignments, service areas, and incident "
                    "capabilities. It is not a verified legal assignment."
                ),
            },
            "districts": district_agency_profiles,
        },
    )
    write_jsonl(
        REVIEW_DIR / "unresolved_asset_owners.jsonl",
        unresolved_asset_owners,
    )
    write_jsonl(
        REVIEW_DIR / "spatial_conflicts.jsonl",
        spatial_conflicts,
    )
    write_json(
        REVIEW_DIR / "review_manifest.json",
        {
            "metadata": {
                "schema_version": SCHEMA_VERSION,
                "generated_at": utc_now(),
                "status": (
                    "manual_review_required"
                    if unresolved_asset_owners or spatial_conflicts
                    else "clear"
                ),
                "is_placeholder_layer": False,
            },
            "counts": {
                "unresolved_asset_owners": len(
                    unresolved_asset_owners
                ),
                "spatial_conflicts": len(spatial_conflicts),
                "total": (
                    len(unresolved_asset_owners)
                    + len(spatial_conflicts)
                ),
            },
            "policy": (
                "Review records describe actual source entities. "
                "They are excluded from verified assignments until resolved."
            ),
        },
    )

    validation_checks = {
        "district_count_is_50": len(districts.features) == 50,
        "district_agency_count_is_50": (
            sum(
                row["agency_category"] == "bma_district_office"
                for row in agencies.rows.values()
            )
            == 50
        ),
        "responsibility_hashes_unique": len(assignments)
        == len({row["responsibility_hash_sha256"] for row in assignments}),
        "all_agency_foreign_keys_valid": all(
            row["agency_id"] in agencies.rows for row in assignments
        ),
        "all_assignments_unverified": all(
            not row["is_official_legal_assignment"] for row in assignments
        ),
        "all_assignments_have_bangkok_district": all(
            row["district_code"] and row["district_name_th"]
            for row in assignments
        ),
        "all_assignments_have_geohash7": all(
            len(row["spatial_hash_geohash7"]) == 7 for row in assignments
        ),
        "one_primary_per_flood_signal": (
            sum(
                row["responsibility_role"] == "primary_response_candidate"
                for row in assignments
            )
            == source_counts["official_risk_point"]
            + source_counts["road_flood_sensor"]
        ),
        "district_fallback_covers_all_50_agencies": (
            len(
                {
                    agency_id
                    for agency_ids in district_hash["cells"].values()
                    for agency_id in agency_ids
                }
            )
            == 50
        ),
        "has_spatial_cells": bool(all_cells),
        "has_district_fallback_cells": bool(district_hash["cells"]),
        "official_service_areas_cover_50_districts": (
            len(service_areas_by_district) == 50
            and all(
                len(hashes) == 2
                for hashes in service_areas_by_district.values()
            )
        ),
        "official_service_area_hashes_unique": len(service_area_rows)
        == len(
            {
                row["service_area_hash_sha256"]
                for row in service_area_rows
            }
        ),
        "agency_incident_capability_count_is_300": (
            len(capability_rows) == 300
        ),
        "agency_incident_capability_hashes_unique": len(
            capability_rows
        )
        == len(
            {
                row["capability_hash_sha256"]
                for row in capability_rows
            }
        ),
        "legal_reference_hashes_unique": len(legal_reference_rows)
        == len(
            {
                row["legal_reference_hash_sha256"]
                for row in legal_reference_rows
            }
        ),
        "district_agency_summary_covers_all_50_districts": (
            len(district_agency_profiles) == 50
            and all(
                profile["candidate_agency_count"] > 0
                for profile in district_agency_profiles
            )
        ),
        "district_agency_summary_hashes_unique": len(
            district_agency_rows
        )
        == len(
            {
                row[
                    "district_agency_responsibility_hash_sha256"
                ]
                for row in district_agency_rows
            }
        ),
        "district_agency_summary_contains_all_source_records": (
            sum(
                row["source_record_count"]
                for row in district_agency_rows
                if row["responsibility_scope"]
                == "entity_assignment"
            )
            == len(assignments)
            and sum(
                row["source_record_count"]
                for row in district_agency_rows
                if row["responsibility_scope"] == "service_area"
            )
            == len(service_area_rows)
            and sum(
                row["source_record_count"]
                for row in district_agency_rows
                if row["responsibility_scope"]
                == "incident_capability"
            )
            == len(capability_rows)
        ),
        "review_records_are_actual_not_placeholders": all(
            row["is_placeholder"] is False
            for row in unresolved_asset_owners + spatial_conflicts
        ),
        "review_hashes_unique": (
            len(unresolved_asset_owners) + len(spatial_conflicts)
            == len(
                {
                    row["review_hash_sha256"]
                    for row in unresolved_asset_owners + spatial_conflicts
                }
            )
        ),
    }
    quality = {
        "metadata": metadata,
        "checks": validation_checks,
        "passed": all(validation_checks.values()),
        "responsibility_role_counts": dict(
            sorted(Counter(row["responsibility_role"] for row in assignments).items())
        ),
        "owner_value_counts": dict(owner_counts.most_common()),
        "unmapped_owner_counts": dict(unmapped_owners.most_common()),
        "ignored_mitigation_field_counts": dict(
            ignored_mitigation_fields.most_common()
        ),
        "district_field_spatial_conflicts": dict(
            district_field_conflicts.most_common()
        ),
        "ignored_mitigation_field_reason": (
            "The source contains at least one mitigation text that conflicts "
            "with the risk point district; fields are retained in source data "
            "but excluded from automatic agency routing."
        ),
        "spatial_cell_count": len(all_cells),
        "district_fallback_cell_count": len(district_hash["cells"]),
        "service_area_candidate_count": len(service_area_rows),
        "agency_incident_capability_count": len(capability_rows),
        "district_agency_responsibility_summary_count": len(
            district_agency_rows
        ),
        "legal_reference_count": len(legal_reference_rows),
        "manual_review_counts": {
            "unresolved_asset_owners": len(unresolved_asset_owners),
            "spatial_conflicts": len(spatial_conflicts),
        },
    }
    write_json(CANDIDATE_DIR / "quality_report.json", quality)
    if not quality["passed"]:
        raise RuntimeError("Responsibility index validation failed")
    evidence = build_official_document_evidence(set(agencies.rows))
    district_process_rows = build_district_office_flood_process_index(
        districts,
        service_area_rows,
        evidence,
    )
    acquisition = build_acquired_source_evidence(
        districts,
        unresolved_asset_owners,
        spatial_conflicts,
    )
    data_source_rows = build_data_source_registry(
        legal_sources,
        evidence,
        acquisition["sources"],
        legal_authority["sources"],
    )
    evidence_checks = {
        "district_process_covers_all_50_districts": (
            len(district_process_rows) == 50
            and {
                row["district_code"] for row in district_process_rows
            }
            == {
                row["district_code"] for row in districts.features
            }
        ),
        "district_process_hashes_unique": len(district_process_rows)
        == len(
            {
                row["district_process_hash_sha256"]
                for row in district_process_rows
            }
        ),
        "all_district_processes_require_confirmation": all(
            row["requires_district_confirmation"] is True
            and row["district_specific_sop_verified"] is False
            and row["is_official_legal_assignment"] is False
            for row in district_process_rows
        ),
        "data_source_hashes_unique": len(data_source_rows)
        == len(
            {
                row["data_source_hash_sha256"]
                for row in data_source_rows
            }
        ),
        "all_data_sources_use_https": all(
            row["source_url"].startswith("https://")
            for row in data_source_rows
        ),
    }
    evidence["quality"]["checks"].update(evidence_checks)
    evidence["quality"]["metadata"].update(
        {
            "district_process_count": len(district_process_rows),
            "data_source_count": len(data_source_rows),
        }
    )
    evidence["quality"]["passed"] = all(
        evidence["quality"]["checks"].values()
    )
    write_json(
        EVIDENCE_DIR / "quality_report.json",
        evidence["quality"],
    )
    if not evidence["quality"]["passed"]:
        raise RuntimeError("District process or source lineage validation failed")
    write_ingestion_risk_report(
        data_source_rows,
        unresolved_asset_owners,
        spatial_conflicts,
    )
    verified_quality = build_verified_index(
        set(agencies.rows),
        {district["district_code"] for district in districts.features},
    )
    write_hash_index_catalog(
        assignments=assignments,
        service_area_rows=service_area_rows,
        capability_rows=capability_rows,
        legal_reference_rows=legal_reference_rows,
        district_agency_rows=district_agency_rows,
        document_evidence_rows=evidence["documents"],
        mission_duty_rows=evidence["mission_duties"],
        sop_process_rows=evidence["sop_processes"],
        district_process_rows=district_process_rows,
        data_source_rows=data_source_rows,
        unresolved_asset_owners=unresolved_asset_owners,
        spatial_conflicts=spatial_conflicts,
        acquisition=acquisition,
        legal_authority=legal_authority,
        verified_quality=verified_quality,
    )
    write_security_policy()
    analytics_manifest_path = (
        VISUALIZATION_DIR / "visualization_manifest.json"
    )
    normalization_manifest_path = (
        NORMALIZED_DIR / "normalization_manifest.json"
    )
    analytics_available = (
        analytics_manifest_path.exists()
        and normalization_manifest_path.exists()
    )
    analytics_manifest = (
        read_json(analytics_manifest_path)
        if analytics_available
        else {}
    )
    normalization_manifest = (
        read_json(normalization_manifest_path)
        if analytics_available
        else {}
    )
    manifest = {
        "metadata": {
            "schema_version": SCHEMA_VERSION,
            "generated_at": utc_now(),
            "scope": "Bangkok flood responsibility hash indexes",
        },
        "layers": {
            "candidate": {
                "status": "candidate_unverified",
                "assignment_count": len(assignments),
                "district_agency_responsibility_summary_count": len(
                    district_agency_rows
                ),
                "directory": "candidate/",
                "may_be_used_as_legal_assignment": False,
            },
            "inputs": {
                "status": "manual_official_evidence_required",
                "directory": "inputs/",
                "purpose": "Controlled intake for legal and ownership evidence.",
            },
            "review": {
                "status": (
                    "manual_review_required"
                    if unresolved_asset_owners or spatial_conflicts
                    else "clear"
                ),
                "record_count": (
                    len(unresolved_asset_owners) + len(spatial_conflicts)
                ),
                "directory": "review/",
                "contains_placeholders": False,
            },
            "evidence": {
                "status": evidence["quality"]["metadata"]["status"],
                "document_count": len(evidence["documents"]),
                "mission_duty_count": len(evidence["mission_duties"]),
                "sop_process_count": len(evidence["sop_processes"]),
                "district_process_count": len(district_process_rows),
                "data_source_count": len(data_source_rows),
                "directory": "evidence/",
                "may_be_used_as_legal_assignment": False,
            },
            "acquisition": {
                "status": "public_evidence_acquired_with_open_gaps",
                "source_count": len(acquisition["sources"]),
                "asset_owner_status_count": len(
                    acquisition["owner_statuses"]
                ),
                "spatial_conflict_status_count": len(
                    acquisition["spatial_statuses"]
                ),
                "district_sop_availability_count": len(
                    acquisition["district_sop_rows"]
                ),
                "directory": "acquisition/",
                "may_be_used_as_legal_assignment": False,
                "may_auto_dispatch": False,
            },
            "legal_authority": {
                "status": legal_authority["quality"]["metadata"][
                    "status"
                ],
                "source_count": len(legal_authority["sources"]),
                "role_count": len(legal_authority["roles"]),
                "provision_count": len(legal_authority["provisions"]),
                "district_candidate_count": len(
                    legal_authority["district_candidates"]
                ),
                "review_queue_count": len(
                    legal_authority["review_queue"]
                ),
                "verified_legal_assignment_count": 0,
                "verified_dispatch_authorization_count": 0,
                "directory": "legal_authority/",
                "may_be_used_as_legal_assignment": False,
                "may_auto_dispatch": False,
            },
            "verified": {
                "status": verified_quality["metadata"]["status"],
                "assignment_count": verified_quality["metadata"][
                    "assignment_count"
                ],
                "dispatch_authorization_count": verified_quality[
                    "metadata"
                ]["dispatch_authorization_count"],
                "directory": "verified/",
                "contains_only_reviewed_assignments": True,
                "currently_usable": bool(
                    verified_quality["metadata"]["assignment_count"]
                    or verified_quality["metadata"][
                        "dispatch_authorization_count"
                    ]
                ),
            },
            "security": {
                "status": "controls_active_with_open_findings",
                "ingestion_risk_report": (
                    "security/ingestion_risk_report.json"
                ),
                "directory": "security/",
            },
            "analytics": {
                "status": (
                    "derived_analytical_artifacts_ready"
                    if analytics_available
                    else "not_built"
                ),
                "prepared_directory": "prepared/",
                "normalized_directory": "normalized/",
                "visualization_directory": "visualization/",
                "normalization_passed": normalization_manifest.get(
                    "passed",
                    False,
                ),
                "source_fingerprint_sha256": analytics_manifest.get(
                    "metadata",
                    {},
                ).get("source_fingerprint_sha256"),
                "frontend_artifact": False,
                "operational_dispatch_input": False,
            },
        },
        "separation_rule": (
            "Candidate assignments are never promoted automatically. "
            "Verified outputs are built only from independently reviewed inputs."
        ),
    }
    write_json(OUTPUT_DIR / "manifest.json", manifest)
    write_integrity_manifest()
    return quality


def query(
    latitude: float,
    longitude: float,
    incident_type_code: str | None = None,
) -> dict[str, Any]:
    cell7 = encode_geohash(latitude, longitude, 7)
    cell6 = encode_geohash(latitude, longitude, 6)
    responsibility = read_json(
        CANDIDATE_DIR / "responsibility_by_geohash7.json"
    )
    district = read_json(CANDIDATE_DIR / "district_by_geohash6.json")
    agency_master = read_json(CANDIDATE_DIR / "agency_master.json")
    service_area_index = read_json(
        CANDIDATE_DIR / "agency_service_areas_by_district.json"
    )
    service_area_rows = read_jsonl(
        CANDIDATE_DIR / "agency_service_area_hash_index.jsonl"
    )
    service_area_by_hash = {
        row["service_area_hash_sha256"]: row for row in service_area_rows
    }
    capability_rows = read_jsonl(
        CANDIDATE_DIR
        / "agency_incident_capability_hash_index.jsonl"
    )
    incident_types = {
        row["incident_type_code"]
        for row in build_incident_type_registry()["incident_types"]
    }
    agency_by_id = {
        row["agency_id"]: row for row in agency_master["agencies"]
    }
    cell = responsibility["cells"].get(
        cell7, {"asset_refs": [], "signal_refs": [], "agency_ids": []}
    )
    exact_district = DistrictIndex().locate(longitude, latitude)
    exact_district_id = (
        f"bma-district-{exact_district['district_code']}"
        if exact_district
        else None
    )
    district_ids = (
        [exact_district_id]
        if exact_district_id
        else district["cells"].get(cell6, [])
    )
    exact_district_code = (
        exact_district["district_code"] if exact_district else None
    )
    service_area_hashes = (
        service_area_index["districts"].get(exact_district_code, [])
        if exact_district_code
        else []
    )
    agency_ids = list(dict.fromkeys(cell["agency_ids"] + district_ids))
    return {
        "query": {
            "latitude": latitude,
            "longitude": longitude,
            "spatial_hash_geohash7": cell7,
            "district_hash_geohash6": cell6,
            "incident_type_code": incident_type_code,
            "incident_type_known": (
                incident_type_code in incident_types
                if incident_type_code
                else None
            ),
        },
        "asset_refs": cell["asset_refs"],
        "signal_refs": cell["signal_refs"],
        "agency_candidates": [
            agency_by_id[agency_id]
            for agency_id in agency_ids
            if agency_id in agency_by_id
        ],
        "official_reference_service_area_candidates": [
            service_area_by_hash[value]
            for value in service_area_hashes
            if value in service_area_by_hash
        ],
        "agency_incident_capability_candidates": [
            row
            for row in capability_rows
            if row["district_code"] == exact_district_code
            and (
                incident_type_code is None
                or row["incident_type_code"] == incident_type_code
            )
        ],
        "routing_status": (
            "unknown_incident_type"
            if incident_type_code
            and incident_type_code not in incident_types
            else "candidate_requires_review"
            if incident_type_code
            else "candidate_requires_incident_type_and_review"
        ),
        "verification_status": "candidate_unverified",
        "requires_human_approval": True,
        "legal_notice": "This lookup does not determine legal liability.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build Bangkok flood responsibility hash indexes"
    )
    parser.add_argument(
        "--query",
        nargs=2,
        type=float,
        metavar=("LATITUDE", "LONGITUDE"),
        help="Build, then query one coordinate",
    )
    parser.add_argument(
        "--incident-type",
        help="Filter coordinate lookup by one incident type code",
    )
    args = parser.parse_args()
    quality = build()
    print(
        json.dumps(
            {
                "status": "ok",
                "assignment_count": quality["metadata"]["assignment_count"],
                "spatial_cell_count": quality["spatial_cell_count"],
                "quality_passed": quality["passed"],
            },
            ensure_ascii=False,
        )
    )
    if args.query:
        print(
            json.dumps(
                query(*args.query, args.incident_type),
                ensure_ascii=False,
                indent=2,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
