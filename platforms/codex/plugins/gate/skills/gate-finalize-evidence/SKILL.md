---
name: gate-finalize-evidence
description: "Evidence finalization — verify HEAD equals the recorded FINAL_SHA (run-state-v1, via update_run_state.py verify), then re-run every applicable category command through the canonical record_evidence.py workflow and produce all 14 self-attested gate-evidence records against that exact commit. Use when the user explicitly invokes $gate-finalize-evidence or asks for this gate finalize-evidence workflow."
---

# Gate Finalize Evidence

Follow this workflow using the user's supplied context. Preserve stated gates, evidence requirements, safety constraints, and output contracts.

Use $production-readiness-reviewer in finalizer mode. Apply it to the user's supplied arguments and surrounding request.

You are the LAST step before the launch gate. Records minted against intermediate commits are invalid by construction — this command exists so all evidence is generated once, after everything is final.

**Manual-only execution boundary:** this command may be invoked only by the
user. Never invoke it from another skill/agent and never chain preview into
execution automatically. For every verified category, run
`record_evidence.py --preview ...` first and show the complete plan to the
user. Stop and wait for explicit approval. Only then replace `--preview` with
`--confirm-execution <the exact preview token>`. A changed HEAD, tree, argv,
timeout, output cap, or network choice invalidates the token. Network commands
also require `--allow-network` in both steps. Run untrusted project commands in
an OS/container sandbox when available; the helper scrubs credentials and
common network-enabled tool settings, but does not claim to be an OS sandbox.
Commands are contained as a new POSIX session/process group or a Windows
kill-on-close Job Object. On timeout the whole container is terminated and
stdout/stderr readers must drain to EOF; any surviving descendant/reader
refuses the artifact and record. This blocks ordinary child leaks, but is not
a substitute for an OS/container sandbox against intentionally hostile code.

**Preconditions (verify, do not assume):**

1. Code, CI config, release plans, documentation, and project memory (`.solo/*.md`) are final and **committed**. `git status --porcelain` shows nothing outside the two generated runtime dirs (`.solo/gate-evidence/`, `.solo/run-state/`) — ONLY those two paths are ever excluded.
2. `.solo/gate-evidence/` AND `.solo/run-state/` are untracked/gitignored (the only supported workflow — the recorder refuses tracked runtime state, and re-checks HEAD and cleanliness again AFTER each command executes).
3. `FINAL_SHA` is recorded in UNTRACKED `.solo/run-state/<run_id>.json` — the formal **run-state-v1** contract (`schema/run-state-v1.schema.json`; exact lowercase keys `schema`, `run_id`, `base_sha`, `integration_sha`, `final_sha`), written ONLY by the freeze producer running `update_run_state.py advance final` (the helper derives the SHA from `git rev-parse HEAD` itself, enforces monotonic transitions, and freezes `final_sha`). Never a tracked file — a commit cannot contain its own SHA. Verify mechanically; a nonzero exit stops this command:

```bash
python3 "<skill-root>/../production-readiness-reviewer/scripts/update_run_state.py" \
    --root . --run-id "$RUN_ID" verify final
```

4. Read `HEAD:.solo/project.md` and require exactly one standalone `Project profile: <recognized-slug>` line. The selected `--profile` must equal that committed value. Missing, malformed, ambiguous, symlink-backed, or working-tree-only profile data is a hard stop.

**Then, for each of the 14 categories** (product, architecture, design, frontend, backend, database, security, testing, performance, seo, analytics, deployment, monitoring, documentation):

- If the applicability matrix permits N/A for the committed project profile AND the category genuinely does not apply, use the recorder's canonical N/A operation — never write N/A JSON by hand in the supported workflow. The tool derives the commit and canonical profile from Git objects, requires `--profile-source` to remain exactly `.solo/project.md`, rejects CLI/profile mismatches and the seven mandatory categories — product, architecture, security, testing, deployment, monitoring, documentation are NEVER N/A — and generates the timestamps. The required `recorder` field is a copyable self-attested format label, not cryptographic proof that the helper wrote the file:

```bash
python3 "<skill-root>/../production-readiness-reviewer/scripts/record_evidence.py" \
    --not-applicable --category seo --project "<repo name>" --environment production \
    --root . --reviewer "evidence finalizer" --run-id "$RUN_ID" \
    --profile api-service --profile-source .solo/project.md \
    --reason "API service exposes no public HTML pages; nothing to index" \
    --checked "router exposes JSON endpoints only" --checked "no robots.txt/sitemap by design"
```

- Otherwise run the category's policy-validated command through the recorder (it derives HEAD and the committed-tree digest itself and captures the REAL exit code — never write records by hand):

```bash
python3 "<skill-root>/../production-readiness-reviewer/scripts/record_evidence.py" \
    --category testing --project "<repo name>" --environment production \
    --root . --reviewer "evidence finalizer" --run-id "$RUN_ID" --preview -- \
    python3 -m pytest -q
# STOP. Show the preview and wait for explicit user approval. Then rerun the
# identical command with --confirm-execution <PREVIEW_TOKEN> in place of
# --preview. Never infer approval.
# Document-backed categories (product, architecture, design, documentation)
# use the bundled CATEGORY-SPECIFIC content check AS THE RECORDED COMMAND
# (required headings, substantive content, placeholder rejection, required
# identifier/decision fields) — always wrapped through record_evidence.py,
# NEVER run standalone as finalization (a bare gate_policy.py run produces
# no record and proves nothing to the gate):
python3 "<skill-root>/../production-readiness-reviewer/scripts/record_evidence.py" \
    --category product --project "<repo name>" --environment production \
    --root . --reviewer "evidence finalizer" --run-id "$RUN_ID" --preview -- \
    python3 "<skill-root>/../../lib/gate_policy.py" \
    verify-artifact product --root .
# deployment and monitoring are NOT document-backed: release.md /
# monitoring.md content alone never passes them. Deployment evidence binds
# the DEPLOYED RESULT to FINAL_SHA: a CI run bound to HEAD + success, or a
# bounded-timeout curl of the COMMITTED `version-endpoint:` from
# .solo/stack.md whose response must contain FINAL_SHA:
python3 "<skill-root>/../production-readiness-reviewer/scripts/record_evidence.py" \
    --category deployment --project "<repo name>" --environment production \
    --root . --reviewer "evidence finalizer" --run-id "$RUN_ID" \
    --allow-network --gh-config-dir "<external gh config directory>" --preview -- \
    gh run view <RUN_ID_NUMBER> --exit-status --json headSha,conclusion,status
# gh authentication is explicit: point --gh-config-dir at an existing
# OUTSIDE-THE-REPOSITORY GitHub CLI config directory containing hosts.yml
# (for example, the directory selected when running gh auth login with
# GH_CONFIG_DIR set). The recorder never inherits GH_TOKEN/GITHUB_TOKEN and
# never reads, copies, hashes, prints, or records hosts.yml/token contents. It
# exposes only GH_CONFIG_DIR to gh; preview/evidence show an opaque profile id,
# not the path. The directory and hosts.yml must be real/non-linked. On POSIX,
# they must be current-user-owned, the directory not group/world-writable, and
# hosts.yml mode 0600. On Windows, preserve a current-user-only ACL: the
# recorder rejects reparse points but cannot prove Windows ACL correctness.
# Monitoring evidence uses the COMMITTED `health-endpoint:` with a bounded
# timeout; the response must be an explicit health contract (JSON
# status/state/health, or the committed `health-expect:` marker) — a
# generic homepage response is refused:
python3 "<skill-root>/../production-readiness-reviewer/scripts/record_evidence.py" \
    --category monitoring --project "<repo name>" --environment production \
    --root . --reviewer "evidence finalizer" --run-id "$RUN_ID" \
    --allow-network --preview -- \
    curl -sSf -m 10 https://<the-committed-health-endpoint>/health
# when no CI run / live endpoint is reachable, the category stays
# UNVERIFIED and the gate is BLOCKED — report it; do not substitute a
# document check.
```

A failing command produces a record with its REAL nonzero exit code — report it as a blocker; do not re-run until the underlying problem is fixed and committed (which changes FINAL_SHA — `update_run_state.py` refuses to rewrite a frozen `final_sha`, so a new freeze means a new run id and finalization restarts).

**After FINAL_SHA, nothing tracked may change.** Only untracked `.solo/gate-evidence/` and `.solo/run-state/` files may be created. If any category command mutates tracked files, that is a defect to report — the recorder will refuse further records until the tree is clean again.

Finish by running the checker (it derives HEAD itself):

```bash
python3 "<skill-root>/../production-readiness-reviewer/scripts/check_evidence.py" .solo/gate-evidence \
    --root . --environment production --project "<repo name>" --profile <project profile>
```

## Output
End with exactly:
- **FINAL_SHA** — the verified commit, and proof (`update_run_state.py verify final` output)
- **Records produced** — per category: verified (command_id + exit code) or N/A (matrix cell, minted via --not-applicable)
- **Failures** — categories whose commands exited nonzero, with the artifact path
- **Checker result** — the check_evidence.py summary line
- **Next skill** — `$gate-production-ready` when the checker exits 0; otherwise the fix that unblocks the failing category

## User-facing output contract

Outside required machine-readable artifacts, end every response with exactly these seven labeled sections: **Summary**, **Findings / Work done**, **Risks**, **Required fixes**, **Suggested tasks** (stable T-IDs for `.solo/tasks.md`), **Verification**, and **Next skill** (the exact `$skill` invocation).
