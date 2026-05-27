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
from unittest.mock import patch


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
hcloud_resource_query = load_module("hcloud_resource_query", SCRIPTS / "hcloud_resource_query.py")
hcloud_resource_verify = load_module("hcloud_resource_verify", SCRIPTS / "hcloud_resource_verify.py")
hcloud_service_readiness = load_module("hcloud_service_readiness", SCRIPTS / "hcloud_service_readiness.py")
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

    def test_resource_query_builds_explicit_show_command(self) -> None:
        args = SimpleNamespace(
            service="EIP",
            operation="ShowPublicip",
            param=["publicip_id=eip-1"],
            arg=[],
            region="cn-north-4",
            project_id="project-1",
            profile=None,
            execute=False,
            timeout=1,
            allow_sensitive_read=False,
        )

        result = hcloud_resource_query.build_plan(args)

        self.assertTrue(result["success"], result)
        self.assertEqual(result["operation_scope"], "resource_query")
        self.assertIn("--arg=--publicip_id=eip-1", result["command"])
        self.assertIn("--arg=--cli-output=json", result["command"])
        self.assertIn("--expect-json", result["command"])

    def test_resource_query_resolves_lowercase_operation_name(self) -> None:
        args = SimpleNamespace(
            service="EIP",
            operation="showpublicip",
            param=["publicip_id=eip-1"],
            arg=[],
            region="cn-north-4",
            project_id="project-1",
            profile=None,
            execute=False,
            timeout=1,
            allow_sensitive_read=False,
        )

        result = hcloud_resource_query.build_plan(args)

        self.assertTrue(result["success"], result)
        self.assertEqual(result["operation"], "ShowPublicip")
        self.assertEqual(result["requested_operation"], "showpublicip")
        self.assertIn("--arg=--publicip_id=eip-1", result["command"])

    def test_resource_query_builds_vpc_show_command(self) -> None:
        args = SimpleNamespace(
            service="VPC",
            operation="showvpc",
            param=["vpc_id=vpc-1"],
            arg=[],
            region="cn-north-4",
            project_id="project-1",
            profile=None,
            execute=False,
            timeout=1,
            allow_sensitive_read=False,
        )

        result = hcloud_resource_query.build_plan(args)

        self.assertTrue(result["success"], result)
        self.assertEqual(result["operation_scope"], "resource_query")
        self.assertEqual(result["operation"], "ShowVpc")
        self.assertIn("--arg=--vpc_id=vpc-1", result["command"])

    def test_resource_query_rejects_missing_required_param(self) -> None:
        args = SimpleNamespace(
            service="CCE",
            operation="ShowCluster",
            param=[],
            arg=[],
            region="cn-north-4",
            project_id="project-1",
            profile=None,
            execute=False,
            timeout=1,
            allow_sensitive_read=False,
        )

        result = hcloud_resource_query.build_plan(args)

        self.assertFalse(result["success"])
        self.assertEqual(result["missing_params"], ["cluster_id"])

    def test_resource_query_blocks_sensitive_read_by_default(self) -> None:
        args = SimpleNamespace(
            service="ECS",
            operation="ShowServerPassword",
            param=["server_id=server-1"],
            arg=[],
            region="cn-north-4",
            project_id="project-1",
            profile=None,
            execute=False,
            timeout=1,
            allow_sensitive_read=False,
        )

        result = hcloud_resource_query.build_plan(args)

        self.assertFalse(result["success"])
        self.assertIn("Sensitive read", result["error"])

    def test_resource_query_maps_rds_configuration_alias(self) -> None:
        args = SimpleNamespace(
            service="RDS",
            operation="ShowConfigurationDetail",
            param=["config_id=config-1"],
            arg=[],
            region="cn-north-4",
            project_id="project-1",
            profile=None,
            execute=False,
            timeout=1,
            allow_sensitive_read=False,
        )

        result = hcloud_resource_query.build_plan(args)

        self.assertTrue(result["success"], result)
        self.assertEqual(result["requested_operation"], "ShowConfigurationDetail")
        self.assertEqual(result["operation"], "ShowConfiguration")
        self.assertIn("ShowConfiguration", result["command"])
        self.assertIn("--arg=--config_id=config-1", result["command"])

    def test_service_readiness_builds_vpc_profile(self) -> None:
        args = SimpleNamespace(
            service=["VPC"],
            target=[],
            region="cn-north-4",
            project_id="project-1",
            profile=None,
            limit=20,
            execute=False,
            timeout=1,
            strict=True,
            require_all=False,
        )

        result = hcloud_service_readiness.build_readiness(args)

        self.assertTrue(result["success"], result)
        checks = result["services"][0]["checks"]
        self.assertEqual(
            {item["operation"] for item in checks},
            {
                "ListVpcs",
                "ListSubnets",
                "ListSecurityGroups",
                "ListSecurityGroupRules",
                "ListVpcPeerings",
                "ShowVpc",
                "ShowSubnet",
                "ShowSecurityGroup",
            },
        )
        skipped = [item for item in checks if item.get("skipped")]
        self.assertEqual({item["operation"] for item in skipped}, {"ShowVpc", "ShowSubnet", "ShowSecurityGroup"})
        planned = [item for item in checks if not item.get("skipped")]
        self.assertTrue(all(item["runner"] == "scripts/hcloud_resource_discovery.py" for item in planned))

    def test_service_readiness_default_includes_high_frequency_profiles(self) -> None:
        args = SimpleNamespace(
            service=None,
            target=[],
            region="cn-north-4",
            project_id="project-1",
            profile=None,
            limit=20,
            execute=False,
            timeout=1,
            strict=True,
            require_all=False,
        )

        result = hcloud_service_readiness.build_readiness(args)

        self.assertTrue(result["success"], result)
        services = [item["service"] for item in result["services"]]
        self.assertEqual(services[:10], ["ECS", "VPC", "RDS", "IMS", "EVS", "EIP", "ELB", "NAT", "KPS", "IAM"])

    def test_service_readiness_skips_target_dependent_checks(self) -> None:
        args = SimpleNamespace(
            service=["ELB"],
            target=[],
            region="cn-north-4",
            project_id="project-1",
            profile=None,
            limit=20,
            execute=False,
            timeout=1,
            strict=True,
            require_all=False,
        )

        result = hcloud_service_readiness.build_readiness(args)

        self.assertTrue(result["success"], result)
        skipped = [item for item in result["services"][0]["checks"] if item.get("skipped")]
        self.assertEqual(
            {item["operation"] for item in skipped},
            {"ShowLoadBalancer", "ShowListener", "ShowPool", "ListMembers", "ShowMember"},
        )
        member_check = next(item for item in skipped if item["operation"] == "ShowMember")
        self.assertEqual(member_check["missing_targets"], ["pool_id", "member_id"])

    def test_service_readiness_uses_targets_for_member_checks(self) -> None:
        args = SimpleNamespace(
            service=["ELB"],
            target=["pool_id=pool-1", "member_id=member-1", "loadbalancer_id=lb-1", "listener_id=listener-1"],
            region="cn-north-4",
            project_id="project-1",
            profile=None,
            limit=20,
            execute=False,
            timeout=1,
            strict=True,
            require_all=True,
        )

        result = hcloud_service_readiness.build_readiness(args)

        self.assertTrue(result["success"], result)
        member_check = next(item for item in result["services"][0]["checks"] if item["operation"] == "ListMembers")
        self.assertFalse(member_check["skipped"])
        self.assertEqual(member_check["runner"], "scripts/hcloud_resource_query.py")
        self.assertIn("--arg=--pool_id=pool-1", member_check["plan"]["command"])
        show_member_check = next(item for item in result["services"][0]["checks"] if item["operation"] == "ShowMember")
        self.assertFalse(show_member_check["skipped"])
        self.assertIn("--arg=--member_id=member-1", show_member_check["plan"]["command"])

    def test_service_readiness_non_strict_execute_allows_execution_failures(self) -> None:
        args = SimpleNamespace(
            service=["VPC"],
            target=[],
            region="cn-north-4",
            project_id="project-1",
            profile=None,
            limit=20,
            execute=True,
            timeout=1,
            strict=False,
            require_all=False,
        )

        def fake_check(_args, service, _entry, check_spec, _targets):
            return {
                "service": service,
                "operation": check_spec["operation"],
                "stage": "execute",
                "success": False,
                "execution_success": False,
                "skipped": False,
            }

        with patch.object(hcloud_service_readiness, "build_check", side_effect=fake_check):
            result = hcloud_service_readiness.build_readiness(args)

        self.assertTrue(result["success"], result)
        self.assertTrue(result["services"][0]["success"])

    def test_service_readiness_non_strict_execute_keeps_plan_failures_blocking(self) -> None:
        args = SimpleNamespace(
            service=["VPC"],
            target=[],
            region="cn-north-4",
            project_id="project-1",
            profile=None,
            limit=20,
            execute=True,
            timeout=1,
            strict=False,
            require_all=False,
        )

        def fake_check(_args, service, _entry, check_spec, _targets):
            operation = check_spec["operation"]
            if operation == "ListSubnets":
                return {"service": service, "operation": operation, "stage": "plan", "success": False, "skipped": False}
            return {"service": service, "operation": operation, "stage": "execute", "success": False, "skipped": False}

        with patch.object(hcloud_service_readiness, "build_check", side_effect=fake_check):
            result = hcloud_service_readiness.build_readiness(args)

        self.assertFalse(result["success"])
        self.assertFalse(result["services"][0]["success"])

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

    def test_resource_verify_collects_singular_high_frequency_shapes(self) -> None:
        cases = [
            ("VPC", {"vpc": {"id": "vpc-1", "status": "OK"}}),
            ("ELB", {"loadbalancer": {"id": "lb-1", "provisioning_status": "ACTIVE"}}),
            ("EVS", {"volume": {"id": "vol-1", "status": "available"}}),
            ("NAT", {"dnat_rule": {"id": "dnat-1", "status": "ACTIVE"}}),
            ("IMS", {"image": {"id": "img-1", "status": "active"}}),
            ("KPS", {"keypair": {"keypair_name": "key-1"}}),
        ]

        for service, payload in cases:
            with self.subTest(service=service):
                resources = hcloud_resource_verify.collect_dicts(payload, service)

                self.assertEqual(len(resources), 1)

    def test_resource_verify_collects_top_level_rds_configuration(self) -> None:
        payload = {
            "id": "config-1",
            "name": "Default-PostgreSQL-11",
            "configuration_parameters": [
                {"name": "statement_timeout", "value": "0"},
            ],
        }

        resources = hcloud_resource_verify.collect_dicts(payload, "RDS")

        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]["id"], "config-1")

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
