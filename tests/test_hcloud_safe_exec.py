"""Tests for hcloud safe execution redaction helpers."""

from __future__ import annotations

import importlib.util
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "hcloud_safe_exec.py"
SPEC = importlib.util.spec_from_file_location("hcloud_safe_exec", SCRIPT)
assert SPEC and SPEC.loader
hcloud_safe_exec = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(hcloud_safe_exec)


class SafeExecRedactionTest(unittest.TestCase):
    """Validate redaction without calling hcloud."""

    def test_collect_inline_secrets_handles_equals_and_two_token_forms(self) -> None:
        secrets = hcloud_safe_exec.collect_inline_secrets(
            [
                "--secret-key=secret-one",
                "--access-key",
                "secret-two",
                "--name",
                "plain",
            ]
        )

        self.assertEqual(secrets, {"secret-one", "secret-two"})

    def test_redact_command_handles_two_token_secret_forms(self) -> None:
        command = ["hcloud", "configure", "set", "--secret-key", "secret-two", "--name", "plain"]

        redacted = hcloud_safe_exec.redact_command(command, {"secret-two"})

        self.assertEqual(redacted, ["hcloud", "configure", "set", "--secret-key", "***", "--name", "plain"])

    def test_redact_json_redacts_secret_keys_and_known_values(self) -> None:
        payload = {
            "token": "token-value",
            "nested": {
                "note": "prefix secret-value suffix",
                "items": [{"adminPass": "password-value"}],
            },
        }

        redacted = hcloud_safe_exec.redact_json(payload, {"secret-value"})

        self.assertEqual(redacted["token"], "***")
        self.assertEqual(redacted["nested"]["note"], "prefix *** suffix")
        self.assertEqual(redacted["nested"]["items"][0]["adminPass"], "***")

    def test_collect_json_input_secrets_reads_sensitive_fields_from_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "input.json"
            path.write_text(json.dumps({"body": {"server": {"adminPass": "password-value"}}}), encoding="utf-8")
            args = SimpleNamespace(json_input_file=str(path), json_input_text=None)

            secrets = hcloud_safe_exec.collect_json_input_secrets(args)

        self.assertEqual(secrets, {"password-value"})

    def test_collect_json_secrets_detects_sensitive_output_keys(self) -> None:
        payload = {
            "servers": [
                {
                    "OS-EXT-SRV-ATTR:user_data": "encoded-user-data",
                    "metadata": {"private_key": "key-value"},
                }
            ]
        }

        secrets = hcloud_safe_exec.collect_json_secrets(payload)

        self.assertEqual(secrets, {"encoded-user-data", "key-value"})

    def test_cli_redacts_parsed_json_and_parsed_json_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            hcloud_path = tmp_path / "hcloud"
            hcloud_path.write_text(
                "#!/usr/bin/env python3\n"
                "import json\n"
                "print(json.dumps({"
                "'adminPass': 'password-value', "
                "'note': 'token-value', "
                "'server': {'OS-EXT-SRV-ATTR:user_data': 'encoded-user-data'}"
                "}))\n",
                encoding="utf-8",
            )
            hcloud_path.chmod(hcloud_path.stat().st_mode | stat.S_IXUSR)
            input_path = tmp_path / "input.json"
            input_path.write_text(json.dumps({"adminPass": "password-value", "token": "token-value"}), encoding="utf-8")
            parsed_path = tmp_path / "parsed.json"

            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--service",
                    "ECS",
                    "--operation",
                    "ListServersDetails",
                    f"--json-input-file={input_path}",
                    "--expect-json",
                    f"--parsed-json-file={parsed_path}",
                ],
                capture_output=True,
                text=True,
                check=False,
                env={**os.environ, "PATH": f"{tmp_path}{os.pathsep}{os.environ.get('PATH', '')}"},
            )

            result = json.loads(completed.stdout)
            parsed_file = json.loads(parsed_path.read_text(encoding="utf-8"))

        self.assertEqual(completed.returncode, 0)
        self.assertEqual(
            result["parsed_json"],
            {"adminPass": "***", "note": "***", "server": {"OS-EXT-SRV-ATTR:user_data": "***"}},
        )
        self.assertEqual(
            parsed_file,
            {"adminPass": "***", "note": "***", "server": {"OS-EXT-SRV-ATTR:user_data": "***"}},
        )
        self.assertNotIn("password-value", completed.stdout)
        self.assertNotIn("token-value", completed.stdout)
        self.assertNotIn("encoded-user-data", completed.stdout)


if __name__ == "__main__":
    unittest.main()
