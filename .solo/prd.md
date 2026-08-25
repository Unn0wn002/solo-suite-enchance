# PRD — Solo Suite Enchance

## Problem

AI coding clients can accumulate duplicated, platform-specific instructions with inconsistent routing, permissions, validation, and release behavior.

## Users

Developers and small teams using Claude Code, Codex, and/or Antigravity who want one portable, auditable workflow system.

## Goals

- Preserve platform-native capabilities while keeping cross-platform parity where intended.
- Route work through explicit roles, artifacts, permissions, and evidence gates.
- Keep project memory portable through the `.solo/` contract.
- Keep installation and security behavior explicit, reversible, and fail-closed.
- Prevent application source/data from being vendored into this distribution repository.

## Non-goals

- Hosting a product website or application.
- Persisting consuming-project databases, secrets, deployment metadata, or business data.
- Silently installing global tools, hooks, MCP servers, or credentials.

## Acceptance

The repository-level validators and native platform validation harnesses pass, generated mirrors remain synchronized, security remediation controls remain intact, and repository-boundary checks find no bundled application subsystem.
