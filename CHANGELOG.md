# Changelog

## 0.2.1 - 2026-05-29

- Strengthened large-output handling guidance for `IMS ListImages`, `ECS ListFlavors`, and `ECS ListFlavorSellPolicies`.
- Added explicit recommendations to use filtering, field projection, result files, parsed JSON files, and small summaries instead of sending full large JSON payloads back into the conversation.
- Updated IMS and ECS readiness playbooks with large-result handling patterns for image discovery, flavor selection, and flavor sell policy analysis.

## 0.2.0 - 2026-05-28

Full release note: see `RELEASE_NOTES.md`.

- Expanded from the v0.1 ECS-focused baseline to a data-driven multi-service skill covering ECS, VPC, RDS, IMS, EVS, EIP, ELB, NAT, KPS, IAM, CCE, CDN, DNS, SCM, OBS, and CES through registry-backed query/readiness/planner routes.
- Added `references/service-registry.json` plus `scripts/check_question_coverage.py` to validate generated question coverage, Excel E2E validation paths, CRUD risk labels, and executable route coverage.
- Added multi-service read-only execution tools: `hcloud_resource_discovery.py`, `hcloud_resource_query.py`, `hcloud_service_readiness.py`, `hcloud_readonly_smoke.py`, and `hcloud_resource_detail_probe.py`.
- Strengthened ECS completion semantics with ECS create count guards, placeholder checks, JSON-friendly command output, `hcloud_ecs_wait_job.py` job-only scope, and `hcloud_ecs_verify_active.py` ACTIVE resource verification.
- Added guarded change flows: EIP-specific Plan -> dry-run -> submit -> `ShowPublicip` verify, plus generic VPC/ELB/EVS/NAT/RDS/CDN/DNS/SCM Plan -> dry-run -> guarded submit -> resource Show* verify -> service smoke.
- Added OBS `hcloud obs`/obsutil adapters for bucket read-only checks and planner-only bucket/lifecycle/policy changes.
- Added structured `error_details` to `hcloud_safe_exec.py`, covering credential, permission, region/project, quota, parameter, not found, network, metadata, timeout, and cloud API failures.
- Added broad playbooks, service coverage docs, manual validation records, architecture contracts, and 94 passing unit tests.

## 0.1.0

- Initial hcloud/KooCLI skill with context inspection, safe execution, metadata lookup, ECS create planning, ECS job polling, references, playbooks, examples, and baseline tests.
