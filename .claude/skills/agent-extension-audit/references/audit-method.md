# Audit method

## Evidence fields

For each source record URL, resolved URL, owner, repository, default branch, pinned commit, release/tag, meaningful update, maintainer status, archive status, license and rights, manifests, lock files, install methods, dependencies, lifecycle scripts, executable scripts, Git/agent hooks, MCP definitions and permissions, environment and credential needs, network and filesystem behavior, telemetry, external services, destructive operations, prompt-injection patterns, determinism, tests, documentation alignment, risk, classification, platform statuses, adapter, and recommendation.

## Decisions

- `LOW`: bounded instructions or reviewed local behavior with no privileged automatic execution.
- `MEDIUM`: material local/network/tool behavior that is explicit and scoped.
- `HIGH`: broad access, automatic execution, unsafe defaults, or unresolved material supply-chain behavior. Keep disabled.
- `CRITICAL`: confirmed destructive, exfiltration, credential-theft, verification-bypass, or equivalent behavior. Quarantine.
- `UNKNOWN`: evidence or license is insufficient. Do not copy.

Use exactly one primary classification and one compatibility status per platform. Preserve evidence for blocked entries and continue.

## Safe inspection

Use shallow, filtered, non-recursive clones. Read manifests, locks, scripts, code, configuration, and tests directly. Do not execute package managers, project binaries, hooks, MCP servers, generated code, or installer commands during source review. Scanner absence is a limitation, not evidence of safety.

## Promotion gate

A capability can enter the canonical library only when its source and path are pinned, its license permits the intended use or the implementation is an original wrapper/reference, its security decision is accepted, its trigger does not duplicate another canonical skill, its adapters are deterministic, and its validators pass.
