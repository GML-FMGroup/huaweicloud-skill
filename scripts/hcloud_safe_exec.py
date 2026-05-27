#!/usr/bin/env python3
"""Execute hcloud commands with structured JSON output and basic secret redaction."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any


SECRET_HINTS = (
    "access-key",
    "accesskey",
    "secret-key",
    "secretaccesskey",
    "security-token",
    "securitytoken",
    "x-auth-token",
    "auth-token",
    "token",
    "credential",
    "credentials",
    "password",
    "passwd",
    "adminpass",
    "private-key",
    "private_key",
    "privatekey",
    "user-data",
    "user_data",
    "userdata",
)
ERROR_TYPES = ("USE_ERROR", "NETWORK_ERROR", "OPENAPI_ERROR", "APIE_ERROR")


def load_json(path: Path) -> Any:
    """Return parsed JSON content from a file."""
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_bool_text(value: Any) -> Any:
    """Normalize KooCLI config booleans stored as strings."""
    if isinstance(value, str):
        lowered = value.lower()
        if lowered == "true":
            return True
        if lowered == "false":
            return False
    return value


def collect_known_secrets() -> set[str]:
    """Collect locally known secrets so they can be redacted from output."""
    config_path = Path.home() / ".hcloud" / "config.json"
    if not config_path.exists():
        return set()

    config = load_json(config_path)
    secrets: set[str] = set()
    for profile in config.get("profiles", []):
        for key in ("accessKeyId", "secretAccessKey", "securityToken"):
            value = profile.get(key)
            if value:
                secrets.add(str(value))
    return secrets


def looks_like_secret_arg(arg: str) -> bool:
    """Return True when an argument key suggests sensitive data."""
    lowered = arg.lower()
    return any(hint in lowered for hint in SECRET_HINTS)


def collect_inline_secrets(args: list[str]) -> set[str]:
    """Collect secret values directly passed via CLI arguments."""
    secrets: set[str] = set()
    for index, arg in enumerate(args):
        if "=" in arg and looks_like_secret_arg(arg.split("=", 1)[0]):
            secrets.add(arg.split("=", 1)[1])
            continue
        if looks_like_secret_arg(arg) and index + 1 < len(args):
            next_arg = args[index + 1]
            if next_arg and not next_arg.startswith("-"):
                secrets.add(next_arg)
    return secrets


def collect_json_secrets(value: Any) -> set[str]:
    """Collect sensitive scalar values from a JSON-like object."""
    secrets: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            if looks_like_secret_arg(str(key)):
                if isinstance(child, str) and child:
                    secrets.add(child)
                elif isinstance(child, (int, float, bool)):
                    secrets.add(str(child))
                continue
            secrets.update(collect_json_secrets(child))
    elif isinstance(value, list):
        for child in value:
            secrets.update(collect_json_secrets(child))
    return secrets


def collect_json_input_secrets(args: argparse.Namespace) -> set[str]:
    """Collect secrets embedded in JSON input text or files when parseable."""
    secrets: set[str] = set()
    try:
        if args.json_input_file:
            secrets.update(collect_json_secrets(load_json(Path(args.json_input_file))))
        if args.json_input_text:
            secrets.update(collect_json_secrets(json.loads(args.json_input_text)))
    except (OSError, json.JSONDecodeError):
        return secrets
    return secrets


def coerce_output_text(value: str | bytes | None) -> str:
    """Normalize subprocess output to text for redaction and reporting."""
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def redact_text(text: str | bytes | None, secrets: set[str]) -> str:
    """Replace exact secret values with a redaction marker."""
    redacted = coerce_output_text(text)
    for secret in sorted((item for item in secrets if item), key=len, reverse=True):
        redacted = redacted.replace(secret, "***")
    return redacted


def redact_command(command: list[str], secrets: set[str]) -> list[str]:
    """Return a redacted command list."""
    redacted: list[str] = []
    redact_next = False
    for item in command:
        if redact_next:
            redacted.append(item if item.startswith("-") else "***")
            redact_next = False
            continue
        if "=" in item and looks_like_secret_arg(item.split("=", 1)[0]):
            key = item.split("=", 1)[0]
            redacted.append(f"{key}=***")
        elif looks_like_secret_arg(item):
            redacted.append(item)
            redact_next = True
        else:
            redacted.append(redact_text(item, secrets))
    return redacted


def redact_json(value: Any, secrets: set[str], key: str | None = None) -> Any:
    """Recursively redact sensitive values in parsed JSON-like data."""
    if key is not None and looks_like_secret_arg(key):
        return "***"
    if isinstance(value, dict):
        return {item_key: redact_json(child, secrets, str(item_key)) for item_key, child in value.items()}
    if isinstance(value, list):
        return [redact_json(child, secrets) for child in value]
    if isinstance(value, str):
        return redact_text(value, secrets)
    return value


def classify_error(stdout: str, stderr: str) -> str | None:
    """Extract the first known KooCLI error type from output."""
    combined = f"{stdout}\n{stderr}"
    for error_type in ERROR_TYPES:
        if f"[{error_type}]" in combined:
            return error_type
    return None


def advice_for_error(error_type: str | None) -> str | None:
    """Return a short next-step hint for a known error type."""
    if error_type == "USE_ERROR":
        return "Re-check the active profile, region, service, operation, and parameter names."
    if error_type == "NETWORK_ERROR":
        return "Check connectivity and consider increasing cli-connect-timeout, cli-read-timeout, and cli-retry-count."
    if error_type == "OPENAPI_ERROR":
        return "The cloud API rejected the request. Re-check the actual business parameters and service-side constraints."
    if error_type == "APIE_ERROR":
        return "Live metadata lookup failed. Fall back to local meta cache or curated references before guessing parameters."
    return None


def trim_text(text: str, max_chars: int) -> tuple[str, bool]:
    """Trim text to a maximum length and report whether truncation happened."""
    if len(text) <= max_chars:
        return text, False
    return text[:max_chars], True


def maybe_parse_json(stdout: str) -> tuple[Any | None, str | None]:
    """Try to parse stdout as JSON."""
    stripped = stdout.strip()
    if not stripped:
        return None, None
    try:
        return json.loads(stripped), None
    except json.JSONDecodeError as exc:
        for marker in ("{", "["):
            marker_index = stripped.find(marker)
            if marker_index > 0:
                candidate = stripped[marker_index:]
                try:
                    return json.loads(candidate), None
                except json.JSONDecodeError:
                    continue
        return None, str(exc)


def build_command(args: argparse.Namespace, temp_json_file: Path | None) -> list[str]:
    """Build the final hcloud subprocess command."""
    binary = shutil.which("hcloud")
    if not binary:
        raise FileNotFoundError("hcloud binary not found in PATH.")

    if args.command_part:
        command = [binary] + args.command_part
    else:
        command = [binary, args.service, args.operation]

    command.extend(args.arg)

    if args.json_input_file:
        command.append(f"--cli-jsonInput={args.json_input_file}")
    if temp_json_file is not None:
        command.append(f"--cli-jsonInput={temp_json_file}")

    return command


def ensure_json_input_args(args: argparse.Namespace) -> None:
    """Validate JSON input arguments."""
    if args.json_input_file and args.json_input_text:
        raise ValueError("Use either --json-input-file or --json-input-text, not both.")


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--service", help="Huawei Cloud service name, for example ECS.")
    parser.add_argument("--operation", help="Huawei Cloud operation name, for example ListFlavors.")
    parser.add_argument(
        "--command-part",
        action="append",
        default=[],
        help="Generic hcloud command parts, for example --command-part=configure --command-part=show.",
    )
    parser.add_argument(
        "--arg",
        action="append",
        default=[],
        help="A raw hcloud argument token. Use the = form, for example --arg=--cli-region=cn-north-4.",
    )
    parser.add_argument("--json-input-file", help="Existing JSON file path to pass via --cli-jsonInput.")
    parser.add_argument("--json-input-text", help="Inline JSON text to write to a temporary file for --cli-jsonInput.")
    parser.add_argument("--cwd", help="Working directory for the hcloud subprocess.")
    parser.add_argument("--timeout", type=int, default=120, help="Subprocess timeout in seconds.")
    parser.add_argument("--max-output-chars", type=int, default=20000, help="Maximum number of chars kept for stdout and stderr.")
    parser.add_argument("--expect-json", action="store_true", help="Attempt to parse stdout as JSON.")
    parser.add_argument("--result-file", help="Optional path to save the full structured result JSON.")
    parser.add_argument("--parsed-json-file", help="Optional path to save only parsed_json when available.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print the JSON result.")
    args = parser.parse_args()

    if not args.command_part and not (args.service and args.operation):
        parser.error("Provide either --command-part ... or both --service and --operation.")
    if args.command_part and (args.service or args.operation):
        parser.error("Do not mix --command-part with --service/--operation.")

    return args


def main() -> int:
    """Run hcloud and print a structured execution result."""
    args = parse_args()
    ensure_json_input_args(args)

    temp_json_file: Path | None = None
    if args.json_input_text:
        temp = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
        temp.write(args.json_input_text)
        temp.flush()
        temp.close()
        temp_json_file = Path(temp.name)

    known_secrets = collect_known_secrets()
    known_secrets.update(collect_inline_secrets(args.arg + args.command_part))
    known_secrets.update(collect_json_input_secrets(args))

    started_at = time.time()
    try:
        command = build_command(args, temp_json_file)
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            cwd=args.cwd,
            timeout=args.timeout,
            check=False,
        )
        duration_seconds = round(time.time() - started_at, 3)
        raw_stdout = completed.stdout
        raw_stderr = completed.stderr
        parsed_json = None
        parsed_json_error = None
        if args.expect_json:
            parsed_json, parsed_json_error = maybe_parse_json(raw_stdout)
            if parsed_json is not None:
                known_secrets.update(collect_json_secrets(parsed_json))

        redacted_stdout = redact_text(raw_stdout, known_secrets)
        redacted_stderr = redact_text(raw_stderr, known_secrets)
        stdout_trimmed, stdout_truncated = trim_text(redacted_stdout, args.max_output_chars)
        stderr_trimmed, stderr_truncated = trim_text(redacted_stderr, args.max_output_chars)
        error_type = classify_error(raw_stdout, raw_stderr)
        logical_success = completed.returncode == 0 and error_type is None

        result = {
            "success": logical_success,
            "return_code": completed.returncode,
            "duration_seconds": duration_seconds,
            "service": args.service,
            "operation": args.operation,
            "command": redact_command(command, known_secrets),
            "stdout": stdout_trimmed,
            "stderr": stderr_trimmed,
            "stdout_truncated": stdout_truncated,
            "stderr_truncated": stderr_truncated,
            "error_type": error_type,
            "advice": advice_for_error(error_type),
            "parsed_json": redact_json(parsed_json, known_secrets) if parsed_json is not None else None,
            "parsed_json_error": parsed_json_error,
            "config_context": {
                "cwd": args.cwd,
                "timeout": args.timeout,
                "expect_json": args.expect_json,
                "used_temp_json_input": bool(temp_json_file),
            },
        }
    except FileNotFoundError as exc:
        result = {
            "success": False,
            "return_code": None,
            "duration_seconds": round(time.time() - started_at, 3),
            "service": args.service,
            "operation": args.operation,
            "command": [],
            "stdout": "",
            "stderr": str(exc),
            "stdout_truncated": False,
            "stderr_truncated": False,
            "error_type": None,
            "advice": "Install KooCLI or make sure `hcloud` is available in PATH.",
            "parsed_json": None,
            "parsed_json_error": None,
            "config_context": {
                "cwd": args.cwd,
                "timeout": args.timeout,
                "expect_json": args.expect_json,
                "used_temp_json_input": bool(temp_json_file),
            },
        }
    except subprocess.TimeoutExpired as exc:
        stdout_text = coerce_output_text(exc.stdout)
        stderr_text = coerce_output_text(exc.stderr)
        result = {
            "success": False,
            "return_code": None,
            "duration_seconds": round(time.time() - started_at, 3),
            "service": args.service,
            "operation": args.operation,
            "command": redact_command(exc.cmd if isinstance(exc.cmd, list) else [], known_secrets),
            "stdout": redact_text(stdout_text, known_secrets),
            "stderr": redact_text(stderr_text, known_secrets),
            "stdout_truncated": False,
            "stderr_truncated": False,
            "error_type": "TIMEOUT",
            "advice": "The command timed out. Consider increasing --timeout or KooCLI timeout arguments.",
            "parsed_json": None,
            "parsed_json_error": None,
            "config_context": {
                "cwd": args.cwd,
                "timeout": args.timeout,
                "expect_json": args.expect_json,
                "used_temp_json_input": bool(temp_json_file),
            },
        }
    finally:
        if temp_json_file and temp_json_file.exists():
            temp_json_file.unlink()

    if args.result_file:
        result_path = Path(args.result_file)
        result_path.parent.mkdir(parents=True, exist_ok=True)
        result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.parsed_json_file and result.get("parsed_json") is not None:
        parsed_path = Path(args.parsed_json_file)
        parsed_path.parent.mkdir(parents=True, exist_ok=True)
        parsed_path.write_text(
            json.dumps(result["parsed_json"], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    if args.pretty:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(result, ensure_ascii=False))
    return 0 if result["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
