from __future__ import annotations

import importlib.util
import json
import struct
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_responsibility_analytics.py"
SPEC = importlib.util.spec_from_file_location(
    "responsibility_analytics",
    SCRIPT,
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Cannot load {SCRIPT}")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ResponsibilityAnalyticsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.prepared = MODULE.prepare_datasets()
        cls.normalized = MODULE.normalize_datasets(cls.prepared)
        cls.payload = MODULE.build_analysis_payload(
            cls.prepared,
            cls.normalized,
        )

    def test_preparation_counts_and_quality_gates(self) -> None:
        report = self.prepared["report"]
        self.assertTrue(report["passed"])
        self.assertTrue(all(report["checks"].values()))
        self.assertEqual(
            report["counts"],
            {
                "district_operations": 50,
                "agency_missions": 60,
                "quality_issues": 418,
            },
        )

    def test_normalized_dimensions_and_facts(self) -> None:
        manifest = self.normalized["manifest"]
        self.assertTrue(manifest["passed"])
        self.assertEqual(
            manifest["counts"],
            {
                "dim_district.csv": 50,
                "dim_agency.csv": 70,
                "dim_incident_type.csv": 10,
                "dim_source.csv": 35,
                "fact_district_agency_responsibility.csv": 872,
                "fact_district_process_stage.csv": 300,
                "fact_data_quality_issue.csv": 418,
            },
        )
        self.assertTrue(all(manifest["checks"].values()))
        contract = json.loads(
            (
                ROOT
                / "data"
                / "responsibility"
                / "normalized"
                / "data_contract.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(
            contract["normalized"][
                "fact_district_process_stage.csv"
            ]["grain"],
            "one process stage per Bangkok district",
        )

    def test_analytics_never_promotes_verified_status(self) -> None:
        responsibility = self.normalized["facts"]["responsibility"]
        districts = self.prepared["districts"]
        self.assertFalse(
            any(
                row["is_official_legal_assignment"]
                for row in responsibility
            )
        )
        self.assertTrue(
            all(
                row["district_specific_sop_verified"] is False
                and row["requires_district_confirmation"] is True
                for row in districts
            )
        )
        self.assertEqual(
            self.payload["kpis"]["verified_legal_assignment_count"],
            0,
        )

    def test_static_visualizations_match_source_fingerprint(self) -> None:
        visualization_dir = (
            ROOT / "data" / "responsibility" / "visualization"
        )
        manifest = json.loads(
            (
                visualization_dir / "visualization_manifest.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(
            manifest["metadata"]["source_fingerprint_sha256"],
            self.payload["source_fingerprint_sha256"],
        )
        self.assertFalse(manifest["metadata"]["frontend_artifact"])
        self.assertFalse(manifest["metadata"]["hosted"])
        self.assertEqual(len(manifest["visualizations"]), 2)
        for item in manifest["visualizations"]:
            path = ROOT / "data" / "responsibility" / item["path"]
            data = path.read_bytes()
            self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")
            width, height = struct.unpack(">II", data[16:24])
            self.assertGreaterEqual(width, 1500)
            self.assertGreaterEqual(height, 1000)


if __name__ == "__main__":
    unittest.main()
