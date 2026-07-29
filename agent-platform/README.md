# Agent Extension Platform

This directory coordinates a portable, profile-scoped extension system.

- Canonical skills: `.agents/skills/`
- Generated Claude mirrors: `.claude/skills/`
- Shared role definitions: `agent-platform/roles/`
- Generated role adapters: `.claude/agents/` and `.agents/agents/`
- Phase profiles: `agent-platform/profiles/`
- Provenance and decisions: `manifest.yaml` and `agent-extensions.lock.json`
- Audit evidence and reports: `docs/agent-audit/`

Start with `planning`; switch to the smallest phase profile that owns the next artifact. `full-audit` is for
extension maintenance only and still caps active skills. Graphify is optional and installed only through the
explicit project-local bootstrap; rejected tools are never installed or activated.

## Commands without Make

```powershell
python scripts/sync-agent-skills.py
python scripts/validate-agent-skills.py
python scripts/validate-agent-platform.py
python scripts/check-agent-licenses.py
python scripts/check-agent-links.py
python scripts/bootstrap-security-tools.py --check
python scripts/check-high-risk-remediations.py
python scripts/agent-security.py --npm-audit --full-scanners --write-evidence
python scripts/agent-compat.py --write
python scripts/agent-token-report.py --write
python scripts/agent-update-check.py
python scripts/bootstrap-graphify.py --check
```

Every generator supports `--check`, `--dry-run`, or both where mutation is possible. Read the installation and
update guides before changing source pins.
