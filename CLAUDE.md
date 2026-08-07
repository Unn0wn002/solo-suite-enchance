@AGENTS.md

# Claude Code adapter

- Load generated portable skills from `.claude/skills/`; regenerate them from `.agents/skills/` instead of editing mirrors.
- Use only intentional agents in `.claude/agents/`.
- Do not enable project hooks or MCP servers unless their audit decision is approved and their permissions are scoped.
- Run `python scripts/sync-agent-skills.py --check` before treating a mirror as current.
- Project memory lives in `.solo/` — read `handoff.md` and `tasks.md` at session start; update them when work state changes.
