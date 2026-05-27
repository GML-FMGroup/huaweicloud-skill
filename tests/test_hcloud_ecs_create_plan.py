"""Tests for local ECS create planning helpers."""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "hcloud_ecs_create_plan.py"
SPEC = importlib.util.spec_from_file_location("hcloud_ecs_create_plan", SCRIPT)
assert SPEC and SPEC.loader
hcloud_ecs_create_plan = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(hcloud_ecs_create_plan)


def minimal_payload() -> dict:
    """Return a complete minimal ECS create payload for local validation."""
    return {
        "path": {"project_id": "project-1"},
        "body": {
            "server": {
                "name": "ecs-test",
                "availability_zone": "cn-north-4a",
                "flavorRef": "s6.large.2",
                "imageRef": "image-1",
                "vpcid": "vpc-1",
                "nics": [{"subnet_id": "subnet-1"}],
                "security_groups": [{"id": "sg-1"}],
                "root_volume": {"volumetype": "SSD"},
                "key_name": "keypair-1",
                "count": 1,
            }
        },
    }


class EcsCreatePlanTest(unittest.TestCase):
    """Validate ECS create planner behavior without calling hcloud."""

    def test_validate_payload_rejects_placeholders(self) -> None:
        payload = minimal_payload()
        payload["path"]["project_id"] = "<project_id>"

        validation = hcloud_ecs_create_plan.validate_payload(payload)

        self.assertFalse(validation["valid"])
        self.assertIn(
            "Unresolved placeholder at path.project_id: <project_id>",
            validation["errors"],
        )

    def test_validate_payload_accepts_complete_minimal_payload(self) -> None:
        validation = hcloud_ecs_create_plan.validate_payload(minimal_payload())

        self.assertTrue(validation["valid"])
        self.assertEqual(validation["errors"], [])

    def test_build_result_generates_dryrun_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "ecs.json"
            path.write_text(json.dumps(minimal_payload()), encoding="utf-8")
            args = SimpleNamespace(
                json_input_file=str(path),
                operation="CreateServers",
                region="cn-north-4",
                profile=None,
                mode="dryrun",
                confirm_submit=False,
                allow_placeholders=False,
                max_count=10,
                allow_large_count=False,
            )

            result = hcloud_ecs_create_plan.build_result(args)

        self.assertTrue(result["success"])
        self.assertIn("--arg=--dryrun", result["commands"]["safe_exec"])
        self.assertIn("--arg=--cli-output=json", result["commands"]["safe_exec"])
        self.assertIn("--expect-json", result["commands"]["safe_exec"])
        self.assertIn("safe_exec_shell", result["commands"])
        self.assertIn("--cli-region=cn-north-4", result["commands"]["hcloud"])

    def test_submit_mode_requires_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "ecs.json"
            path.write_text(json.dumps(minimal_payload()), encoding="utf-8")
            args = SimpleNamespace(
                json_input_file=str(path),
                operation="CreateServers",
                region="cn-north-4",
                profile=None,
                mode="submit",
                confirm_submit=False,
                allow_placeholders=False,
                max_count=10,
                allow_large_count=False,
            )

            result = hcloud_ecs_create_plan.build_result(args)

        self.assertFalse(result["success"])
        self.assertIn("Non-dryrun submit mode requires --confirm-submit.", result["validation"]["errors"])

    def test_allow_placeholders_does_not_generate_commands(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            payload = minimal_payload()
            payload["path"]["project_id"] = "<project_id>"
            path = Path(tmp_dir) / "ecs.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            args = SimpleNamespace(
                json_input_file=str(path),
                operation="CreateServers",
                region="cn-north-4",
                profile=None,
                mode="dryrun",
                confirm_submit=False,
                allow_placeholders=True,
                max_count=10,
                allow_large_count=False,
            )

            result = hcloud_ecs_create_plan.build_result(args)

        self.assertTrue(result["success"])
        self.assertFalse(result["ready_to_run"])
        self.assertEqual(result["commands"], {})

    def test_validate_payload_rejects_embedded_placeholders(self) -> None:
        payload = minimal_payload()
        payload["body"]["server"]["name"] = "ecs-<env>"

        validation = hcloud_ecs_create_plan.validate_payload(payload)

        self.assertFalse(validation["valid"])
        self.assertIn("Unresolved placeholder at body.server.name: ecs-<env>", validation["errors"])

    def test_validate_payload_rejects_large_count_without_override(self) -> None:
        payload = minimal_payload()
        payload["body"]["server"]["count"] = 11

        validation = hcloud_ecs_create_plan.validate_payload(payload)

        self.assertFalse(validation["valid"])
        self.assertIn(
            "body.server.count exceeds conservative max 10. "
            "Use --allow-large-count only after confirming cost and quota impact.",
            validation["errors"],
        )

    def test_validate_payload_allows_large_count_with_override(self) -> None:
        payload = minimal_payload()
        payload["body"]["server"]["count"] = 11

        validation = hcloud_ecs_create_plan.validate_payload(payload, allow_large_count=True)

        self.assertTrue(validation["valid"])

    def test_validate_payload_allows_admin_password_without_keypair(self) -> None:
        payload = minimal_payload()
        payload["body"]["server"].pop("key_name")
        payload["body"]["server"]["adminPass"] = "password-value"

        validation = hcloud_ecs_create_plan.validate_payload(payload)

        self.assertTrue(validation["valid"])
        self.assertNotIn(
            "No body.server.key_name or body.server.adminPass found. Creation may still be valid, "
            "but login access should be verified before submit.",
            validation["warnings"],
        )

    def test_validate_payload_warns_when_security_group_is_missing(self) -> None:
        payload = minimal_payload()
        payload["body"]["server"].pop("security_groups")

        validation = hcloud_ecs_create_plan.validate_payload(payload)

        self.assertTrue(validation["valid"])
        self.assertIn(
            "No body.server.security_groups[0].id found. Huawei Cloud may bind the default security group, "
            "but network exposure rules should be reviewed before submit.",
            validation["warnings"],
        )


if __name__ == "__main__":
    unittest.main()
