#!/usr/bin/env python3
"""Prepare, normalize, and visualize Bangkok flood responsibility data.

The outputs are analytical artifacts. They do not promote candidate records
to verified legal assignments and are not frontend integration code.
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


ROOT = Path(__file__).resolve().parents[1]
RESPONSIBILITY_DIR = ROOT / "data" / "responsibility"
PREPARED_DIR = RESPONSIBILITY_DIR / "prepared"
NORMALIZED_DIR = RESPONSIBILITY_DIR / "normalized"
VISUALIZATION_DIR = RESPONSIBILITY_DIR / "visualization"
GEOJSON_DIR = ROOT / "data" / "geojson"
SCHEMA_VERSION = "1.0.0"
GEOHASH_BASE32 = "0123456789bcdefghjkmnpqrstuvwxyz"


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
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def stable_hash(*parts: Any) -> str:
    payload = "|".join("" if part is None else str(part) for part in parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def clean_text(value: Any) -> str | None:
    if value is None:
        return None
    result = re.sub(r"\s+", " ", str(value)).strip()
    return result or None


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
            json.dumps(row, ensure_ascii=False, separators=(",", ":"))
            + "\n"
            for row in rows
        ),
        encoding="utf-8",
    )


def csv_value(value: Any) -> Any:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (list, dict)):
        return canonical_json(value)
    return value


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=fields,
            extrasaction="ignore",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(
            {
                key: csv_value(value)
                for key, value in row.items()
            }
            for row in rows
        )


def prepare_datasets() -> dict[str, Any]:
    candidate_dir = RESPONSIBILITY_DIR / "candidate"
    evidence_dir = RESPONSIBILITY_DIR / "evidence"
    review_dir = RESPONSIBILITY_DIR / "review"

    agencies = read_json(candidate_dir / "agency_master.json")["agencies"]
    profiles = read_json(
        candidate_dir / "responsible_agencies_by_district.json"
    )["districts"]
    processes = read_jsonl(
        evidence_dir / "district_office_flood_process_hash_index.jsonl"
    )
    missions = read_jsonl(
        evidence_dir / "mission_duty_evidence_hash_index.jsonl"
    )
    unresolved = read_jsonl(
        review_dir / "unresolved_asset_owners.jsonl"
    )
    conflicts = read_jsonl(review_dir / "spatial_conflicts.jsonl")

    agency_by_id = {row["agency_id"]: row for row in agencies}
    profile_by_district = {
        row["district_code"]: row for row in profiles
    }
    process_by_district = {
        row["district_code"]: row for row in processes
    }
    district_agencies = sorted(
        (
            row
            for row in agencies
            if row["agency_category"] == "bma_district_office"
        ),
        key=lambda row: row["district_code"],
    )

    district_rows = []
    for district_agency in district_agencies:
        code = district_agency["district_code"]
        profile = profile_by_district[code]
        process = process_by_district[code]
        row = {
            "district_code": code,
            "district_name_th": clean_text(
                district_agency["district_name_th"]
            ),
            "district_agency_id": district_agency["agency_id"],
            "district_agency_name_th": clean_text(
                district_agency["agency_name_th"]
            ),
            "candidate_agency_count": profile[
                "candidate_agency_count"
            ],
            "candidate_agency_ids": sorted(
                item["agency_id"] for item in profile["agencies"]
            ),
            "summary_hash_count": profile["summary_hash_count"],
            "source_record_count": profile["source_record_count"],
            "process_stage_count": len(process["process_stages"]),
            "process_stages": process["process_stages"],
            "service_area_candidate_agency_ids": process[
                "service_area_candidate_agency_ids"
            ],
            "mission_duty_hash_sha256": process[
                "mission_duty_hash_sha256"
            ],
            "sop_process_hashes_sha256": process[
                "sop_process_hashes_sha256"
            ],
            "district_process_hash_sha256": process[
                "district_process_hash_sha256"
            ],
            "verification_status": process["verification_status"],
            "district_specific_sop_verified": process[
                "district_specific_sop_verified"
            ],
            "requires_district_confirmation": process[
                "requires_district_confirmation"
            ],
            "timing_is_emergency_response_sla": process[
                "timing_is_emergency_response_sla"
            ],
        }
        row["prepared_record_hash_sha256"] = stable_hash(
            SCHEMA_VERSION,
            "prepared_district_operation",
            code,
            row["district_process_hash_sha256"],
            canonical_json(row["candidate_agency_ids"]),
        )
        district_rows.append(row)

    mission_rows = []
    for mission in missions:
        target_agencies = (
            district_agencies
            if mission.get("agency_selector") == "bma-district-*"
            else [agency_by_id[mission["agency_id"]]]
        )
        for agency in target_agencies:
            row = {
                "agency_id": agency["agency_id"],
                "agency_name_th": clean_text(agency["agency_name_th"]),
                "agency_category": agency["agency_category"],
                "district_code": agency.get("district_code"),
                "district_name_th": clean_text(
                    agency.get("district_name_th")
                ),
                "mission_scope": (
                    "common_bma_district_mission"
                    if mission.get("agency_selector")
                    else "named_agency_mission"
                ),
                "mission_items_th": [
                    clean_text(item)
                    for item in mission["mission_items_th"]
                ],
                "mission_item_count": len(mission["mission_items_th"]),
                "source_document_id": mission["source_document_id"],
                "source_pdf_pages": mission["source_pdf_pages"],
                "mission_duty_hash_sha256": mission[
                    "mission_duty_hash_sha256"
                ],
                "verification_status": mission["verification_status"],
                "is_official_legal_assignment": False,
                "requires_human_approval": True,
            }
            row["prepared_record_hash_sha256"] = stable_hash(
                SCHEMA_VERSION,
                "prepared_agency_mission",
                row["agency_id"],
                row["mission_duty_hash_sha256"],
            )
            mission_rows.append(row)

    issue_rows = []
    for source in unresolved + conflicts:
        row = {
            "quality_issue_hash_sha256": source["review_hash_sha256"],
            "issue_type": source["review_type"],
            "severity": "high",
            "entity_type": source["entity_type"],
            "entity_id": source["entity_id"],
            "entity_name_th": clean_text(source.get("entity_name_th")),
            "source_layer": source["source_layer"],
            "source_path": source["source_path"],
            "spatial_hash_geohash7": source["spatial_hash_geohash7"],
            "district_code": source.get(
                "district_code",
                source.get("selected_district_code"),
            ),
            "district_name_th": clean_text(
                source.get(
                    "district_name_th",
                    source.get("selected_district_name_th"),
                )
            ),
            "source_owner_value": clean_text(
                source.get("source_owner_value")
            ),
            "source_district_value": clean_text(
                source.get("source_district_value")
            ),
            "polygon_district_code": source.get(
                "polygon_district_code"
            ),
            "polygon_district_name_th": clean_text(
                source.get("polygon_district_name_th")
            ),
            "review_status": source["review_status"],
            "requires_manual_review": source[
                "requires_manual_review"
            ],
            "is_placeholder": source["is_placeholder"],
        }
        issue_rows.append(row)
    issue_rows.sort(
        key=lambda row: (
            row["issue_type"],
            row["district_code"] or "",
            row["entity_id"],
        )
    )

    checks = {
        "district_count_is_50": len(district_rows) == 50,
        "district_codes_unique": len(district_rows)
        == len({row["district_code"] for row in district_rows}),
        "district_processes_have_six_stages": all(
            row["process_stage_count"] == 6 for row in district_rows
        ),
        "agency_mission_count_is_60": len(mission_rows) == 60,
        "agency_missions_have_source": all(
            row["mission_duty_hash_sha256"]
            and row["source_document_id"]
            for row in mission_rows
        ),
        "quality_issue_count_is_418": len(issue_rows) == 418,
        "quality_issue_hashes_unique": len(issue_rows)
        == len(
            {row["quality_issue_hash_sha256"] for row in issue_rows}
        ),
        "no_placeholder_quality_issues": all(
            row["is_placeholder"] is False for row in issue_rows
        ),
        "no_verified_claims_created": all(
            row["is_official_legal_assignment"] is False
            for row in mission_rows
        ),
    }
    report = {
        "metadata": {
            "schema_version": SCHEMA_VERSION,
            "generated_at": utc_now(),
            "scope": "Responsibility analytical data preparation",
        },
        "counts": {
            "district_operations": len(district_rows),
            "agency_missions": len(mission_rows),
            "quality_issues": len(issue_rows),
        },
        "issue_type_counts": dict(
            sorted(Counter(row["issue_type"] for row in issue_rows).items())
        ),
        "checks": checks,
        "passed": all(checks.values()),
        "preparation_actions": [
            "Trimmed and collapsed whitespace in display text.",
            "Expanded the common district mission to 50 explicit agencies.",
            "Joined district process, agency profile, and service areas.",
            "Unified owner and spatial conflicts into one issue contract.",
            "Preserved source hashes and review status without promotion.",
        ],
    }
    write_jsonl(
        PREPARED_DIR / "district_flood_operations.jsonl",
        district_rows,
    )
    write_jsonl(
        PREPARED_DIR / "agency_flood_missions.jsonl",
        mission_rows,
    )
    write_jsonl(
        PREPARED_DIR / "data_quality_issues.jsonl",
        issue_rows,
    )
    write_json(PREPARED_DIR / "preparation_report.json", report)
    if not report["passed"]:
        raise RuntimeError("Responsibility data preparation failed")
    return {
        "districts": district_rows,
        "missions": mission_rows,
        "issues": issue_rows,
        "report": report,
    }


def normalize_datasets(prepared: dict[str, Any]) -> dict[str, Any]:
    candidate_dir = RESPONSIBILITY_DIR / "candidate"
    evidence_dir = RESPONSIBILITY_DIR / "evidence"
    agency_master = read_json(candidate_dir / "agency_master.json")[
        "agencies"
    ]
    incident_types = read_json(
        candidate_dir / "incident_type_registry.json"
    )["incident_types"]
    sources = read_jsonl(
        evidence_dir / "data_source_registry_hash_index.jsonl"
    )
    responsibility = read_jsonl(
        candidate_dir
        / "district_agency_responsibility_hash_index.jsonl"
    )

    dim_district = [
        {
            "district_key": row["district_code"],
            "district_code": row["district_code"],
            "district_name_th": row["district_name_th"],
            "district_agency_id": row["district_agency_id"],
            "requires_district_confirmation": row[
                "requires_district_confirmation"
            ],
            "district_specific_sop_verified": row[
                "district_specific_sop_verified"
            ],
        }
        for row in prepared["districts"]
    ]
    dim_agency = [
        {
            "agency_key": row["agency_id"],
            "agency_id": row["agency_id"],
            "agency_name_th": clean_text(row["agency_name_th"]),
            "agency_category": row["agency_category"],
            "response_tier": row["response_tier"],
            "parent_agency_id": row.get("parent_agency_id"),
            "district_code": row.get("district_code"),
            "operational_function": row.get("operational_function"),
            "legal_verification_status": row[
                "legal_verification_status"
            ],
        }
        for row in sorted(
            agency_master,
            key=lambda row: row["agency_id"],
        )
    ]
    dim_incident = [
        {
            "incident_type_key": row["incident_type_code"],
            "incident_type_code": row["incident_type_code"],
            "incident_type_name_th": clean_text(
                row["incident_type_name_th"]
            ),
            "candidate_lookup_strategy": row[
                "candidate_lookup_strategy"
            ],
            "routing_status": row["routing_status"],
            "is_official_legal_assignment": row[
                "is_official_legal_assignment"
            ],
        }
        for row in incident_types
    ]
    dim_source = [
        {
            "source_key": row["data_source_hash_sha256"],
            "source_id": row["source_id"],
            "source_kind": row["source_kind"],
            "source_category": row["source_category"],
            "publisher_th": row["publisher_th"],
            "source_url": row["source_url"],
            "source_url_precision": row["source_url_precision"],
            "provenance_status": row["provenance_status"],
            "local_path": row.get("local_path"),
            "local_file_sha256": row.get("local_file_sha256"),
            "upstream_document_sha256": row.get(
                "upstream_document_sha256"
            ),
            "used_by_hash_datasets": row["used_by_hash_datasets"],
        }
        for row in sources
    ]

    fact_responsibility = [
        {
            "responsibility_fact_key": row[
                "district_agency_responsibility_hash_sha256"
            ],
            "district_key": row["district_code"],
            "agency_key": row["agency_id"],
            "incident_type_key": row.get("incident_type_code"),
            "responsibility_scope": row["responsibility_scope"],
            "responsibility_role": row["responsibility_role"],
            "source_record_count": row["source_record_count"],
            "source_hashes_sha256": row["source_hashes_sha256"],
            "legal_basis_reference_ids": row[
                "legal_basis_reference_ids"
            ],
            "verification_status": row["verification_status"],
            "is_official_legal_assignment": row[
                "is_official_legal_assignment"
            ],
            "requires_human_approval": row["requires_human_approval"],
        }
        for row in responsibility
    ]

    fact_process_stage = []
    for district in prepared["districts"]:
        for stage in district["process_stages"]:
            row = {
                "process_stage_fact_key": stable_hash(
                    SCHEMA_VERSION,
                    "process_stage_fact",
                    district["district_code"],
                    stage["stage_code"],
                    district["district_process_hash_sha256"],
                ),
                "district_key": district["district_code"],
                "district_agency_key": district["district_agency_id"],
                "district_process_hash_sha256": district[
                    "district_process_hash_sha256"
                ],
                "stage_sequence": stage["sequence"],
                "stage_code": stage["stage_code"],
                "action_th": clean_text(stage["action_th"]),
                "owner_role_th": clean_text(stage["owner_role_th"]),
                "manual_document_duration_days": stage.get(
                    "manual_document_duration_days"
                ),
                "timing_is_emergency_response_sla": district[
                    "timing_is_emergency_response_sla"
                ],
                "verification_status": district[
                    "verification_status"
                ],
            }
            fact_process_stage.append(row)

    fact_quality_issue = [
        {
            "quality_issue_fact_key": row[
                "quality_issue_hash_sha256"
            ],
            "district_key": row["district_code"],
            "issue_type": row["issue_type"],
            "severity": row["severity"],
            "entity_type": row["entity_type"],
            "entity_id": row["entity_id"],
            "source_layer": row["source_layer"],
            "source_path": row["source_path"],
            "spatial_hash_geohash7": row[
                "spatial_hash_geohash7"
            ],
            "polygon_district_code": row[
                "polygon_district_code"
            ],
            "review_status": row["review_status"],
            "requires_manual_review": row[
                "requires_manual_review"
            ],
        }
        for row in prepared["issues"]
    ]

    district_keys = {row["district_key"] for row in dim_district}
    agency_keys = {row["agency_key"] for row in dim_agency}
    checks = {
        "dimension_counts_expected": (
            len(dim_district) == 50
            and len(dim_agency) == 70
            and len(dim_incident) == 10
            and len(dim_source) == 35
        ),
        "responsibility_fact_count_is_872": (
            len(fact_responsibility) == 872
        ),
        "process_stage_fact_count_is_300": (
            len(fact_process_stage) == 300
        ),
        "quality_issue_fact_count_is_418": (
            len(fact_quality_issue) == 418
        ),
        "responsibility_district_keys_valid": all(
            row["district_key"] in district_keys
            for row in fact_responsibility
        ),
        "responsibility_agency_keys_valid": all(
            row["agency_key"] in agency_keys
            for row in fact_responsibility
        ),
        "process_stage_keys_unique": len(fact_process_stage)
        == len(
            {
                row["process_stage_fact_key"]
                for row in fact_process_stage
            }
        ),
        "quality_issue_keys_unique": len(fact_quality_issue)
        == len(
            {
                row["quality_issue_fact_key"]
                for row in fact_quality_issue
            }
        ),
        "verified_fact_count_is_zero": not any(
            row["is_official_legal_assignment"]
            for row in fact_responsibility
        ),
    }

    datasets = {
        "dim_district.csv": dim_district,
        "dim_agency.csv": dim_agency,
        "dim_incident_type.csv": dim_incident,
        "dim_source.csv": dim_source,
        "fact_district_agency_responsibility.csv": fact_responsibility,
        "fact_district_process_stage.csv": fact_process_stage,
        "fact_data_quality_issue.csv": fact_quality_issue,
    }
    for file_name, rows in datasets.items():
        write_csv(NORMALIZED_DIR / file_name, rows)

    data_contract = {
        "metadata": {
            "schema_version": SCHEMA_VERSION,
            "model": "star_like_analytical_model",
        },
        "prepared": {
            "district_flood_operations.jsonl": {
                "grain": "one Bangkok district office",
                "primary_key": "district_code",
                "record_count": 50,
            },
            "agency_flood_missions.jsonl": {
                "grain": "one agency and source mission",
                "primary_key": "prepared_record_hash_sha256",
                "record_count": 60,
            },
            "data_quality_issues.jsonl": {
                "grain": "one unresolved source issue",
                "primary_key": "quality_issue_hash_sha256",
                "record_count": 418,
            },
        },
        "normalized": {
            "dim_district.csv": {
                "grain": "one Bangkok district",
                "primary_key": "district_key",
            },
            "dim_agency.csv": {
                "grain": "one agency or operational unit",
                "primary_key": "agency_key",
                "foreign_keys": {
                    "district_code": "dim_district.district_key"
                },
            },
            "dim_incident_type.csv": {
                "grain": "one normalized flood incident type",
                "primary_key": "incident_type_key",
            },
            "dim_source.csv": {
                "grain": "one source-lineage record",
                "primary_key": "source_key",
            },
            "fact_district_agency_responsibility.csv": {
                "grain": (
                    "district + agency + responsibility scope + role + "
                    "optional incident type"
                ),
                "primary_key": "responsibility_fact_key",
                "foreign_keys": {
                    "district_key": "dim_district.district_key",
                    "agency_key": "dim_agency.agency_key",
                    "incident_type_key": (
                        "dim_incident_type.incident_type_key"
                    ),
                },
            },
            "fact_district_process_stage.csv": {
                "grain": "one process stage per Bangkok district",
                "primary_key": "process_stage_fact_key",
                "foreign_keys": {
                    "district_key": "dim_district.district_key",
                    "district_agency_key": "dim_agency.agency_key",
                },
            },
            "fact_data_quality_issue.csv": {
                "grain": "one unresolved source issue",
                "primary_key": "quality_issue_fact_key",
                "foreign_keys": {
                    "district_key": "dim_district.district_key"
                },
            },
        },
        "null_policy": {
            "incident_type_key": (
                "Null is allowed when a responsibility row is not "
                "incident-specific."
            ),
            "district_key": (
                "Quality issues may be null only when no district can be "
                "resolved; current prepared issues all have a selected "
                "district."
            ),
        },
        "status_policy": (
            "Analytical transforms preserve source verification status and "
            "never create verified legal or dispatch records."
        ),
    }
    write_json(NORMALIZED_DIR / "data_contract.json", data_contract)

    manifest = {
        "metadata": {
            "schema_version": SCHEMA_VERSION,
            "generated_at": utc_now(),
            "model": "star_like_analytical_model",
            "scope": "Bangkok flood responsibility analysis",
            "operational_use": False,
        },
        "counts": {
            file_name: len(rows)
            for file_name, rows in datasets.items()
        },
        "checks": checks,
        "passed": all(checks.values()),
        "join_keys": {
            "district": "district_key",
            "agency": "agency_key",
            "incident_type": "incident_type_key",
            "source": "source_key",
        },
        "status_rule": (
            "Candidate and pending-review records remain unverified. "
            "Normalization never promotes legal or dispatch status."
        ),
    }
    write_json(NORMALIZED_DIR / "normalization_manifest.json", manifest)
    if not manifest["passed"]:
        raise RuntimeError("Responsibility normalization failed")
    return {
        "dimensions": {
            "district": dim_district,
            "agency": dim_agency,
            "incident": dim_incident,
            "source": dim_source,
        },
        "facts": {
            "responsibility": fact_responsibility,
            "process_stage": fact_process_stage,
            "quality_issue": fact_quality_issue,
        },
        "manifest": manifest,
    }


def build_analysis_payload(
    prepared: dict[str, Any],
    normalized: dict[str, Any],
) -> dict[str, Any]:
    responsibility = normalized["facts"]["responsibility"]
    source_rows = normalized["dimensions"]["source"]
    coverage: dict[str, set[str]] = defaultdict(set)
    source_records: Counter[str] = Counter()
    for row in responsibility:
        coverage[row["agency_key"]].add(row["district_key"])
        source_records[row["agency_key"]] += row["source_record_count"]
    agency_by_id = {
        row["agency_key"]: row
        for row in normalized["dimensions"]["agency"]
    }
    top_agencies = [
        {
            "agency_id": agency_id,
            "agency_name_th": agency_by_id[agency_id][
                "agency_name_th"
            ],
            "district_coverage_count": len(districts),
            "source_record_count": source_records[agency_id],
        }
        for agency_id, districts in sorted(
            coverage.items(),
            key=lambda item: (
                -len(item[1]),
                -source_records[item[0]],
                item[0],
            ),
        )[:12]
    ]
    district_metrics = [
        {
            "district_code": row["district_code"],
            "district_name_th": row["district_name_th"],
            "candidate_agency_count": row["candidate_agency_count"],
            "source_record_count": row["source_record_count"],
            "process_stage_count": row["process_stage_count"],
            "district_specific_sop_verified": row[
                "district_specific_sop_verified"
            ],
        }
        for row in prepared["districts"]
    ]
    issue_counts = Counter(
        row["issue_type"] for row in prepared["issues"]
    )
    provenance_counts = Counter(
        row["provenance_status"] for row in source_rows
    )
    verification_counts = Counter(
        row["verification_status"] for row in responsibility
    )
    process_stages = []
    for sequence in range(1, 7):
        rows = [
            row
            for row in normalized["facts"]["process_stage"]
            if row["stage_sequence"] == sequence
        ]
        process_stages.append(
            {
                "sequence": sequence,
                "stage_code": rows[0]["stage_code"],
                "action_th": rows[0]["action_th"],
                "district_count": len(rows),
                "manual_document_duration_days": rows[0][
                    "manual_document_duration_days"
                ],
                "is_emergency_sla": False,
            }
        )

    payload = {
        "metadata": {
            "schema_version": SCHEMA_VERSION,
            "generated_at": utc_now(),
            "scope": "Static analytical visualization backing data",
            "not_for_automatic_dispatch": True,
        },
        "kpis": {
            "district_count": len(prepared["districts"]),
            "agency_count": len(normalized["dimensions"]["agency"]),
            "mission_assignment_count": len(prepared["missions"]),
            "responsibility_fact_count": len(responsibility),
            "quality_issue_count": len(prepared["issues"]),
            "source_count": len(source_rows),
            "verified_legal_assignment_count": 0,
        },
        "district_metrics": district_metrics,
        "quality_issue_counts": dict(sorted(issue_counts.items())),
        "source_provenance_counts": dict(
            sorted(provenance_counts.items())
        ),
        "responsibility_verification_counts": dict(
            sorted(verification_counts.items())
        ),
        "top_agency_coverage": top_agencies,
        "process_stages": process_stages,
    }
    payload["source_fingerprint_sha256"] = stable_hash(
        canonical_json(
            {
                "district_metrics": district_metrics,
                "quality_issue_counts": payload[
                    "quality_issue_counts"
                ],
                "source_provenance_counts": payload[
                    "source_provenance_counts"
                ],
                "top_agency_coverage": top_agencies,
                "process_stages": process_stages,
            }
        )
    )
    write_json(VISUALIZATION_DIR / "analysis_payload.json", payload)
    return payload


def decode_geohash_center(value: str) -> tuple[float, float]:
    lat = [-90.0, 90.0]
    lon = [-180.0, 180.0]
    even = True
    for character in value:
        number = GEOHASH_BASE32.index(character)
        for mask in (16, 8, 4, 2, 1):
            interval = lon if even else lat
            midpoint = sum(interval) / 2
            if number & mask:
                interval[0] = midpoint
            else:
                interval[1] = midpoint
            even = not even
    return (sum(lat) / 2, sum(lon) / 2)


def geometry_rings(geometry: dict[str, Any]) -> list[list[list[float]]]:
    if geometry["type"] == "Polygon":
        return geometry["coordinates"]
    if geometry["type"] == "MultiPolygon":
        return [
            ring
            for polygon in geometry["coordinates"]
            for ring in polygon
        ]
    return []


def render_visualizations(payload: dict[str, Any]) -> list[Path]:
    try:
        from PIL import Image, ImageDraw, ImageFont, PngImagePlugin
    except ImportError as exc:
        raise RuntimeError(
            "Pillow is required for static PNG rendering. Use the bundled "
            "workspace Python runtime."
        ) from exc

    regular_font_path = Path(
        "/System/Library/Fonts/Supplemental/Tahoma.ttf"
    )
    bold_font_path = Path(
        "/System/Library/Fonts/Supplemental/Tahoma Bold.ttf"
    )
    if not regular_font_path.exists():
        regular_font_path = Path(
            "/System/Library/Fonts/Supplemental/Arial Unicode.ttf"
        )
        bold_font_path = regular_font_path

    def font(size: int, bold: bool = False) -> Any:
        path = bold_font_path if bold else regular_font_path
        return ImageFont.truetype(str(path), size=size)

    title_font = font(34, True)
    heading_font = font(23, True)
    body_font = font(18)
    small_font = font(14)
    tiny_font = font(11)
    colors = {
        "ink": "#17222d",
        "muted": "#61707d",
        "line": "#d7dee3",
        "green": "#2a9d6f",
        "blue": "#2878b5",
        "amber": "#e9a23b",
        "red": "#d9534f",
        "purple": "#7656a6",
        "teal": "#008c95",
        "gray": "#7f8c8d",
        "bg": "#f5f7f8",
        "white": "#ffffff",
    }

    geojson = read_json(GEOJSON_DIR / "districts.geojson")
    metrics = {
        row["district_code"]: row
        for row in payload["district_metrics"]
    }
    all_points = [
        point
        for feature in geojson["features"]
        for ring in geometry_rings(feature["geometry"])
        for point in ring
    ]
    min_lon = min(point[0] for point in all_points)
    max_lon = max(point[0] for point in all_points)
    min_lat = min(point[1] for point in all_points)
    max_lat = max(point[1] for point in all_points)

    map_width, map_height = 1600, 1100
    image = Image.new("RGB", (map_width, map_height), colors["bg"])
    draw = ImageDraw.Draw(image)
    draw.text(
        (48, 34),
        "Bangkok Flood Responsibility: Operational Coverage",
        fill=colors["ink"],
        font=title_font,
    )
    draw.text(
        (48, 82),
        "Fill = candidate agencies per district | Red = spatial conflict | Black = unresolved owner",
        fill=colors["muted"],
        font=body_font,
    )
    plot = (48, 130, 1240, 1040)
    px0, py0, px1, py1 = plot

    def project(lon: float, lat: float) -> tuple[int, int]:
        x = px0 + (lon - min_lon) / (max_lon - min_lon) * (px1 - px0)
        y = py1 - (lat - min_lat) / (max_lat - min_lat) * (py1 - py0)
        return int(x), int(y)

    def fill_for(value: int) -> str:
        if value <= 4:
            return "#8fd3b4"
        if value == 5:
            return "#77bde0"
        if value == 6:
            return "#f1c66f"
        return "#e88973"

    for feature in geojson["features"]:
        properties = feature["properties"]
        code = str(
            properties.get("DISTRICT_I")
            or properties.get("district_code")
        )
        metric = metrics.get(code)
        fill = fill_for(metric["candidate_agency_count"] if metric else 0)
        rings = geometry_rings(feature["geometry"])
        for ring in rings:
            polygon = [project(point[0], point[1]) for point in ring]
            if len(polygon) >= 3:
                draw.polygon(
                    polygon,
                    fill=fill,
                    outline=colors["white"],
                    width=2,
                )
        if rings and metric:
            largest = max(rings, key=len)
            center_lon = sum(point[0] for point in largest) / len(largest)
            center_lat = sum(point[1] for point in largest) / len(largest)
            center = project(center_lon, center_lat)
            label = f"{code[-2:]}:{metric['candidate_agency_count']}"
            draw.text(
                center,
                label,
                fill=colors["ink"],
                font=tiny_font,
                anchor="mm",
            )

    issue_rows = read_jsonl(
        PREPARED_DIR / "data_quality_issues.jsonl"
    )
    for issue in issue_rows:
        lat, lon = decode_geohash_center(
            issue["spatial_hash_geohash7"]
        )
        x, y = project(lon, lat)
        if issue["issue_type"] == "district_spatial_conflict":
            draw.ellipse(
                (x - 3, y - 3, x + 3, y + 3),
                fill=colors["red"],
            )
        else:
            draw.line(
                (x - 2, y - 2, x + 2, y + 2),
                fill=colors["ink"],
                width=1,
            )
            draw.line(
                (x - 2, y + 2, x + 2, y - 2),
                fill=colors["ink"],
                width=1,
            )

    legend_x = 1290
    draw.text(
        (legend_x, 150),
        "Candidate agencies",
        fill=colors["ink"],
        font=heading_font,
    )
    for index, (label, value) in enumerate(
        (("4 or fewer", 4), ("5", 5), ("6", 6), ("7 or more", 7))
    ):
        y = 205 + index * 48
        draw.rectangle(
            (legend_x, y, legend_x + 34, y + 28),
            fill=fill_for(value),
        )
        draw.text(
            (legend_x + 48, y + 3),
            label,
            fill=colors["ink"],
            font=body_font,
        )
    draw.text(
        (legend_x, 430),
        "Important",
        fill=colors["red"],
        font=heading_font,
    )
    warning_lines = [
        "Coverage means routing",
        "candidates, not verified",
        "legal responsibility.",
        "",
        "All 50 district SOP",
        "records still require",
        "district confirmation.",
    ]
    for index, line in enumerate(warning_lines):
        draw.text(
            (legend_x, 475 + index * 28),
            line,
            fill=colors["ink"],
            font=body_font,
        )
    map_path = VISUALIZATION_DIR / "district_operational_coverage_map.png"
    png_info = PngImagePlugin.PngInfo()
    png_info.add_text(
        "Source-Fingerprint",
        payload["source_fingerprint_sha256"],
    )
    image.save(map_path, pnginfo=png_info)

    dashboard = Image.new("RGB", (1800, 1250), colors["bg"])
    draw = ImageDraw.Draw(dashboard)
    draw.text(
        (52, 36),
        "Flood Responsibility Data Readiness",
        fill=colors["ink"],
        font=title_font,
    )
    draw.text(
        (52, 82),
        "Prepared and normalized analytical view; not an operational dispatch interface",
        fill=colors["muted"],
        font=body_font,
    )

    def card(box: tuple[int, int, int, int], title: str) -> None:
        draw.rounded_rectangle(
            box,
            radius=8,
            fill=colors["white"],
            outline=colors["line"],
            width=1,
        )
        draw.text(
            (box[0] + 22, box[1] + 18),
            title,
            fill=colors["ink"],
            font=heading_font,
        )

    kpis = [
        ("Districts", payload["kpis"]["district_count"], colors["green"]),
        ("Agencies", payload["kpis"]["agency_count"], colors["blue"]),
        (
            "Quality issues",
            payload["kpis"]["quality_issue_count"],
            colors["red"],
        ),
        ("Sources", payload["kpis"]["source_count"], colors["amber"]),
        (
            "Verified legal",
            payload["kpis"]["verified_legal_assignment_count"],
            colors["purple"],
        ),
    ]
    for index, (label, value, color) in enumerate(kpis):
        x = 52 + index * 342
        draw.rounded_rectangle(
            (x, 130, x + 314, 248),
            radius=8,
            fill=colors["white"],
            outline=colors["line"],
        )
        draw.text((x + 20, 148), label, fill=colors["muted"], font=body_font)
        draw.text((x + 20, 182), str(value), fill=color, font=font(38, True))

    issue_box = (52, 278, 610, 650)
    card(issue_box, "Unresolved data quality")
    issue_values = [
        (
            "Asset owner unresolved",
            payload["quality_issue_counts"].get(
                "unresolved_asset_owner", 0
            ),
            colors["amber"],
        ),
        (
            "District spatial conflict",
            payload["quality_issue_counts"].get(
                "district_spatial_conflict", 0
            ),
            colors["red"],
        ),
    ]
    max_issue = max(value for _, value, _ in issue_values)
    for index, (label, value, color) in enumerate(issue_values):
        y = 350 + index * 110
        draw.text((76, y), label, fill=colors["ink"], font=body_font)
        width = int(430 * value / max_issue)
        draw.rectangle((76, y + 36, 76 + width, y + 64), fill=color)
        draw.text(
            (520, y + 34),
            str(value),
            fill=colors["ink"],
            font=heading_font,
            anchor="ra",
        )

    source_box = (636, 278, 1174, 650)
    card(source_box, "Source provenance")
    source_groups = {
        "Acquired official evidence": 0,
        "Content hash captured": 0,
        "Legal copies pending review": 0,
        "Incomplete SEDGIS": 0,
        "Partial provenance": 0,
        "Web reference only": 0,
        "Blocked/no hash": 0,
    }
    for status, count in payload["source_provenance_counts"].items():
        if status.startswith("acquired"):
            source_groups["Acquired official evidence"] += count
        elif status.startswith("content_hash"):
            source_groups["Content hash captured"] += count
        elif status.startswith("official_copy"):
            source_groups["Legal copies pending review"] += count
        elif status.startswith("incomplete"):
            source_groups["Incomplete SEDGIS"] += count
        elif status.startswith("reference"):
            source_groups["Web reference only"] += count
        elif status.startswith("partial"):
            source_groups["Partial provenance"] += count
        else:
            source_groups["Blocked/no hash"] += count
    source_groups = {
        label: value
        for label, value in source_groups.items()
        if value
    }
    source_colors = [
        colors["green"],
        colors["red"],
        colors["teal"],
        colors["blue"],
        colors["amber"],
        colors["purple"],
        colors["gray"],
    ]
    total_sources = sum(source_groups.values())
    cursor = 76
    for (label, value), color in zip(
        source_groups.items(),
        source_colors,
    ):
        width = int(480 * value / total_sources)
        draw.rectangle(
            (660 + cursor - 76, 350, 660 + cursor - 76 + width, 390),
            fill=color,
        )
        cursor += width
    for index, ((label, value), color) in enumerate(
        zip(source_groups.items(), source_colors)
    ):
        y = 410 + index * 32
        draw.rectangle((660, y + 4, 676, y + 20), fill=color)
        draw.text((688, y), label, fill=colors["ink"], font=small_font)
        draw.text(
            (1138, y),
            str(value),
            fill=colors["ink"],
            font=small_font,
            anchor="ra",
        )

    coverage_box = (1200, 278, 1748, 650)
    card(coverage_box, "Top agency district coverage")
    coverage_rows = payload["top_agency_coverage"][:7]
    max_coverage = max(
        row["district_coverage_count"] for row in coverage_rows
    )
    for index, row in enumerate(coverage_rows):
        y = 346 + index * 42
        label = row["agency_id"].replace("bma-", "")[:28]
        draw.text((1224, y), label, fill=colors["ink"], font=small_font)
        width = int(
            180 * row["district_coverage_count"] / max_coverage
        )
        draw.rectangle(
            (1495, y + 3, 1495 + width, y + 22),
            fill=colors["blue"],
        )
        draw.text(
            (1722, y),
            str(row["district_coverage_count"]),
            fill=colors["ink"],
            font=small_font,
            anchor="ra",
        )

    process_box = (52, 680, 1748, 1168)
    card(process_box, "Common district process evidence")
    stages = payload["process_stages"]
    stage_colors = [
        colors["blue"],
        colors["purple"],
        colors["amber"],
        colors["green"],
        colors["red"],
        colors["ink"],
    ]
    x_positions = [90 + index * 272 for index in range(6)]
    for index, (stage, color) in enumerate(zip(stages, stage_colors)):
        x = x_positions[index]
        draw.ellipse((x, 775, x + 54, 829), fill=color)
        draw.text(
            (x + 27, 802),
            str(stage["sequence"]),
            fill=colors["white"],
            font=heading_font,
            anchor="mm",
        )
        if index < 5:
            draw.line(
                (x + 60, 802, x + 250, 802),
                fill=colors["line"],
                width=4,
            )
        draw.text(
            (x, 850),
            stage["stage_code"].replace("_", " "),
            fill=colors["ink"],
            font=small_font,
        )
        draw.text(
            (x, 885),
            f"{stage['district_count']} districts",
            fill=colors["muted"],
            font=small_font,
        )
        duration = stage["manual_document_duration_days"]
        if duration is not None:
            draw.text(
                (x, 917),
                f"Manual: {duration} days",
                fill=colors["red"],
                font=small_font,
            )
    draw.text(
        (90, 1035),
        "The 2/2/3-day values are document workflow durations, not emergency response SLA.",
        fill=colors["red"],
        font=body_font,
    )
    draw.text(
        (90, 1080),
        "All district processes remain pending district confirmation; verified legal assignments = 0.",
        fill=colors["ink"],
        font=body_font,
    )
    dashboard_path = (
        VISUALIZATION_DIR / "responsibility_data_readiness_dashboard.png"
    )
    png_info = PngImagePlugin.PngInfo()
    png_info.add_text(
        "Source-Fingerprint",
        payload["source_fingerprint_sha256"],
    )
    dashboard.save(dashboard_path, pnginfo=png_info)
    return [map_path, dashboard_path]


def build(render_images: bool = True) -> dict[str, Any]:
    prepared = prepare_datasets()
    normalized = normalize_datasets(prepared)
    payload = build_analysis_payload(prepared, normalized)
    image_paths = render_visualizations(payload) if render_images else []
    manifest = {
        "metadata": {
            "schema_version": SCHEMA_VERSION,
            "generated_at": utc_now(),
            "source_fingerprint_sha256": payload[
                "source_fingerprint_sha256"
            ],
            "frontend_artifact": False,
            "hosted": False,
        },
        "prepared_counts": prepared["report"]["counts"],
        "normalized_counts": normalized["manifest"]["counts"],
        "visualizations": [
            {
                "path": path.relative_to(RESPONSIBILITY_DIR).as_posix(),
                "sha256": file_sha256(path),
                "purpose": (
                    "district_spatial_quality_and_coverage"
                    if "coverage_map" in path.name
                    else "responsibility_readiness_and_data_quality"
                ),
            }
            for path in image_paths
        ],
        "notice": (
            "Static analytical artifacts only. They are not frontend code "
            "and must not be used for automatic legal assignment."
        ),
    }
    write_json(VISUALIZATION_DIR / "visualization_manifest.json", manifest)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--no-images",
        action="store_true",
        help="Build prepared/normalized data and payload without PNG files.",
    )
    args = parser.parse_args()
    result = build(render_images=not args.no_images)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
