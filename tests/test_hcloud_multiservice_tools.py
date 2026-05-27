"""Tests for multi-service smoke, planner, and verifier helpers."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def load_module(name: str, path: Path):
    """Load a script module for isolated unit tests."""
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


hcloud_readonly_smoke = load_module("hcloud_readonly_smoke", SCRIPTS / "hcloud_readonly_smoke.py")
hcloud_resource_verify = load_module("hcloud_resource_verify", SCRIPTS / "hcloud_resource_verify.py")
hcloud_service_change_plan = load_module("hcloud_service_change_plan", SCRIPTS / "hcloud_service_change_plan.py")


class MultiServiceToolsTest(unittest.TestCase):
    """Validate multi-service tool contracts without calling hcloud."""

    def test_readonly_smoke_builds_registered_service_commands(self) -> None:
        args = SimpleNamespace(
            service=["EIP", "RDS"],
            operation=[],
            region="cn-north-4",
            project_id="project-1",
            profile=None,
            limit=20,
            execute=False,
            timeout=1,
            strict=True,
        )

        result = hcloud_readonly_smoke.build_smoke_plan(args)

        self.assertTrue(result["success"], result)
        self.assertEqual(result["mode"], "plan")
        self.assertEqual(result["service_count"], 2)
        services = {item["service"] for item in result["checks"]}
        self.assertEqual(services, {"EIP", "RDS"})
        operations = {item["service"]: item["operation"] for item in result["checks"]}
        self.assertEqual(operations["EIP"], "ListPublicips")
        self.assertEqual(operations["RDS"], "ListInstances")
        for item in result["checks"]:
            command = item["plan"]["commands"][0]["command"]
            self.assertIn("--expect-json", command)
            self.assertIn("--arg=--cli-output=json", command)

    def test_readonly_smoke_uses_supported_cdn_cli_region(self) -> None:
        args = SimpleNamespace(
            service=["CDN"],
            operation=[],
            region="cn-north-4",
            project_id="project-1",
            profile=None,
            limit=20,
            execute=False,
            timeout=1,
            strict=True,
        )

        result = hcloud_readonly_smoke.build_smoke_plan(args)

        self.assertTrue(result["success"], result)
        command_item = result["checks"][0]["plan"]["commands"][0]
        self.assertIn("--arg=--cli-region=cn-north-1", command_item["command"])
        self.assertNotIn("--arg=--cli-region=cn-north-4", command_item["command"])
        self.assertEqual(command_item["region_resolution"]["requested_region"], "cn-north-4")
        self.assertEqual(command_item["region_resolution"]["resolved_region"], "cn-north-1")

    def test_resource_verify_accepts_eip_binding(self) -> None:
        payload = {
            "parsed_json": {
                "publicips": [
                    {
                        "id": "eip-1",
                        "alias": "eip-app-01",
                        "status": "BIND_ACTIVE",
                        "port_id": "port-1",
                        "associate_instance_id": "server-1",
                    }
                ]
            }
        }
        args = SimpleNamespace(
            service="EIP",
            target_id=["eip-1"],
            target_name=[],
            expect_status=["BIND_ACTIVE"],
            expect_field=[],
            expect_cidr=None,
            expect_bound_to="port-1",
            require_match=True,
        )

        result = hcloud_resource_verify.verify_payload(args, payload)

        self.assertTrue(result["success"], result)
        self.assertEqual(result["matched_count"], 1)
        self.assertEqual(result["failures"], [])

    def test_resource_verify_accepts_eip_associate_instance_binding(self) -> None:
        payload = {
            "publicips": [
                {
                    "id": "eip-1",
                    "status": "ACTIVE",
                    "associate_instance_id": "elb-1",
                }
            ]
        }
        args = SimpleNamespace(
            service="EIP",
            target_id=["eip-1"],
            target_name=[],
            expect_status=["ACTIVE"],
            expect_field=[],
            expect_cidr=None,
            expect_bound_to="elb-1",
            require_match=True,
        )

        result = hcloud_resource_verify.verify_payload(args, payload)

        self.assertTrue(result["success"], result)

    def test_resource_verify_reports_status_mismatch(self) -> None:
        payload = {"instances": [{"id": "rds-1", "name": "db", "status": "BUILD"}]}
        args = SimpleNamespace(
            service="RDS",
            target_id=[],
            target_name=["db"],
            expect_status=["AVAILABLE"],
            expect_field=[],
            expect_cidr=None,
            expect_bound_to=None,
            require_match=True,
        )

        result = hcloud_resource_verify.verify_payload(args, payload)

        self.assertFalse(result["success"])
        self.assertIn("status_mismatch", result["failures"])

    def test_resource_verify_accepts_expected_fields(self) -> None:
        payload = {"loadbalancers": [{"id": "lb-1", "provisioning_status": "ACTIVE", "operating_status": "ONLINE"}]}
        args = SimpleNamespace(
            service="ELB",
            target_id=["lb-1"],
            target_name=[],
            expect_status=["ACTIVE"],
            expect_field=["operating_status=ONLINE"],
            expect_cidr=None,
            expect_bound_to=None,
            require_match=True,
        )

        result = hcloud_resource_verify.verify_payload(args, payload)

        self.assertTrue(result["success"], result)

    def test_resource_verify_accepts_cdn_domain_status(self) -> None:
        payload = {"domains": [{"id": "domain-1", "domain_name": "static.example.com", "domain_status": "online"}]}
        args = SimpleNamespace(
            service="CDN",
            target_id=[],
            target_name=["static.example.com"],
            expect_status=["ONLINE"],
            expect_field=[],
            expect_cidr=None,
            expect_bound_to=None,
            require_match=True,
        )

        result = hcloud_resource_verify.verify_payload(args, payload)

        self.assertTrue(result["success"], result)

    def test_resource_verify_accepts_dns_recordset_name(self) -> None:
        payload = {"recordsets": [{"id": "recordset-1", "name": "www.example.com.", "status": "ACTIVE"}]}
        args = SimpleNamespace(
            service="DNS",
            target_id=[],
            target_name=["www.example.com."],
            expect_status=["ACTIVE"],
            expect_field=[],
            expect_cidr=None,
            expect_bound_to=None,
            require_match=True,
        )

        result = hcloud_resource_verify.verify_payload(args, payload)

        self.assertTrue(result["success"], result)

    def test_service_change_plan_adds_service_hints(self) -> None:
        args = SimpleNamespace(
            service="EIP",
            operation="CreatePublicip",
            region="cn-north-4",
            project_id="project-1",
            profile=None,
            json_input_file=None,
            arg=[],
            no_dryrun=False,
            allow_unregistered=False,
        )

        result = hcloud_service_change_plan.build_service_plan(args)

        self.assertTrue(result["success"], result)
        self.assertTrue(result["planning_only"])
        self.assertTrue(result["registered_change_operation"])
        self.assertEqual(result["resource_verifier"], "scripts/hcloud_resource_verify.py")
        self.assertTrue(result["service_verification_hints"])
        self.assertIn("--arg=--dryrun", result["commands"]["dryrun_or_plan"])

    def test_service_change_plan_uses_supported_cdn_cli_region(self) -> None:
        args = SimpleNamespace(
            service="CDN",
            operation="CreateDomain",
            region="cn-north-4",
            project_id="project-1",
            profile=None,
            json_input_file=None,
            arg=[],
            no_dryrun=False,
            allow_unregistered=False,
        )

        result = hcloud_service_change_plan.build_service_plan(args)

        self.assertTrue(result["success"], result)
        self.assertIn("--arg=--cli-region=cn-north-1", result["commands"]["dryrun_or_plan"])
        self.assertNotIn("--arg=--cli-region=cn-north-4", result["commands"]["dryrun_or_plan"])
        self.assertEqual(result["region_resolution"]["requested_region"], "cn-north-4")
        self.assertEqual(result["region_resolution"]["resolved_region"], "cn-north-1")

    def test_service_change_plan_rejects_unregistered_operation(self) -> None:
        args = SimpleNamespace(
            service="EIP",
            operation="RunUnknownMutation",
            region="cn-north-4",
            project_id="project-1",
            profile=None,
            json_input_file=None,
            arg=[],
            no_dryrun=False,
            allow_unregistered=False,
        )

        result = hcloud_service_change_plan.build_service_plan(args)

        self.assertFalse(result["success"])
        self.assertIn("not registered", result["error"])

    def test_resource_verify_cli_reads_safe_exec_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "result.json"
            path.write_text(
                json.dumps({"parsed_json": {"volumes": [{"id": "vol-1", "status": "in-use", "attachments": [{"server_id": "server-1"}]}]}}),
                encoding="utf-8",
            )
            args = SimpleNamespace(
                service="EVS",
                json_file=str(path),
                target_id=["vol-1"],
                target_name=[],
                expect_status=["IN-USE"],
                expect_field=[],
                expect_cidr=None,
                expect_bound_to="server-1",
                require_match=True,
                pretty=False,
            )

            result = hcloud_resource_verify.verify_payload(args, hcloud_resource_verify.load_json(path))

        self.assertTrue(result["success"], result)

    def test_resource_verify_cli_reports_missing_file_as_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "missing.json"

            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "hcloud_resource_verify.py"),
                    "--service",
                    "CDN",
                    "--json-file",
                    str(path),
                ],
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(completed.returncode, 1)
        result = json.loads(completed.stdout)
        self.assertFalse(result["success"])
        self.assertIn("missing.json", result["error"])


if __name__ == "__main__":
    unittest.main()
