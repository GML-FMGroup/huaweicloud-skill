#!/usr/bin/env python3
"""Plan and optionally execute guarded non-ECS Huawei Cloud changes."""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
from types import SimpleNamespace
from typing import Any

import hcloud_resource_discovery
import hcloud_service_change_plan


def execute_command(command: list[str], timeout: int) -> dict[str, Any]:
    """Run one generated safe_exec command and parse its JSON result."""
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


def service_plan_args(args: argparse.Namespace) -> SimpleNamespace:
    """Convert guarded flow arguments to service change planner arguments."""
    return SimpleNamespace(
        service=args.service.upper(),
        operation=args.operation,
        region=args.region,
        project_id=args.project_id,
        profile=args.profile,
        json_input_file=args.json_input_file,
        arg=args.arg,
        no_dryrun=args.no_dryrun,
        allow_unregistered=args.allow_unregistered,
    )


def submit_guard_failure(args: argparse.Namespace, service_plan: dict[str, Any]) -> dict[str, Any] | None:
    """Return a structured guard failure when submit preconditions are not met."""
    if not args.execute_submit:
        return None
    if not args.confirm_submit:
        return {
            "success": False,
            "error": "Submit execution requires --confirm-submit.",
            "reason": "Cloud changes can affect cost, network reachability, availability, or data state.",
        }
    risk = service_plan.get("risk", {})
    if risk.get("dryrun_required") and not (args.execute_dryrun or args.skip_dryrun):
        return {
            "success": False,
            "error": "Submit execution requires a successful dry-run or --skip-dryrun.",
            "reason": "The planned operation is mutating and the risk gate marked dry-run as required.",
        }
    return None


def build_flow(args: argparse.Namespace) -> dict[str, Any]:
    """Build and optionally execute a guarded change flow."""
    service = args.service.upper()
    service_plan = hcloud_service_change_plan.build_service_plan(service_plan_args(args))
    result: dict[str, Any] = {
        "success": bool(service_plan.get("success")),
        "service": service,
        "operation": args.operation,
        "mode": "execute" if (args.execute_dryrun or args.execute_submit or args.execute_readiness) else "plan",
        "planning_only": True,
        "service_plan": service_plan,
        "submit_guard": {
            "execute_submit": args.execute_submit,
            "confirm_submit": args.confirm_submit,
            "skip_dryrun": args.skip_dryrun,
        },
        "next_steps": [
            "Review the service_plan risk, dry-run command, target project, and rollback expectations.",
            "Run --execute-dryrun first when the operation supports dry-run.",
            "Only use --execute-submit --confirm-submit after explicit user approval for this exact cloud change.",
            "Run --execute-readiness after submit to execute the read-only post-change smoke plan.",
        ],
    }
    if not service_plan.get("success"):
        return result
    if service_plan.get("delegated_planner"):
        result["success"] = False
        result["error"] = "This service uses a dedicated planner; use delegated_planner instead of the generic guarded flow."
        return result

    commands = service_plan.get("commands", {})
    if not commands.get("dryrun_or_plan") or not commands.get("submit"):
        result["success"] = False
        result["error"] = "Service plan did not produce dry-run/submit commands."
        return result

    guard_failure = submit_guard_failure(args, service_plan)
    if guard_failure:
        result["success"] = False
        result["submit_guard_failure"] = guard_failure
        return result

    dryrun_result: dict[str, Any] | None = None
    if args.execute_dryrun:
        dryrun_result = execute_command(commands["dryrun_or_plan"], args.timeout)
        result["dryrun"] = dryrun_result
        result["dryrun_command_shell"] = shlex.join(commands["dryrun_or_plan"])
        if not dryrun_result.get("success"):
            result["success"] = False
            result["next_steps"].append("Dry-run failed. Inspect dryrun.error_details/advice before changing arguments.")
            return result

    submit_result: dict[str, Any] | None = None
    if args.execute_submit:
        submit_result = execute_command(commands["submit"], args.timeout)
        result["submit"] = submit_result
        result["submit_command_shell"] = shlex.join(commands["submit"])
        result["planning_only"] = False
        if not submit_result.get("success"):
            result["success"] = False
            result["next_steps"].append("Submit failed. Inspect submit.error_details/advice before retrying.")
            return result

    readiness_plan = service_plan.get("read_only_smoke_plan")
    if readiness_plan:
        result["post_change_readiness_plan"] = readiness_plan
        if args.execute_readiness:
            readiness_result = hcloud_resource_discovery.execute_plan(readiness_plan, args.timeout)
            result["post_change_readiness"] = readiness_result
            result["success"] = bool(readiness_result.get("success"))
    elif args.execute_readiness:
        result["success"] = False
        result["post_change_readiness"] = {
            "success": False,
            "error": "Service plan did not include a read-only smoke plan.",
        }
    return result


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--service", required=True, help="Registered service name, for example VPC or ELB.")
    parser.add_argument("--operation", required=True, help="Registered change operation name.")
    parser.add_argument("--region", help="Explicit cli-region for generated commands.")
    parser.add_argument("--project-id", help="Optional project_id for generated commands.")
    parser.add_argument("--profile", help="Optional cli-profile for generated commands.")
    parser.add_argument("--json-input-file", help="Optional JSON body file for the change operation.")
    parser.add_argument("--arg", action="append", default=[], help="Additional raw hcloud argument token.")
    parser.add_argument("--no-dryrun", action="store_true", help="Do not add --dryrun to the generated dry-run command.")
    parser.add_argument("--allow-unregistered", action="store_true", help="Allow an operation not listed in the registry.")
    parser.add_argument("--execute-dryrun", action="store_true", help="Execute the generated dry-run command.")
    parser.add_argument("--execute-submit", action="store_true", help="Execute the generated submit command.")
    parser.add_argument("--confirm-submit", action="store_true", help="Required with --execute-submit.")
    parser.add_argument("--skip-dryrun", action="store_true", help="Allow submit without running dry-run first.")
    parser.add_argument("--execute-readiness", action="store_true", help="Execute the read-only post-change smoke plan.")
    parser.add_argument("--timeout", type=int, default=120, help="Timeout for executed safe_exec commands.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    args = parser.parse_args()
    if args.timeout < 1:
        parser.error("--timeout must be greater than 0.")
    return args


def main() -> int:
    """Build and optionally execute the guarded change flow."""
    args = parse_args()
    result = build_flow(args)
    if args.pretty:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(result, ensure_ascii=False))
    return 0 if result["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
