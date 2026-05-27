# Changelog

## 0.2.0 - 2026-05-27

- Added structured redaction for `hcloud_safe_exec.py` parsed JSON and parsed JSON file output.
- Added ECS ACTIVE verification with `scripts/hcloud_ecs_verify_active.py`.
- Clarified that `scripts/hcloud_ecs_wait_job.py` verifies only job terminal state.
- Added conservative ECS create count guard, embedded placeholder detection, JSON-friendly generated commands, and shell command output.
- Added `references/service-registry.json` and list-only discovery through `scripts/hcloud_resource_discovery.py`.
- Added lightweight shared execution schemas, generic change risk planning, JSONL run journal, and materials drift check.
- Added architecture contract, CLI mock, metadata parsing, and ECS ACTIVE verifier tests.

## 0.1.0

- Initial hcloud/KooCLI skill with context inspection, safe execution, metadata lookup, ECS create planning, ECS job polling, references, playbooks, examples, and baseline tests.
