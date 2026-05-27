"""Tests for local hcloud metadata lookup helpers."""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "hcloud_meta_lookup.py"
SPEC = importlib.util.spec_from_file_location("hcloud_meta_lookup", SCRIPT)
assert SPEC and SPEC.loader
hcloud_meta_lookup = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(hcloud_meta_lookup)


class MetaLookupTest(unittest.TestCase):
    """Validate metadata parsing without depending on a real hcloud cache."""

    def test_load_operation_detail_reads_json_compatible_yaml_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            template_dir = Path(tmp_dir)
            detail_path = template_dir / "ListServersDetails_en.yaml"
            detail_path.write_text(
                json.dumps(
                    {
                        "Description": "List servers.",
                        "Request": {"Method": "GET", "Path": "/v1/{project_id}/cloudservers/detail"},
                        "Params": [{"Name": ["project_id"], "Required": True, "Position": "path", "ParamType": "string"}],
                    }
                ),
                encoding="utf-8",
            )

            detail = hcloud_meta_lookup.load_operation_detail(template_dir, "ListServersDetails")

        self.assertIsNotNone(detail)
        assert detail is not None
        self.assertEqual(detail["detail_file_format"], "json")
        self.assertEqual(detail["param_count"], 1)

    def test_load_operation_detail_reports_yaml_boundary_clearly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            template_dir = Path(tmp_dir)
            detail_path = template_dir / "ListThings_en.yaml"
            detail_path.write_text("Description: List things\nParams:\n  - Name: [project_id]\n", encoding="utf-8")

            detail = hcloud_meta_lookup.load_operation_detail(template_dir, "ListThings")

        self.assertIsNotNone(detail)
        assert detail is not None
        self.assertIn(detail["detail_file_format"], {"yaml", "yaml_unavailable"})
        if detail["detail_file_format"] == "yaml_unavailable":
            self.assertIn("PyYAML is not installed", detail["error"])


if __name__ == "__main__":
    unittest.main()
