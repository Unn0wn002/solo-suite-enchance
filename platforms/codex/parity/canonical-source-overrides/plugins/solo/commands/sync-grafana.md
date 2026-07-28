---
description: Sync project health from .solo/ into a Grafana dashboard and annotations (interpreting "Grapify" as Grafana). External write — dry-run first, confirmation required.
argument-hint: [optional Grafana URL or dashboard name, or --dry-run/--apply]
disable-model-invocation: true
---
Use the memory-sync skill in Grafana mode. $ARGUMENTS

Read .solo/ and push project HEALTH to Grafana: generate/refresh a dashboard JSON with panels
for task counts (open/done/blocked), tasks-done-over-time, open audit findings by severity
(from audit tasks written back by site-doctor / stack audits), and a blockers table; and post
annotations for releases, audits, and key decisions. If a Grafana connector/MCP or API is
available, create/update the dashboard by UID and post annotations directly — idempotently,
no duplicates; otherwise emit the dashboard JSON and annotation payloads to import.

SAFETY CONTRACT (mandatory):
- .solo/config.md stores ONLY the Grafana URL, dashboard UID/datasource name, and the NAME
  of the environment variable holding the token (e.g. token_env: GRAFANA_API_TOKEN). The
  token value comes from that environment variable or the OS secret store — never from a
  file, never pasted into chat. Ensure .solo/config.md is in .gitignore (add it if missing).
- DEFAULT IS DRY-RUN: show what would be created/updated (dashboard diff, annotation list)
  and make NO external write until the user explicitly confirms with --apply / "apply".
- Present the dry run as a clear PREVIEW and require EXPLICIT CONFIRMATION before every
  external write, even when credentials and a connector are already available.
- Never include secrets, .solo/config.md, or .env values in dashboards or annotations.
- Redact tokens and Authorization headers from all output, including errors. Report the dashboard UID/URL (or JSON) and annotations posted.
Note: this reads "Grapify" as Grafana - if a different tool was meant, the same read->transform
->write-idempotently structure ports to it; just say which.

## Output
End with the 7-part contract: **Summary · Findings/Work done · Risks · Required fixes · Suggested tasks** (→ `.solo/tasks.md`, stable T-IDs) **· Verification · Next command** (exact slash command).
