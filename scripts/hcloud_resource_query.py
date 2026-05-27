#!/usr/bin/env python3
"""Build or run explicit-parameter read queries from the service registry."""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
from pathlib import Path
from typing import Any

import hcloud_change_plan
import hcloud_resource_discovery
from hcloud_meta_lookup import collect_template_dirs, load_operation_detail, normalize_token


ROOT = Path(__file__).resolve().parents[1]

CURATED_REQUIRED_PARAMS = {
    ("CCE", "ListNodes"): ("cluster_id",),
    ("CCE", "ShowCluster"): ("cluster_id",),
    ("CDN", "ShowDomain"): ("domain_id",),
    ("EIP", "ShowPublicip"): ("publicip_id",),
    ("ELB", "ListMembers"): ("pool_id",),
    ("RDS", "ShowConfiguration"): ("config_id",),
}
OPERATION_ALIASES = {
    ("RDS", "ShowConfigurationDetail"): "ShowConfiguration",
}
IGNORED_REQUIRED_PARAMS = {"x-auth-token", "project_id", "projectid"}


def parse_key_value(values: list[str], label: str) -> dict[str, str]:
    """Parse repeated KEY=VALUE arguments."""
    parsed: dict[str, str] = {}
    for value in values:
        if "=" not in value:
            raise ValueError(f"Invalid {label}, expected KEY=VALUE: {value}")
        key, raw = value.split("=", 1)
        key = normalize_param_name(key)
        raw = raw.strip()
        if not key or not raw:
            raise ValueError(f"Invalid {label}, expected non-empty KEY=VALUE: {value}")
        parsed[key] = raw
    return parsed


def normalize_param_name(value: str) -> str:
    """Normalize a KooCLI parameter name for comparison."""
    return value.strip().lstrip("-").replace("-", "_").lower()


def arg_param_name(value: str) -> str | None:
    """Extract the parameter name from a raw hcloud argument token."""
    token = value.strip()
    if not token.startswith("--"):
        return None
    return normalize_param_name(token.split("=", 1)[0])


def operation_scope(service_entry: dict[str, Any], operation: str) -> str | None:
    """Return whether an operation is a generic or explicit-parameter read query."""
    if operation in service_entry.get("resource_query_operations", []):
        return "resource_query"
    if operation in service_entry.get("query_operations", []):
        return "query"
    return None


def canonical_operation(service: str, operation: str) -> str:
    """Return the executable KooCLI operation name for a user-facing alias."""
    return OPERATION_ALIASES.get((service.upper(), operation), operation)


def metadata_required_params(service: str, operation: str) -> list[str]:
    """Return required non-header params from local KooCLI metadata when available."""
    meta_repo = Path.home() / ".hcloud" / "metaRepo"
    template_dir = collect_template_dirs(meta_repo).get(normalize_token(service))
    detail = load_operation_detail(template_dir, operation)
    if not isinstance(detail, dict):
        return []

    required: list[str] = []
    for param in detail.get("params", []):
        if not param.get("required"):
            continue
        if str(param.get("position", "")).lower() == "header":
            continue
        names = param.get("name", [])
        if not names:
            continue
        name = normalize_param_name(str(names[0]))
        if name in IGNORED_REQUIRED_PARAMS:
            continue
        required.append(name)
    return required


def required_params(service: str, operation: str) -> list[str]:
    """Return required explicit parameters for a read query."""
    params = set(metadata_required_params(service, operation))
    params.update(CURATED_REQUIRED_PARAMS.get((service.upper(), operation), ()))
    return sorted(params)


def provided_param_names(args: argparse.Namespace, params: dict[str, str]) -> set[str]:
    """Return normalized parameter names already provided by the user."""
    names = set(params)
    if args.project_id:
        names.add("project_id")
    for raw_arg in args.arg:
        name = arg_param_name(raw_arg)
        if name:
            names.add(name)
    return names


def build_command(
    args: argparse.Namespace,
    service_entry: dict[str, Any],
    params: dict[str, str],
    operation: str,
) -> tuple[list[str], dict[str, Any] | None]:
    """Build the safe_exec command for an explicit read query."""
    cli_region, region_resolution = hcloud_resource_discovery.resolve_cli_region(args, service_entry)
    command = [
        "python3",
        "scripts/hcloud_safe_exec.py",
        "--service",
        args.service.upper(),
        "--operation",
        operation,
        "--arg=--cli-output=json",
        "--expect-json",
    ]
    if args.profile:
        command.append(f"--arg=--cli-profile={args.profile}")
    if cli_region:
        command.append(f"--arg=--cli-region={cli_region}")
    if args.project_id:
        command.append(f"--arg=--project_id={args.project_id}")
    for key, value in sorted(params.items()):
        command.append(f"--arg=--{key}={value}")
    for raw_arg in args.arg:
        if not raw_arg.startswith("--"):
            raise ValueError(f"Raw --arg values must start with --: {raw_arg}")
        command.append(f"--arg={raw_arg}")
    return command, region_resolution


def execute_command(command: list[str], timeout: int) -> dict[str, Any]:
    """Run one safe_exec read query and parse its JSON output."""
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError:
        return {
            "success": False,
            "return_code": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "parsed_json": None,
            "parsed_json_error": "hcloud_safe_exec.py did not return valid JSON.",
        }


def build_plan(args: argparse.Namespace) -> dict[str, Any]:
    """Build or run an explicit-parameter read query plan."""
    registry = hcloud_resource_discovery.load_registry()
    service = args.service.upper()
    requested_operation = args.operation
    operation = canonical_operation(service, requested_operation)
    entry = registry.get("services", {}).get(service)
    if entry is None:
        return {
            "success": False,
            "service": service,
            "operation": operation,
            "requested_operation": requested_operation,
            "error": f"Service is not registered: {service}",
            "available_services": sorted(registry.get("services", {})),
        }

    scope = operation_scope(entry, operation)
    if scope is None:
        return {
            "success": False,
            "service": service,
            "operation": operation,
            "requested_operation": requested_operation,
            "error": "Operation is not registered as a read query for this service.",
            "available_query_operations": entry.get("query_operations", []),
            "available_resource_query_operations": entry.get("resource_query_operations", []),
        }

    risk = hcloud_change_plan.assess_risk(operation, dryrun_supported=False)
    if risk.level == "high" and not args.allow_sensitive_read:
        return {
            "success": False,
            "service": service,
            "operation": operation,
            "requested_operation": requested_operation,
            "operation_scope": scope,
            "risk": risk.to_dict(),
            "error": "Sensitive read operation requires --allow-sensitive-read.",
        }

    params = parse_key_value(args.param, "--param")
    required = required_params(service, operation)
    missing = [name for name in required if name not in provided_param_names(args, params)]
    if missing:
        return {
            "success": False,
            "service": service,
            "operation": operation,
            "requested_operation": requested_operation,
            "operation_scope": scope,
            "required_params": required,
            "provided_params": sorted(provided_param_names(args, params)),
            "missing_params": missing,
            "error": "Missing required explicit query parameters.",
        }

    command, region_resolution = build_command(args, entry, params, operation)
    result: dict[str, Any] = {
        "success": True,
        "mode": "execute" if args.execute else "plan",
        "service": service,
        "operation": operation,
        "operation_scope": scope,
        "coverage": entry.get("coverage"),
        "risk": risk.to_dict(),
        "required_params": required,
        "provided_params": sorted(provided_param_names(args, params)),
        "command": command,
        "command_shell": shlex.join(command),
    }
    if requested_operation != operation:
        result["requested_operation"] = requested_operation
    if region_resolution:
        result["region_resolution"] = region_resolution
    if args.execute:
        execution = execute_command(command, args.timeout)
        result["execution_success"] = execution.get("success", False)
        result["result"] = execution
        result["success"] = bool(execution.get("success"))
    return result


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--service", required=True, help="Registered Huawei Cloud service name.")
    parser.add_argument("--operation", required=True, help="Registered query or resource query operation.")
    parser.add_argument("--param", action="append", default=[], help="Explicit operation parameter as KEY=VALUE. Can be repeated.")
    parser.add_argument("--arg", action="append", default=[], help="Raw hcloud argument token such as --name=value. Can be repeated.")
    parser.add_argument("--region", help="Explicit cli-region for generated commands.")
    parser.add_argument("--project-id", help="Optional project_id for generated commands.")
    parser.add_argument("--profile", help="Optional cli-profile for generated commands.")
    parser.add_argument("--execute", action="store_true", help="Execute the read query through hcloud_safe_exec.py.")
    parser.add_argument("--timeout", type=int, default=120, help="Timeout for the executed command.")
    parser.add_argument("--allow-sensitive-read", action="store_true", help="Allow high-risk read operations such as password/private-key reads.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    args = parser.parse_args()
    if args.timeout < 1:
        parser.error("--timeout must be greater than 0.")
    return args


def main() -> int:
    """Build or run an explicit-parameter resource query."""
    args = parse_args()
    try:
        result = build_plan(args)
    except ValueError as exc:
        result = {"success": False, "error": str(exc)}
    if args.pretty:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(result, ensure_ascii=False))
    return 0 if result["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
