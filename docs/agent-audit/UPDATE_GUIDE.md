# Agent Extension Update Guide

Updates are audit events, not installs.

1. Run `python scripts/agent-update-check.py` to compare pinned commits and releases without changing the lock.
2. Review upstream ownership, license, release notes, default branch, and exact diff from the pinned commit.
3. Run `python scripts/audit-agent-sources.py --dry-run` to inspect clone targets and safety policy.
4. Refresh in the isolated ignored directory with `python scripts/audit-agent-sources.py --refresh`. This clones
   source only; it does not execute source code, hooks, submodules, installers, or lifecycle scripts.
5. Review `docs/agent-audit/evidence/source-audits.json` and any focused evidence files.
6. Rebuild deterministically with `python scripts/build-agent-audit.py --write`.
7. Synchronize generated adapters with `python scripts/sync-agent-skills.py`.
8. Run `make agent-validate` or the Python equivalents in `agent-platform/README.md`.
9. Review the Git diff for license changes, permissions, credentials, hooks, MCP activation, binaries, caches,
   secrets, and unpinned references.
10. Remove isolated clones with `python scripts/agent-clean-temp.py --dry-run`, then run it without `--dry-run`.
11. Update Graphify incrementally only after the final source state is stable.

Never update a pin to floating `main`, `master`, or `latest`. Unknown licenses are blocked, and high-risk
capabilities stay disabled until a human approves the new permission and trust boundary.
