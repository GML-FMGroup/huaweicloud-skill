#!/usr/bin/env python3
"""Create a service-aware, non-executing Huawei Cloud change plan."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import hcloud_change_plan
import hcloud_resource_discovery


ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "references" / "service-registry.json"

SERVICE_VERIFICATION_HINTS = {
    "EIP": [
        "After create/bind/update, query ListPublicips or ShowPublicip and verify status, public IP address, bandwidth, and port/instance binding.",
        "For unbind/delete, verify the public IP is no longer bound or no longer appears in ListPublicips.",
    ],
    "VPC": [
        "After VPC/subnet/security group changes, query ListVpcs, ListSubnets, ListSecurityGroups, and ListSecurityGroupRules.",
        "Verify CIDR, gateway, VPC ID, subnet ID, direction, protocol, port range, and remote IP prefix.",
    ],
    "ELB": [
        "After load balancer/listener/pool/member changes, query ListLoadbalancers, ListListeners, ListPools, and ListMembers.",
        "Verify provisioning_status is ACTIVE and backend member operating_status is ONLINE before protocol testing.",
    ],
    "EVS": [
        "After volume create/attach/resize, query ListVolumes or ShowVolume and verify status, size, type, and attachment target.",
        "Guest filesystem formatting and mount checks require an ECS remote-command or SSH path before declaring application readiness.",
    ],
    "RDS": [
        "After instance/configuration/backup changes, query ListInstances and relevant Show* detail APIs.",
        "Verify instance status, engine version, flavor, storage, backup policy, endpoint, and parameter status.",
    ],
    "NAT": [
        "After NAT gateway or rule changes, query ListNatGateways and rule list APIs, then verify route and EIP dependencies.",
    ],
    "DNS": [
        "After DNS record changes, query ListRecordSets and verify zone ID, name, type, TTL, and values.",
    ],
    "SCM": [
        "After certificate operations, query ListCertificates and verify domain, status, expiration, and deployment target.",
    ],
    "CDN": [
        "After CDN domain or config changes, query ShowDomain/ListDomains and verify online status, origin, HTTPS, and cache config.",
    ],
    "CCE": [
        "After cluster or node changes, query ShowCluster/ListNodes and verify cluster availability and node readiness.",
    ],
}

SERVICE_CONTEXT_HINTS = {
    "EIP": [
        "Resolve VPC/port/ECS target before bind or unbind operations.",
        "Confirm bandwidth size, billing mode, and whether an idle EIP can be reused.",
    ],
    "VPC": [
        "Resolve region, project, VPC CIDR, subnet CIDR, availability zone, and security group intent.",
        "For security group rules, require direction, protocol, port range, and remote IP prefix.",
    ],
    "ELB": [
        "Resolve VPC, subnet, EIP/public/private network type, listener port, pool protocol, health monitor, and backend member address.",
    ],
    "EVS": [
        "Resolve volume type, size, AZ, target ECS ID, mount path, and whether guest filesystem actions are in scope.",
    ],
    "RDS": [
        "Resolve engine, version, flavor, storage, VPC/subnet/security group, backup retention, and credential handling.",
    ],
}

PREFERRED_DISCOVERY_OPERATIONS = {
    "EIP": "ListPublicips",
    "VPC": "ListVpcs",
    "ELB": "ListLoadbalancers",
    "EVS": "ListVolumes",
    "RDS": "ListInstances",
    "NAT": "ListNatGateways",
    "DNS": "ListRecordSets",
    "SCM": "ListCertificates",
    "CDN": "ListDomains",
    "CCE": "ListClusters",
}


def load_registry(path: Path = REGISTRY_PATH) -> dict[str, Any]:
    """Return the service registry."""
    return json.loads(path.read_text(encoding="utf-8"))


def registry_change_operations(registry: dict[str, Any], service: str) -> set[str]:
    """Return registered change operations for a service."""
    entry = registry.get("services", {}).get(service.upper(), {})
    return {str(item) for item in entry.get("change_operations", [])}


def service_entry(registry: dict[str, Any], service: str) -> dict[str, Any]:
    """Return a registry service entry or an empty dictionary."""
    return registry.get("services", {}).get(service.upper(), {})


def planner_args(args: argparse.Namespace, cli_region: str | None) -> SimpleNamespace:
    """Convert service planner args to hcloud_change_plan args."""
    return SimpleNamespace(
        service=args.service.upper(),
        operation=args.operation,
        region=cli_region,
        project_id=args.project_id,
        profile=args.profile,
        json_input_file=args.json_input_file,
        arg=args.arg,
        no_dryrun=args.no_dryrun,
    )


def build_service_plan(args: argparse.Namespace) -> dict[str, Any]:
    """Build a non-executing service-aware change plan."""
    registry = load_registry()
    service = args.service.upper()
    entry = service_entry(registry, service)
    if not entry:
        return {
            "success": False,
            "service": service,
            "operation": args.operation,
            "error": f"Service is not registered: {service}",
            "available_services": sorted(registry.get("services", {})),
        }

    registered_changes = registry_change_operations(registry, service)
    registered = args.operation in registered_changes
    preferred_discovery = PREFERRED_DISCOVERY_OPERATIONS.get(service)
    if registered_changes and not registered and not args.allow_unregistered:
        return {
            "success": False,
            "service": service,
            "operation": args.operation,
            "error": "Operation is not registered as a planned change for this service.",
            "available_change_operations": sorted(registered_changes),
            "next_actions": [
                "Use --allow-unregistered only after confirming the operation from hcloud help or official Huawei Cloud docs.",
                "Keep the plan non-executing until dry-run or equivalent validation has passed.",
            ],
        }

    cli_region, region_resolution = hcloud_resource_discovery.resolve_cli_region(args, entry)
    plan = hcloud_change_plan.build_plan(planner_args(args, cli_region))
    plan.update(
        {
            "success": True,
            "planning_only": True,
            "registered_change_operation": registered,
            "coverage": entry.get("coverage"),
            "service_known_limits": entry.get("known_limits", []),
            "service_context_hints": SERVICE_CONTEXT_HINTS.get(service, []),
            "service_verification_hints": SERVICE_VERIFICATION_HINTS.get(service, []),
            "resource_verifier": "scripts/hcloud_resource_verify.py",
            "read_only_smoke_plan": hcloud_resource_discovery.build_plan(
                SimpleNamespace(
                    service=service,
                    operation=preferred_discovery,
                    region=args.region,
                    project_id=args.project_id,
                    profile=args.profile,
                    limit=20,
                    execute=False,
                )
            ),
        }
    )
    if region_resolution:
        plan["region_resolution"] = region_resolution
    plan["next_steps"] = [
        *plan.get("next_steps", []),
        "Use hcloud_resource_verify.py against post-change JSON results before declaring the resource ready.",
        "Do not run submit commands from this plan without a separate explicit user confirmation.",
    ]
    return plan


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--service", required=True, help="Huawei Cloud service name.")
    parser.add_argument("--operation", required=True, help="Change operation name.")
    parser.add_argument("--region", help="Explicit cli-region for generated commands.")
    parser.add_argument("--project-id", help="Optional project_id for generated commands.")
    parser.add_argument("--profile", help="Optional cli-profile for generated commands.")
    parser.add_argument("--json-input-file", help="Optional JSON input file to pass via --cli-jsonInput.")
    parser.add_argument("--arg", action="append", default=[], help="Additional raw hcloud argument token.")
    parser.add_argument("--no-dryrun", action="store_true", help="Do not add --dryrun even when risk gate asks for it.")
    parser.add_argument("--allow-unregistered", action="store_true", help="Allow an operation not listed in service-registry.json.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    return parser.parse_args()


def main() -> int:
    """Build and print a service-aware change plan."""
    args = parse_args()
    result = build_service_plan(args)
    if args.pretty:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(result, ensure_ascii=False))
    return 0 if result["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
