from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "scrape_bangkok_water.py"
SPEC = importlib.util.spec_from_file_location("bangkok_water_scraper", SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Cannot load {SCRIPT}")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class FakeHeaders:
    def __init__(
        self,
        content_type: str = "text/html",
        content_length: str | None = None,
    ) -> None:
        self.content_type = content_type
        self.content_length = content_length

    def get_content_type(self) -> str:
        return self.content_type

    def get(self, name: str) -> str | None:
        if name.lower() == "content-length":
            return self.content_length
        return None


class FakeResponse:
    def __init__(
        self,
        final_url: str,
        body: bytes = b"ok",
        content_type: str = "text/html",
        content_length: str | None = None,
    ) -> None:
        self.final_url = final_url
        self.body = body
        self.headers = FakeHeaders(content_type, content_length)

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def geturl(self) -> str:
        return self.final_url

    def read(self, size: int) -> bytes:
        return self.body[:size]


class ScraperSecurityTest(unittest.TestCase):
    def test_compatibility_wrapper_does_not_disable_tls(self) -> None:
        wrapper = (ROOT / "scripts" / "run_scraper.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("_create_unverified_context", wrapper)
        self.assertNotIn("_create_default_https_context =", wrapper)

    def test_source_url_allowlist_rejects_unsafe_origins(self) -> None:
        for url in (
            "http://weather.bangkok.go.th/water/",
            "https://example.com/water/",
            "https://user:pass@weather.bangkok.go.th/water/",
        ):
            with self.subTest(url=url), self.assertRaises(ValueError):
                MODULE.validate_source_url(url)

    def test_redirect_to_non_allowlisted_host_fails_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "allowlisted"):
            MODULE.AllowlistedRedirectHandler().redirect_request(
                None,
                None,
                302,
                "Found",
                None,
                "https://example.com/redirected",
            )
        response = FakeResponse("https://example.com/redirected")
        with mock.patch.object(
            MODULE.SOURCE_OPENER,
            "open",
            return_value=response,
        ):
            with self.assertRaisesRegex(ValueError, "allowlisted"):
                MODULE.http_get(MODULE.CATALOG_URL)

    def test_oversized_response_fails_closed(self) -> None:
        response = FakeResponse(
            MODULE.CATALOG_URL,
            content_length=str(MODULE.MAX_RESPONSE_BYTES + 1),
        )
        with mock.patch.object(
            MODULE.SOURCE_OPENER,
            "open",
            return_value=response,
        ):
            with self.assertRaisesRegex(ValueError, "maximum"):
                MODULE.http_get(MODULE.CATALOG_URL)

    def test_duplicate_station_ids_are_rejected(self) -> None:
        text = json.dumps(
            [
                {"water_id": 1, "latitude": 13.7, "longitude": 100.5},
                {"water_id": 1, "latitude": 13.8, "longitude": 100.6},
            ]
        )
        with self.assertRaisesRegex(ValueError, "duplicate"):
            MODULE.parse_latest_json(text)
        self.assertIsNone(MODULE.clean_float(float("nan")))
        self.assertIsNone(MODULE.parse_bangkok_time("not-a-time"))

    def test_empty_or_wrong_station_history_cache_is_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "1.json"
            path.write_text(
                json.dumps(
                    {
                        "metadata": {"station_id": 2},
                        "series": [],
                    }
                ),
                encoding="utf-8",
            )
            self.assertFalse(MODULE.existing_history_is_valid(path, 1))


if __name__ == "__main__":
    unittest.main()
