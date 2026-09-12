from __future__ import annotations

import importlib.util
import hashlib
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_responsibility_index.py"
SPEC = importlib.util.spec_from_file_location("responsibility_index", SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Cannot load {SCRIPT}")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ResponsibilityIndexTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.quality = MODULE.build()
        cls.assignments = [
            json.loads(line)
            for line in (
                ROOT
                / "data"
                / "responsibility"
                / "candidate"
                / "all_assignments.jsonl"
            ).read_text(encoding="utf-8").splitlines()
        ]

    def test_quality_checks_pass(self) -> None:
        self.assertTrue(self.quality["passed"])
        self.assertTrue(all(self.quality["checks"].values()))

    def test_all_assignments_are_unverified_candidates(self) -> None:
        self.assertTrue(self.assignments)
        self.assertTrue(
            all(
                row["verification_status"] == "candidate_unverified"
                and row["is_official_legal_assignment"] is False
                and row["requires_human_approval"] is True
                for row in self.assignments
            )
        )

    def test_each_flood_signal_has_one_primary_candidate(self) -> None:
        primary_counts: dict[str, int] = {}
        for row in self.assignments:
            if row["responsibility_role"] == "primary_response_candidate":
                primary_counts[row["entity_id"]] = (
                    primary_counts.get(row["entity_id"], 0) + 1
                )
        self.assertEqual(len(primary_counts), 725)
        self.assertTrue(all(count == 1 for count in primary_counts.values()))

    def test_coordinate_lookup_uses_bangkok_district_polygon(self) -> None:
        result = MODULE.query(13.666764, 100.42846)
        agency_ids = {
            row["agency_id"] for row in result["agency_candidates"]
        }
        self.assertIn("bma-district-1050", agency_ids)
        self.assertNotIn("bma-district-1021", agency_ids)
        self.assertIn("road_flood_sensor:FL.BBN.06", result["signal_refs"])
        self.assertEqual(
            len(result["official_reference_service_area_candidates"]),
            2,
        )
        incident_result = MODULE.query(
            13.666764,
            100.42846,
            "road_flooding_main_system",
        )
        self.assertEqual(
            len(
                incident_result[
                    "agency_incident_capability_candidates"
                ]
            ),
            1,
        )
        self.assertEqual(
            incident_result["routing_status"],
            "candidate_requires_review",
        )

    def test_candidate_indexes_are_separated_by_role(self) -> None:
        candidate_dir = ROOT / "data" / "responsibility" / "candidate"
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
        split_rows = []
        for file_name, expected_roles in role_files.items():
            rows = [
                json.loads(line)
                for line in (candidate_dir / file_name)
                .read_text(encoding="utf-8")
                .splitlines()
            ]
            self.assertTrue(
                all(
                    row["responsibility_role"] in expected_roles
                    for row in rows
                )
            )
            split_rows.extend(rows)
        self.assertEqual(len(split_rows), len(self.assignments))

    def test_verified_index_is_empty_without_reviewed_inputs(self) -> None:
        responsibility_dir = ROOT / "data" / "responsibility"
        verified_rows = (
            responsibility_dir
            / "verified"
            / "legal_responsibility_hash_index.jsonl"
        ).read_text(encoding="utf-8").splitlines()
        quality = json.loads(
            (
                responsibility_dir / "verified" / "quality_report.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(verified_rows, [])
        self.assertEqual(
            quality["metadata"]["status"],
            "awaiting_verified_legal_inputs",
        )
        self.assertTrue(quality["passed"])
        dispatch_rows = (
            responsibility_dir
            / "verified"
            / "dispatch_authorization_hash_index.jsonl"
        ).read_text(encoding="utf-8").splitlines()
        self.assertEqual(dispatch_rows, [])
        self.assertEqual(
            quality["metadata"]["dispatch_authorization_count"],
            0,
        )

    def test_legacy_mixed_outputs_are_removed(self) -> None:
        responsibility_dir = ROOT / "data" / "responsibility"
        self.assertFalse(
            (responsibility_dir / "responsibility_hash_index.jsonl").exists()
        )
        self.assertTrue((responsibility_dir / "manifest.json").exists())

    def test_invalid_legal_input_fails_closed(self) -> None:
        original_input_dir = MODULE.INPUT_DIR
        original_verified_dir = MODULE.VERIFIED_DIR
        try:
            with tempfile.TemporaryDirectory() as directory:
                temporary = Path(directory)
                MODULE.INPUT_DIR = temporary / "inputs"
                MODULE.VERIFIED_DIR = temporary / "verified"
                MODULE.write_csv(
                    MODULE.INPUT_DIR / "legal_basis.csv",
                    [
                        {
                            "legal_basis_id": "invalid-document",
                            "document_title": "Invalid test document",
                            "issuing_authority": "Test",
                            "document_type": "order",
                            "section_or_page": "1",
                            "source_url": "https://example.invalid/doc.pdf",
                            "document_sha256": "not-a-sha256",
                            "verification_status": "verified",
                            "verified_by": "Test reviewer",
                            "verified_at": "2026-06-28T00:00:00Z",
                        }
                    ],
                    MODULE.LEGAL_BASIS_FIELDS,
                )
                MODULE.write_csv(
                    MODULE.INPUT_DIR
                    / "verified_responsibility_assignments.csv",
                    [],
                    MODULE.VERIFIED_ASSIGNMENT_FIELDS,
                )
                with self.assertRaisesRegex(
                    RuntimeError, "validation failed"
                ):
                    MODULE.build_verified_index({"bma"})
                output = (
                    MODULE.VERIFIED_DIR
                    / "legal_responsibility_hash_index.jsonl"
                )
                self.assertEqual(output.read_text(encoding="utf-8"), "")
        finally:
            MODULE.INPUT_DIR = original_input_dir
            MODULE.VERIFIED_DIR = original_verified_dir

    def test_canal_entity_ids_do_not_collapse_source_features(self) -> None:
        canal_ids = {
            row["entity_id"]
            for row in self.assignments
            if row["source_layer"] == "canals"
            and row["responsibility_role"]
            == "geographic_jurisdiction_candidate"
        }
        self.assertEqual(len(canal_ids), 2000)

    def test_official_service_area_candidates_cover_all_districts(self) -> None:
        candidate_dir = ROOT / "data" / "responsibility" / "candidate"
        rows = [
            json.loads(line)
            for line in (
                candidate_dir / "agency_service_area_hash_index.jsonl"
            ).read_text(encoding="utf-8").splitlines()
        ]
        by_district = json.loads(
            (
                candidate_dir / "agency_service_areas_by_district.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(len(rows), 100)
        self.assertEqual(len(by_district["districts"]), 50)
        self.assertTrue(
            all(
                len(values) == 2
                for values in by_district["districts"].values()
            )
        )

    def test_additional_candidate_hash_indexes_are_unique(self) -> None:
        candidate_dir = ROOT / "data" / "responsibility" / "candidate"
        capability_rows = [
            json.loads(line)
            for line in (
                candidate_dir
                / "agency_incident_capability_hash_index.jsonl"
            ).read_text(encoding="utf-8").splitlines()
        ]
        legal_rows = [
            json.loads(line)
            for line in (
                candidate_dir / "legal_reference_hash_index.jsonl"
            ).read_text(encoding="utf-8").splitlines()
        ]
        self.assertEqual(len(capability_rows), 300)
        self.assertEqual(
            len(capability_rows),
            len(
                {
                    row["capability_hash_sha256"]
                    for row in capability_rows
                }
            ),
        )
        self.assertEqual(len(legal_rows), 8)
        self.assertEqual(
            len(legal_rows),
            len(
                {
                    row["legal_reference_hash_sha256"]
                    for row in legal_rows
                }
            ),
        )
        self.assertTrue(
            all(
                row["is_document_content_hash"] is False
                for row in legal_rows
            )
        )
        self.assertTrue(
            all(
                row["verification_status"]
                == "official_reference_unverified"
                and row["is_official_legal_assignment"] is False
                for row in capability_rows
            )
        )

    def test_district_agency_summary_contains_all_candidate_sources(
        self,
    ) -> None:
        responsibility_dir = ROOT / "data" / "responsibility"
        candidate_dir = responsibility_dir / "candidate"
        rows = [
            json.loads(line)
            for line in (
                candidate_dir
                / "district_agency_responsibility_hash_index.jsonl"
            ).read_text(encoding="utf-8").splitlines()
        ]
        profiles = json.loads(
            (
                candidate_dir / "responsible_agencies_by_district.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(len(profiles["districts"]), 50)
        self.assertTrue(
            all(
                district["candidate_agency_count"] > 0
                and district["district_agency_id"]
                for district in profiles["districts"]
            )
        )
        self.assertEqual(
            len(rows),
            len(
                {
                    row[
                        "district_agency_responsibility_hash_sha256"
                    ]
                    for row in rows
                }
            ),
        )
        counts = {
            scope: sum(
                row["source_record_count"]
                for row in rows
                if row["responsibility_scope"] == scope
            )
            for scope in (
                "entity_assignment",
                "service_area",
                "incident_capability",
            )
        }
        self.assertEqual(
            counts,
            {
                "entity_assignment": 8112,
                "service_area": 100,
                "incident_capability": 300,
            },
        )
        self.assertTrue(
            all(
                row["is_official_legal_assignment"] is False
                and row["requires_human_approval"] is True
                for row in rows
            )
        )

    def test_hash_index_catalog_covers_both_pr_commits(self) -> None:
        responsibility_dir = ROOT / "data" / "responsibility"
        catalog = json.loads(
            (responsibility_dir / "hash_index_catalog.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(
            catalog["totals"]["canonical_candidate_hash_count"],
            8520,
        )
        self.assertEqual(
            catalog["totals"]["manual_review_hash_count"],
            418,
        )
        self.assertEqual(
            catalog["totals"]["verified_hash_count"],
            0,
        )
        self.assertEqual(
            catalog["totals"]["official_evidence_hash_count"],
            25,
        )
        self.assertEqual(
            catalog["totals"]["district_process_candidate_hash_count"],
            50,
        )
        self.assertEqual(
            catalog["totals"]["provenance_source_hash_count"],
            35,
        )
        self.assertEqual(
            catalog["totals"]["acquisition_source_hash_count"],
            7,
        )
        self.assertEqual(
            catalog["totals"]["acquisition_gap_status_hash_count"],
            477,
        )
        self.assertEqual(
            catalog["totals"]["legal_authority_evidence_hash_count"],
            17,
        )
        self.assertEqual(
            catalog["totals"][
                "district_legal_authority_candidate_hash_count"
            ],
            50,
        )
        self.assertEqual(
            catalog["totals"]["legal_authority_review_hash_count"],
            17,
        )
        self.assertEqual(
            {
                dataset["dataset_id"]
                for dataset in catalog["datasets"]
            },
            {
                "candidate-responsibility-assignments",
                "candidate-geographic-jurisdiction",
                "candidate-asset-owner",
                "candidate-flood-signal-routing",
                "candidate-data-custodian",
                "candidate-agency-service-area",
                "candidate-agency-incident-capability",
                "candidate-legal-reference",
                "candidate-district-agency-summary",
                "evidence-official-document-registry",
                "evidence-mission-duty",
                "evidence-sop-process",
                "evidence-district-office-flood-process",
                "evidence-data-source-registry",
                "review-unresolved-asset-owner",
                "review-spatial-conflict",
                "acquisition-source-evidence",
                "acquisition-asset-owner-status",
                "acquisition-spatial-conflict-status",
                "acquisition-district-sop-availability",
                "acquisition-gap-resolution",
                "legal-authority-source-registry",
                "legal-authority-provisions",
                "legal-authority-district-candidates",
                "legal-authority-review-queue",
                "verified-legal-responsibility",
                "verified-dispatch-authorization",
            },
        )

    def test_official_document_evidence_is_traceable_and_unverified(
        self,
    ) -> None:
        evidence_dir = ROOT / "data" / "responsibility" / "evidence"
        registry = json.loads(
            (evidence_dir / "official_document_registry.json").read_text(
                encoding="utf-8"
            )
        )
        documents = registry["documents"]
        downloaded = [
            row
            for row in documents
            if row["source_access_status"] == "downloaded"
        ]
        blocked = [
            row
            for row in documents
            if row["source_access_status"] == "blocked_http_418"
        ]
        self.assertEqual(len(documents), 7)
        self.assertEqual(len(downloaded), 6)
        self.assertEqual(len(blocked), 1)
        self.assertIsNone(blocked[0]["document_sha256"])
        self.assertTrue(
            all(
                len(row["document_sha256"]) == 64
                and row["local_binary_committed"] is False
                for row in downloaded
            )
        )
        self.assertTrue(
            all(
                row["verification_status"] == "pending_legal_review"
                and row["is_official_legal_assignment"] is False
                and row["requires_human_approval"] is True
                for row in documents
            )
        )

    def test_mission_and_sop_evidence_excludes_personal_data(self) -> None:
        evidence_dir = ROOT / "data" / "responsibility" / "evidence"
        mission_rows = [
            json.loads(line)
            for line in (
                evidence_dir / "mission_duty_evidence_hash_index.jsonl"
            ).read_text(encoding="utf-8").splitlines()
        ]
        sop_rows = [
            json.loads(line)
            for line in (
                evidence_dir / "sop_process_evidence_hash_index.jsonl"
            ).read_text(encoding="utf-8").splitlines()
        ]
        self.assertEqual(len(mission_rows), 11)
        self.assertEqual(len(sop_rows), 7)
        self.assertEqual(
            len(mission_rows),
            len(
                {
                    row["mission_duty_hash_sha256"]
                    for row in mission_rows
                }
            ),
        )
        self.assertEqual(
            len(sop_rows),
            len(
                {
                    row["sop_process_hash_sha256"]
                    for row in sop_rows
                }
            ),
        )
        self.assertTrue(
            all(
                row["contains_personal_data"] is False
                and row["verification_status"]
                == "pending_legal_review"
                and row["is_official_legal_assignment"] is False
                for row in mission_rows + sop_rows
            )
        )
        self.assertTrue(
            all(row["source_pdf_pages"] for row in mission_rows + sop_rows)
        )

    def test_district_process_index_covers_all_50_offices(self) -> None:
        evidence_dir = ROOT / "data" / "responsibility" / "evidence"
        rows = [
            json.loads(line)
            for line in (
                evidence_dir
                / "district_office_flood_process_hash_index.jsonl"
            ).read_text(encoding="utf-8").splitlines()
        ]
        self.assertEqual(len(rows), 50)
        self.assertEqual(
            len(rows),
            len({row["district_code"] for row in rows}),
        )
        self.assertEqual(
            len(rows),
            len(
                {
                    row["district_process_hash_sha256"]
                    for row in rows
                }
            ),
        )
        self.assertTrue(
            all(
                len(row["process_stages"]) == 6
                and len(row["sop_process_hashes_sha256"]) in {2, 3}
                and len(row["service_area_candidate_agency_ids"]) == 2
                and row["requires_district_confirmation"] is True
                and row["district_specific_sop_verified"] is False
                and row["timing_is_emergency_response_sla"] is False
                and row["is_official_legal_assignment"] is False
                for row in rows
            )
        )
        bang_kho_laem = next(
            row for row in rows if row["district_code"] == "1031"
        )
        self.assertTrue(
            bang_kho_laem["district_specific_order_available"]
        )
        self.assertEqual(
            bang_kho_laem["district_specific_sop_status"],
            "candidate_historical_public_document",
        )

    def test_acquired_evidence_never_fabricates_ownership(self) -> None:
        acquisition_dir = (
            ROOT / "data" / "responsibility" / "acquisition"
        )
        owner_rows = [
            json.loads(line)
            for line in (
                acquisition_dir
                / "asset_owner_resolution_status.jsonl"
            ).read_text(encoding="utf-8").splitlines()
        ]
        conflict_rows = [
            json.loads(line)
            for line in (
                acquisition_dir
                / "spatial_conflict_resolution_status.jsonl"
            ).read_text(encoding="utf-8").splitlines()
        ]
        sop_rows = [
            json.loads(line)
            for line in (
                acquisition_dir / "district_sop_availability.jsonl"
            ).read_text(encoding="utf-8").splitlines()
        ]
        report = json.loads(
            (acquisition_dir / "quality_report.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertTrue(report["passed"])
        self.assertEqual(len(owner_rows), 247)
        self.assertEqual(len(conflict_rows), 171)
        self.assertEqual(len(sop_rows), 50)
        self.assertTrue(
            all(
                row["resolution_status"]
                == "requires_agency_confirmation"
                and row["asset_owner_agency_id"] is None
                and row["may_auto_dispatch"] is False
                for row in owner_rows
            )
        )
        self.assertEqual(
            sum(
                row["resolution_status"] == "candidate"
                for row in conflict_rows
            ),
            103,
        )
        self.assertEqual(
            sum(
                row["resolution_status"]
                == "requires_agency_confirmation"
                for row in conflict_rows
            ),
            68,
        )

    def test_data_source_registry_and_ingestion_risks_are_explicit(
        self,
    ) -> None:
        responsibility_dir = ROOT / "data" / "responsibility"
        rows = [
            json.loads(line)
            for line in (
                responsibility_dir
                / "evidence"
                / "data_source_registry_hash_index.jsonl"
            ).read_text(encoding="utf-8").splitlines()
        ]
        risk = json.loads(
            (
                responsibility_dir
                / "security"
                / "ingestion_risk_report.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(len(rows), 35)
        self.assertEqual(
            len(rows),
            len({row["data_source_hash_sha256"] for row in rows}),
        )
        self.assertTrue(
            all(row["source_url"].startswith("https://") for row in rows)
        )
        self.assertEqual(risk["summary"]["finding_count"], 10)
        self.assertEqual(risk["summary"]["open_count"], 4)
        self.assertEqual(risk["summary"]["partial_count"], 2)
        tls = next(
            row
            for row in risk["findings"]
            if row["finding_id"] == "ING-001"
        )
        self.assertEqual(tls["severity"], "critical")
        self.assertEqual(tls["status"], "fixed")
        legal_sources = [
            row
            for row in rows
            if row["source_id"].startswith("legal-authority-")
        ]
        self.assertEqual(len(legal_sources), 2)
        self.assertTrue(
            all(
                row["source_kind"]
                == "checked_in_official_legal_document"
                and row["local_file_sha256"]
                == row["upstream_document_sha256"]
                for row in legal_sources
            )
        )

    def test_legal_authority_evidence_is_real_and_fail_closed(
        self,
    ) -> None:
        legal_dir = (
            ROOT / "data" / "responsibility" / "legal_authority"
        )
        registry = json.loads(
            (legal_dir / "source_registry.json").read_text(
                encoding="utf-8"
            )
        )
        provisions = [
            json.loads(line)
            for line in (
                legal_dir / "authority_provisions_hash_index.jsonl"
            ).read_text(encoding="utf-8").splitlines()
        ]
        districts = [
            json.loads(line)
            for line in (
                legal_dir / "district_authority_candidates.jsonl"
            ).read_text(encoding="utf-8").splitlines()
        ]
        reviews = [
            json.loads(line)
            for line in (
                legal_dir / "legal_review_queue.jsonl"
            ).read_text(encoding="utf-8").splitlines()
        ]
        quality = json.loads(
            (legal_dir / "quality_report.json").read_text(
                encoding="utf-8"
            )
        )
        guardrails = json.loads(
            (legal_dir / "dispatch_guardrails.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(len(registry["sources"]), 2)
        for source in registry["sources"]:
            local_path = ROOT / source["local_path"]
            actual_hash = hashlib.sha256(
                local_path.read_bytes()
            ).hexdigest()
            self.assertEqual(actual_hash, source["actual_sha256"])
            self.assertEqual(actual_hash, source["expected_sha256"])
            self.assertEqual(
                source["verification_status"],
                "pending_legal_review",
            )
            self.assertFalse(source["may_auto_dispatch"])
        self.assertEqual(len(provisions), 15)
        self.assertEqual(
            len(provisions),
            len(
                {
                    row["authority_hash_sha256"]
                    for row in provisions
                }
            ),
        )
        self.assertTrue(
            all(
                row["verification_status"]
                == "pending_legal_review"
                and row["requires_action_specific_order"] is True
                and row["is_official_legal_assignment"] is False
                and row["is_official_dispatch_authorization"] is False
                and row["may_auto_dispatch"] is False
                for row in provisions
            )
        )
        self.assertEqual(len(districts), 50)
        self.assertEqual(
            len({row["district_code"] for row in districts}),
            50,
        )
        self.assertTrue(
            all(
                row["current_district_order_status"]
                == "not_supplied"
                and row["requires_current_district_order"] is True
                and row["may_auto_dispatch"] is False
                for row in districts
            )
        )
        self.assertEqual(len(reviews), 17)
        self.assertTrue(
            all(
                row["review_status"] == "open"
                and row["is_placeholder"] is False
                for row in reviews
            )
        )
        self.assertTrue(quality["passed"])
        self.assertEqual(
            quality["counts"]["verified_legal_assignments"],
            0,
        )
        self.assertEqual(
            quality["counts"]["verified_dispatch_authorizations"],
            0,
        )
        self.assertIn(
            "auto_dispatch",
            guardrails[
                "prohibited_without_verified_action_specific_authorization"
            ],
        )

    def test_review_layer_contains_real_source_records_not_placeholders(
        self,
    ) -> None:
        review_dir = ROOT / "data" / "responsibility" / "review"
        records = []
        for name in (
            "unresolved_asset_owners.jsonl",
            "spatial_conflicts.jsonl",
        ):
            records.extend(
                json.loads(line)
                for line in (review_dir / name)
                .read_text(encoding="utf-8")
                .splitlines()
            )
        manifest = json.loads(
            (review_dir / "review_manifest.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(len(records), 418)
        self.assertEqual(
            manifest["counts"],
            {
                "unresolved_asset_owners": 247,
                "spatial_conflicts": 171,
                "total": 418,
            },
        )
        self.assertTrue(
            all(
                row["is_placeholder"] is False
                and row["requires_manual_review"] is True
                for row in records
            )
        )
        self.assertEqual(
            len(records),
            len({row["review_hash_sha256"] for row in records}),
        )

    def test_integrity_manifest_matches_artifacts(self) -> None:
        responsibility_dir = ROOT / "data" / "responsibility"
        manifest = json.loads(
            (
                responsibility_dir
                / "security"
                / "integrity_manifest.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(
            manifest["metadata"]["signature_status"], "unsigned"
        )
        for artifact in manifest["artifacts"]:
            path = responsibility_dir / artifact["path"]
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertEqual(digest, artifact["sha256"])

    def test_two_person_legal_review_is_enforced(self) -> None:
        original_input_dir = MODULE.INPUT_DIR
        original_verified_dir = MODULE.VERIFIED_DIR
        try:
            with tempfile.TemporaryDirectory() as directory:
                temporary = Path(directory)
                MODULE.INPUT_DIR = temporary / "inputs"
                MODULE.VERIFIED_DIR = temporary / "verified"
                MODULE.write_csv(
                    MODULE.INPUT_DIR / "legal_basis.csv",
                    [
                        {
                            "legal_basis_id": "same-reviewer",
                            "document_title": "Official test document",
                            "issuing_authority": "Bangkok",
                            "document_type": "order",
                            "section_or_page": "1",
                            "effective_from": "2026-01-01",
                            "source_url": "https://dds.bangkok.go.th/test.pdf",
                            "document_sha256": "a" * 64,
                            "verification_status": "verified",
                            "verified_by": "reviewer-1",
                            "verified_at": "2026-06-28T00:00:00Z",
                            "approved_by": "reviewer-1",
                            "approved_at": "2026-06-28T00:01:00Z",
                        }
                    ],
                    MODULE.LEGAL_BASIS_FIELDS,
                )
                MODULE.write_csv(
                    MODULE.INPUT_DIR
                    / "verified_responsibility_assignments.csv",
                    [],
                    MODULE.VERIFIED_ASSIGNMENT_FIELDS,
                )
                with self.assertRaisesRegex(
                    RuntimeError, "verifier and approver must differ"
                ):
                    MODULE.build_verified_index({"bma"})
        finally:
            MODULE.INPUT_DIR = original_input_dir
            MODULE.VERIFIED_DIR = original_verified_dir

    def test_invalid_dispatch_authorization_fails_closed(self) -> None:
        original_input_dir = MODULE.INPUT_DIR
        original_verified_dir = MODULE.VERIFIED_DIR
        try:
            with tempfile.TemporaryDirectory() as directory:
                temporary = Path(directory)
                MODULE.INPUT_DIR = temporary / "inputs"
                MODULE.VERIFIED_DIR = temporary / "verified"
                MODULE.write_csv(
                    MODULE.INPUT_DIR / "legal_basis.csv",
                    [
                        {
                            "legal_basis_id": "verified-order",
                            "document_title": "Official test order",
                            "issuing_authority": "Bangkok",
                            "document_type": "order",
                            "section_or_page": "1",
                            "effective_from": "2026-01-01",
                            "source_url": "https://dds.bangkok.go.th/test.pdf",
                            "document_sha256": "b" * 64,
                            "verification_status": "verified",
                            "verified_by": "reviewer-1",
                            "verified_at": "2026-06-28T00:00:00Z",
                            "approved_by": "approver-1",
                            "approved_at": "2026-06-28T00:01:00Z",
                        }
                    ],
                    MODULE.LEGAL_BASIS_FIELDS,
                )
                MODULE.write_csv(
                    MODULE.INPUT_DIR
                    / "verified_responsibility_assignments.csv",
                    [],
                    MODULE.VERIFIED_ASSIGNMENT_FIELDS,
                )
                MODULE.write_csv(
                    MODULE.INPUT_DIR
                    / "verified_dispatch_authorizations.csv",
                    [
                        {
                            "authorization_source_id": "test-auth-1",
                            "actor_role_code": "district_operator",
                            "actor_agency_id": "bma",
                            "target_agency_id": "unknown-agency",
                            "permitted_action": "route_case",
                            "district_code": "1001",
                            "incident_type_code": "canal_overflow",
                            "legal_basis_id": "verified-order",
                            "effective_from": "2026-01-01",
                            "verified_by": "reviewer-1",
                            "verified_at": "2026-06-28T00:02:00Z",
                            "approved_by": "approver-1",
                            "approved_at": "2026-06-28T00:03:00Z",
                            "change_reason": "Initial test authorization",
                        }
                    ],
                    MODULE.DISPATCH_AUTHORIZATION_FIELDS,
                )
                with self.assertRaisesRegex(
                    RuntimeError, "unknown target_agency_id"
                ):
                    MODULE.build_verified_index({"bma"}, {"1001"})
                output = (
                    MODULE.VERIFIED_DIR
                    / "dispatch_authorization_hash_index.jsonl"
                )
                self.assertEqual(output.read_text(encoding="utf-8"), "")
        finally:
            MODULE.INPUT_DIR = original_input_dir
            MODULE.VERIFIED_DIR = original_verified_dir


if __name__ == "__main__":
    unittest.main()
