"""Tests for local ECS job waiter helpers."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "hcloud_ecs_wait_job.py"
SPEC = importlib.util.spec_from_file_location("hcloud_ecs_wait_job", SCRIPT)
assert SPEC and SPEC.loader
hcloud_ecs_wait_job = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(hcloud_ecs_wait_job)


class EcsWaitJobTest(unittest.TestCase):
    """Validate status extraction and classification without calling hcloud."""

    def test_extract_status_from_top_level_response(self) -> None:
        status = hcloud_ecs_wait_job.extract_status({"status": "SUCCESS"})

        self.assertEqual(status, "SUCCESS")

    def test_extract_status_from_nested_job_response(self) -> None:
        status = hcloud_ecs_wait_job.extract_status({"job": {"status": "running"}})

        self.assertEqual(status, "RUNNING")

    def test_classify_terminal_statuses(self) -> None:
        self.assertEqual(hcloud_ecs_wait_job.classify_status("SUCCESS"), "success")
        self.assertEqual(hcloud_ecs_wait_job.classify_status("FAILED"), "failure")
        self.assertEqual(hcloud_ecs_wait_job.classify_status("RUNNING"), "running")
        self.assertEqual(hcloud_ecs_wait_job.classify_status("QUEUED"), "unknown")


if __name__ == "__main__":
    unittest.main()
