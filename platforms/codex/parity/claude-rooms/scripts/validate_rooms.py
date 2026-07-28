#!/usr/bin/env python3
r"""validate_rooms.py — static validator for solo-suite/agentroom-v1 templates.

VALIDATION ORDER (v1.0.13):
  1. The ACTUAL JSON Schema (../schema/agentroom-v1.schema.json) is applied
     first — with the `jsonschema` library when importable, otherwise with a
     built-in strict draft-07 subset evaluator that covers every construct
     the schema uses (type, const, enum, required, properties,
     additionalProperties, items, minItems, minLength, pattern, minimum,
     oneOf). Malformed root, seat, stage, run, profile, gate-map, worktrees,
     or loop types produce VALIDATION ERRORS — never exceptions.
  2. Semantic rules that JSON Schema cannot express run only on
     schema-valid documents.

SEMANTIC RULES:
  * unique seat AND stage ids; every seat belongs to exactly one stage
    (memory steward exempt — it is OUT-OF-BAND, running after every stage)
  * run identity is REQUIRED (run.id_prefix + run.id_required: true) and
    profiles/applies_to use only the six recognized profile enums
  * GRAPH MODEL (the one documented model): nodes are the seats active for
    the profile under evaluation (no applies_to, or the profile listed;
    the steward is out-of-band). Edges are seat -> each handoff_to target
    (string or list), contracted through inactive seats. Entry = the active
    seats of the first active stage. Exit = THE single exit-gate executor.
    Every active seat must be reachable from an entry seat AND reach the
    exit seat; only the exit seat (and steward) may have a null handoff.
    Handoffs must point to LATER stages — repetition only via the bounded
    `loop` block. The model is evaluated once profile-free and once per
    declared profile.
  * EXACTLY ONE seat executes the exit gate (its `commands` contain
    `exit_gate`). Zero executors or several are both errors — there is NO
    last-stage fallback.
  * gate evidence (`gate_requires`): the executor must read every required
    artifact (exact string or identical glob), and every requirement needs
    an EARLIER producer — a seat in a STRICTLY EARLIER stage whose concrete
    declared write/proposal equals the requirement or fnmatch()es a
    requirement glob. Path matching is exact/fnmatch ONLY: a descriptive
    directory string like ".solo/gate-evidence/ (notes)" does NOT satisfy
    "*.json". The executor's own writes never satisfy its own gate; the
    steward counts as a producer only for the artifacts it `owns`.
  * gate_evidence_map: keys must be gate categories; when the exit gate is
    /gate:production-ready the map must cover all 14 categories, and each
    category needs an earlier producer of the CONCRETE file
    .solo/gate-evidence/<category>.json (or a documented
    assumes_preexisting entry). Per profile, a category whose producers are
    all inactive is an error unless the applicability matrix (NA_ALLOWED —
    kept in sync with check_evidence.py) permits N/A for that
    category/profile; the seven MANDATORY categories always need an active
    producer.
  * WORKTREE EXECUTION CONTRACT: any room with a `workspace: "worktree:…"`
    seat must declare a `worktrees` block — base SHA recorded BEFORE
    spawning (Claude worktree agents branch from the DEFAULT branch, not
    the parent session HEAD), the builder return payload (worktree_path,
    branch, commit_sha, tests, proposal), the proposal transport, the
    integration seat + mode (merge-exact-shas | checkout-exact-sha) in a
    stage after every worktree seat, and the seats that must verify the
    exact integration SHA — a list that must include the exit-gate
    executor and every verifying seat at/after the integration stage.
  * one writer per artifact per stage over EFFECTIVE writes (declared +
    implicit command writes, see IMPLICIT_WRITES); memory steward
    ownership + proposals; artifact locks; workspace ownership; same-stage
    read-after-write; agent existence; command existence; bounded loops.
  * READ PROVENANCE: every concrete .solo/ read must be produced by an
    earlier stage (or the reading seat itself, or the unstaged steward for
    its owned files), covered by assumes_preexisting, or — for
    .solo/run-state/ reads — legitimized by a structured SHA contract
    (worktrees.base_sha or evidence.freeze, both orchestrator-produced).
  * EVIDENCE LIFECYCLE (production-ready rooms): a REQUIRED structured
    evidence.freeze contract (orchestrator commits everything, verifies a
    clean tree, records FINAL_SHA in untracked run-state) sitting
    IMMEDIATELY between its after_stage and the finalizer's stage; the
    finalizer seat must map to a REAL shipped agent (an agent_note is not
    executable); with a memory steward,
    memory_steward.active_through_stage is REQUIRED and must name a stage
    STRICTLY before the finalizer's, so a runner can never invoke the
    steward at or after finalize; with worktrees, finalize/gate seats
    verify FINAL_SHA via worktrees.verify_at_final_sha while
    verify_at_integration_sha covers the review->release band only.

Usage: python3 validate_rooms.py [room.json ...] [--suite ROOT]
Defaults: the agentsrooms/*.json shipped next to this script; suite root is
auto-detected by walking up to .claude-plugin/marketplace.json.
Exit 0 = all valid, 1 = problems. Stdlib only (jsonschema used when
importable)."""
import argparse
import fnmatch
import glob
import json
import os
import re
import sys

try:
    import jsonschema as _jsonschema  # optional; mini evaluator otherwise
except Exception:                     # pragma: no cover
    _jsonschema = None

CMD_RE = re.compile(r"^/[a-z][a-z0-9-]*:[a-z][a-z0-9-]*$")
SEAT_KEYS = ("id", "role", "reads", "writes", "commands", "deliverable",
             "handoff_check")
RECOGNIZED_PROFILES = {"public-marketing-site", "saas-application",
                       "e-commerce", "internal-application", "api-service",
                       "library-package"}
CATEGORIES = {"product", "architecture", "design", "frontend", "backend",
              "database", "security", "testing", "performance", "seo",
              "analytics", "deployment", "monitoring", "documentation"}
# Kept in agreement with check_evidence.py (tests assert equality).
MANDATORY = {"product", "architecture", "security", "testing",
             "deployment", "monitoring", "documentation"}
NA_ALLOWED = {
    "design": {"api-service", "library-package"},
    "frontend": {"api-service", "library-package"},
    "backend": {"public-marketing-site", "library-package"},
    "database": {"public-marketing-site", "library-package"},
    "performance": {"library-package"},
    "seo": {"internal-application", "api-service", "library-package"},
    "analytics": {"internal-application", "api-service", "library-package"},
}
BUILDER_PAYLOAD_REQUIRED = {"worktree_path", "branch", "commit_sha",
                            "tests", "proposal"}

# ---------------------------------------------------------------------------
# Implicit shared-memory writes of suite commands (documented ground truth:
# each command's / skill's "Project memory integration" contract). A pattern
# is either an exact command or a prefix ending in '*'.
IMPLICIT_WRITES = {
    "/site-doctor:*":       [".solo/tasks.md", ".solo/decisions.md", ".solo/handoff.md"],
    "/stack:audit-*":       [".solo/tasks.md", ".solo/handoff.md"],
    "/stack:connector-check": [".solo/stack.md", ".solo/tasks.md", ".solo/decisions.md"],
    "/stack:intake":        [".solo/stack.md", ".solo/decisions.md"],
    "/project:prd":         [".solo/prd.md", ".solo/decisions.md"],
    "/project:architecture": [".solo/architecture.md", ".solo/decisions.md"],
    "/project:task-breakdown": [".solo/tasks.md"],
    "/spec:feature-brief":  [".solo/prd.md"],
    "/spec:acceptance":     [".solo/prd.md"],
    "/spec:api-contract":   [".solo/api-contract.md"],
    "/spec:data-contract":  [".solo/data-contract.md"],
    "/spec:env-contract":   [".solo/env-contract.md"],
    "/design:*":            [".solo/design.md", ".solo/decisions.md"],
    "/dev:implement-feature": [".solo/tasks.md", ".solo/decisions.md"],
    "/dev:fix-bug":         [".solo/tasks.md", ".solo/decisions.md"],
    "/dev:refactor-code":   [".solo/tasks.md", ".solo/decisions.md"],
    "/dev:code-review":     [".solo/tasks.md", ".solo/decisions.md"],
    "/test:*":              [".solo/tests.md", ".solo/tasks.md"],
    "/browser:*":           [".solo/bugs.md", ".solo/tasks.md"],
    "/security:abuse-cases": [".solo/risks.md", ".solo/tasks.md", ".solo/decisions.md", ".solo/handoff.md"],
    "/security:authz-matrix": [".solo/risks.md", ".solo/tasks.md", ".solo/decisions.md"],
    "/security:threat-model": [".solo/risks.md", ".solo/tasks.md", ".solo/decisions.md", ".solo/handoff.md"],
    "/release:ci-setup":    [".solo/tasks.md", ".solo/decisions.md", ".solo/handoff.md"],
    "/release:preflight":   [".solo/release.md", ".solo/tasks.md", ".solo/decisions.md", ".solo/handoff.md"],
    "/release:deploy-plan": [".solo/release.md", ".solo/tasks.md", ".solo/decisions.md", ".solo/handoff.md"],
    "/release:rollback-plan": [".solo/release.md", ".solo/tasks.md", ".solo/decisions.md", ".solo/handoff.md"],
    "/gate:before-code":    [".solo/risks.md", ".solo/tasks.md"],
    "/gate:before-merge":   [".solo/risks.md", ".solo/tasks.md"],
    "/gate:before-deploy":  [".solo/risks.md", ".solo/tasks.md"],
    "/gate:score-project":  [".solo/project.md", ".solo/risks.md", ".solo/tasks.md", ".solo/decisions.md"],
    "/git:sync-issues":     [".solo/tasks.md"],
    "/growth:*":            [".solo/tasks.md"],
    "/repo:*":              [".solo/tasks.md", ".solo/decisions.md"],
    "/docs:*":              [".solo/handoff.md"],
    "/ai:review-output":    [".solo/tasks.md"],
    "/solo:handoff-memory": [".solo/handoff.md"],
    "/solo:end-session":    [".solo/handoff.md", ".solo/tasks.md"],
    "/solo:next-step":      [".solo/tasks.md"],
}
# monitoring is a site-doctor command with its own primary artifact
IMPLICIT_EXTRA = {"/site-doctor:monitoring": [".solo/monitoring.md"]}

TASK_ID_RE = re.compile(r"\bT-\d+\b")


# ===========================================================================
# JSON Schema application (step 1)
# ===========================================================================
def load_schema(schema_path=None):
    path = schema_path or os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "schema",
        "agentroom-v1.schema.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _type_ok(value, t):
    m = {"object": dict, "array": list, "string": str, "boolean": bool,
         "null": type(None)}
    if t == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if t == "number":
        return (isinstance(value, (int, float))
                and not isinstance(value, bool))
    if t in m:
        if t == "boolean":
            return isinstance(value, bool)
        return isinstance(value, m[t]) and not (
            t != "boolean" and isinstance(value, bool))
    return True


def _mini_validate(value, schema, path, errors):
    """Strict draft-07 SUBSET evaluator — covers exactly the constructs used
    by agentroom-v1.schema.json. Appends 'path: message' strings."""
    if not isinstance(schema, dict):
        return
    where = path or "$"
    if "const" in schema:
        if value != schema["const"]:
            errors.append("%s: must be %r (got %r)"
                          % (where, schema["const"], value))
            return
    if "enum" in schema:
        if value not in schema["enum"]:
            errors.append("%s: %r is not one of %s"
                          % (where, value, schema["enum"]))
            return
    if "oneOf" in schema:
        matches, sub_errs = 0, []
        for i, sub in enumerate(schema["oneOf"]):
            e = []
            _mini_validate(value, sub, path, e)
            if not e:
                matches += 1
            else:
                sub_errs.append("[branch %d] %s" % (i, e[0]))
        if matches != 1:
            errors.append("%s: matches %d of the oneOf branches (need "
                          "exactly 1): %s"
                          % (where, matches, "; ".join(sub_errs[:2])))
        return
    t = schema.get("type")
    if t is not None:
        types = t if isinstance(t, list) else [t]
        if not any(_type_ok(value, x) for x in types):
            errors.append("%s: expected type %s, got %s"
                          % (where, "/".join(types), type(value).__name__))
            return
    if isinstance(value, str):
        if "minLength" in schema and len(value) < schema["minLength"]:
            errors.append("%s: string shorter than minLength %d"
                          % (where, schema["minLength"]))
        if "pattern" in schema and not re.search(schema["pattern"], value):
            errors.append("%s: %r does not match pattern %s"
                          % (where, value, schema["pattern"]))
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append("%s: %s is below minimum %s"
                          % (where, value, schema["minimum"]))
    if isinstance(value, list):
        if "minItems" in schema and len(value) < schema["minItems"]:
            errors.append("%s: fewer than minItems %d"
                          % (where, schema["minItems"]))
        if "items" in schema:
            for i, item in enumerate(value):
                _mini_validate(item, schema["items"],
                               "%s[%d]" % (where, i), errors)
    if isinstance(value, dict):
        for k in schema.get("required", ()):
            if k not in value:
                errors.append("%s: missing required property %r" % (where, k))
        props = schema.get("properties", {})
        for k, v in value.items():
            if k in props:
                _mini_validate(v, props[k], "%s.%s" % (where, k), errors)
            elif isinstance(schema.get("additionalProperties"), dict):
                _mini_validate(v, schema["additionalProperties"],
                               "%s.%s" % (where, k), errors)
            elif schema.get("additionalProperties") is False:
                errors.append("%s: unknown property %r (additionalProperties "
                              "is false)" % (where, k))


def schema_errors(data, schema):
    """Apply the actual JSON Schema; return a list of error strings."""
    if _jsonschema is not None:
        try:
            validator = _jsonschema.Draft7Validator(schema)
            out = []
            for e in sorted(validator.iter_errors(data),
                            key=lambda e: list(e.absolute_path)):
                loc = "$" + "".join(
                    "[%d]" % p if isinstance(p, int) else ".%s" % p
                    for p in e.absolute_path)
                out.append("%s: %s" % (loc, e.message.split("\n")[0][:200]))
            return out
        except Exception as e:      # never crash on validator internals
            return ["schema application failed: %s" % e]
    errors = []
    try:
        _mini_validate(data, schema, "$", errors)
    except RecursionError:
        errors.append("$: document too deeply nested to validate")
    return errors


# ===========================================================================
# helpers
# ===========================================================================
# Commands that run AFTER the freeze commit and write ONLY untracked
# runtime state — the /gate:* implicit-risks rule must not apply to them.
# /gate:production-ready is OUTPUT-ONLY post-freeze: its verdict and
# blockers live in its output, and tracked risk/task updates belong BEFORE
# the freeze (a blocked verdict reopens work in the NEXT cycle).
NO_IMPLICIT_WRITES = {"/gate:finalize-evidence", "/gate:production-ready"}

# Paths that are untracked BY DESIGN (gitignored runtime state): writes to
# these never count as tracked writes in post-finalizer rules.
UNTRACKED_RUNTIME_PREFIXES = (".solo/gate-evidence", ".solo/run-state")


def _untracked_runtime(path):
    if not isinstance(path, str):
        return False
    p = path.strip()
    return any(p == d or p.startswith(d + "/")
               for d in UNTRACKED_RUNTIME_PREFIXES)


def implicit_writes_of(commands):
    out = set()
    for c in commands or []:
        if not isinstance(c, str):
            continue
        if c in NO_IMPLICIT_WRITES:
            continue
        for pat, files in IMPLICIT_WRITES.items():
            if pat.endswith("*"):
                if c.startswith(pat[:-1]):
                    out.update(files)
            elif c == pat:
                out.update(files)
        for pat, files in IMPLICIT_EXTRA.items():
            if c == pat:
                out.update(files)
    return out


def check_tasks_file(text):
    """Duplicate task-ID detector for .solo/tasks.md content (the steward's
    uniqueness contract). Returns sorted list of duplicated T-IDs."""
    seen, dups = set(), set()
    for tid in TASK_ID_RE.findall(text or ""):
        if tid in seen:
            dups.add(tid)
        seen.add(tid)
    return sorted(dups)


def find_suite(start):
    d = os.path.abspath(start)
    while True:
        if os.path.isfile(os.path.join(d, ".claude-plugin", "marketplace.json")):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent


def known_agents(suite_root):
    if not suite_root:
        return None
    names = {os.path.basename(p)[:-3] for p in
             glob.glob(os.path.join(suite_root, "plugins", "*", "agents", "*.md"))}
    return names or None


_ISOLATION_RE = re.compile(r"(?m)^isolation:\s*(\S+)\s*$")


def agent_isolation(suite_root):
    """{agent-name: isolation-value-or-None} parsed from the shipped agent
    frontmatter — used to reject worktree seats mapped to agents that do
    not declare `isolation: worktree`."""
    if not suite_root:
        return None
    out = {}
    for p in glob.glob(os.path.join(suite_root, "plugins", "*", "agents",
                                    "*.md")):
        with open(p, encoding="utf-8") as f:
            text = f.read()
        m = _ISOLATION_RE.search(text.split("\n---", 2)[0] if
                                 text.startswith("---") else "")
        out[os.path.basename(p)[:-3]] = m.group(1) if m else None
    return out or None


def known_commands(suite_root):
    if not suite_root:
        return None
    cmds = set()
    for p in glob.glob(os.path.join(suite_root, "plugins", "*", "commands", "*.md")):
        p = p.replace(os.sep, "/")
        cmds.add("/%s:%s" % (p.split("/")[-3], os.path.basename(p)[:-3]))
    return cmds or None


def manual_only_commands(suite_root):
    """Return commands disabled for model invocation by their metadata.

    The command frontmatter is the policy source of truth; keeping a second
    hard-coded denylist here would drift as commands are added or reclassified.
    """
    if not suite_root:
        return None
    commands = set()
    for p in glob.glob(os.path.join(suite_root, "plugins", "*", "commands",
                                    "*.md")):
        with open(p, encoding="utf-8") as f:
            text = f.read()
        if not text.startswith("---"):
            continue
        parts = text.split("---", 2)
        frontmatter = parts[1] if len(parts) >= 3 else ""
        if re.search(r"(?mi)^disable-model-invocation\s*:\s*true\s*$",
                     frontmatter):
            norm = p.replace(os.sep, "/")
            commands.add("/%s:%s" % (norm.split("/")[-3],
                                      os.path.basename(p)[:-3]))
    return commands


def handoff_targets(seat):
    """handoff_to as a list: string -> [s], null -> [], list -> list."""
    tgt = seat.get("handoff_to")
    if tgt is None:
        return []
    if isinstance(tgt, str):
        return [tgt]
    if isinstance(tgt, list):
        return [t for t in tgt if isinstance(t, str)]
    return []


def path_match(concrete, pattern):
    """Exact path / fnmatch semantics ONLY. A descriptive string never
    satisfies a glob: '.solo/gate-evidence/ (notes)' does not match
    '*.json'."""
    if not isinstance(concrete, str) or not isinstance(pattern, str):
        return False
    c, p = concrete.strip(), pattern.strip()
    return c == p or fnmatch.fnmatchcase(c, p)


def normalize_stages(data, bad):
    """Accept legacy [[seat,...],...] and preferred [{id, seats},...]; return
    list of (stage_id, [seat_ids]) or None on structural failure."""
    stages = data.get("stages")
    if not (isinstance(stages, list) and stages):
        bad("'stages' must be a non-empty list")
        return None
    out, ids = [], set()
    for i, entry in enumerate(stages):
        if isinstance(entry, list):
            if not (entry and all(isinstance(x, str) for x in entry)):
                bad("stage %d: legacy stage must be a non-empty list of seat ids" % (i + 1))
                return None
            sid = "stage-%d" % (i + 1)
        elif isinstance(entry, dict):
            sid = entry.get("id")
            seats = entry.get("seats")
            if not (isinstance(sid, str) and sid.strip()):
                bad("stage %d: missing non-empty 'id'" % (i + 1))
                return None
            if not (isinstance(seats, list) and seats
                    and all(isinstance(x, str) for x in seats)):
                bad("stage %r: 'seats' must be a non-empty list of seat ids" % sid)
                return None
            entry = seats
        else:
            bad("stage %d: must be a seat-id list or {id, seats} object" % (i + 1))
            return None
        if sid in ids:
            bad("duplicate stage id %r — stage ids must be unique" % sid)
        ids.add(sid)
        out.append((sid, list(entry)))
    return out


# ===========================================================================
# semantic validation (step 2)
# ===========================================================================
def validate_room(data, label, known=None, known_agents_set=None,
                  schema=None, agent_isolation_map=None,
                  manual_commands_set=None):
    problems = []

    def bad(msg):
        problems.append("%s: %s" % (label, msg))

    if not isinstance(data, dict):
        bad("room document must be a JSON object (got %s)"
            % type(data).__name__)
        return problems

    # ---- step 1: the ACTUAL JSON Schema -----------------------------------
    try:
        sch = schema if schema is not None else load_schema()
    except Exception as e:
        bad("cannot load agentroom-v1 schema: %s" % e)
        sch = None
    if sch is not None:
        errs = schema_errors(data, sch)
        if errs:
            for e in errs[:25]:
                bad("schema: %s" % e)
            return problems          # semantics need schema-valid shapes

    if data.get("schema") != "solo-suite/agentroom-v1":
        bad("schema must be 'solo-suite/agentroom-v1' (got %r)" % data.get("schema"))
    if not (isinstance(data.get("name"), str) and data.get("name").strip()):
        bad("missing non-empty 'name'")

    # ---- run identity (schema enforces shape; double-check presence) ------
    run = data.get("run")
    if not (isinstance(run, dict) and isinstance(run.get("id_prefix"), str)
            and run.get("id_prefix").strip()
            and run.get("id_required") is True):
        bad("'run' identity is required: {id_prefix: <non-empty>, "
            "id_required: true} — every execution must be tagged")

    norm = normalize_stages(data, bad)
    seats = data.get("seats")
    if norm is None:
        return problems
    if not (isinstance(seats, list) and seats
            and all(isinstance(s, dict) for s in seats)):
        bad("'seats' must be a non-empty list of objects")
        return problems

    steward_cfg = data.get("memory_steward")
    steward_id, steward_owns = None, set()
    if steward_cfg is not None:
        if not isinstance(steward_cfg, dict):
            bad("'memory_steward' must be an object")
            steward_cfg = None
        else:
            steward_id = steward_cfg.get("seat")
            owns = steward_cfg.get("owns")
            if not (isinstance(steward_id, str) and steward_id.strip()):
                bad("memory_steward.seat must name a seat id")
            if not (isinstance(owns, list) and owns
                    and all(isinstance(x, str) for x in owns)):
                bad("memory_steward.owns must be a non-empty list of artifacts")
            else:
                steward_owns = set(owns)
            if steward_cfg.get("allocates_task_ids") is not True:
                bad("memory_steward.allocates_task_ids must be true — the "
                    "steward is what makes task IDs unique")
    steward_active_through = (steward_cfg or {}).get("active_through_stage") \
        if isinstance(steward_cfg, dict) else None

    ids = [s.get("id") for s in seats]
    for dup in sorted({i for i in ids if ids.count(i) > 1},
                      key=lambda x: str(x)):
        bad("duplicate seat id %r" % dup)
    idset = set(ids)
    if steward_id is not None and steward_id not in idset:
        bad("memory_steward.seat %r is not a defined seat" % steward_id)

    profiles = data.get("profiles")
    if profiles is not None:
        if not (isinstance(profiles, list)
                and all(isinstance(p, str) for p in profiles)):
            bad("'profiles' must be a list of strings")
            profiles = None
        else:
            for p in profiles:
                if p not in RECOGNIZED_PROFILES:
                    bad("'profiles' entry %r is not a recognized profile %s"
                        % (p, sorted(RECOGNIZED_PROFILES)))

    stage_of = {}
    for si, (sid, group) in enumerate(norm):
        for seat_id in group:
            if seat_id not in idset:
                bad("stage %d lists unknown seat %r" % (si + 1, seat_id))
            if seat_id in stage_of:
                bad("seat %r appears in stage %d AND stage %d — a seat belongs to "
                    "exactly one stage" % (seat_id, stage_of[seat_id] + 1, si + 1))
            else:
                stage_of[seat_id] = si
    for seat_id in sorted(idset - set(stage_of), key=lambda x: str(x)):
        if seat_id != steward_id:
            bad("seat %r is not placed in any stage" % seat_id)
    # A steward may be OUT-OF-BAND (unstaged: runs after every stage) or a
    # normal staged seat (e.g. a triager who also merges memory). Only the
    # unstaged form is excluded from the handoff graph.
    steward_unstaged = steward_id is not None and steward_id not in stage_of
    stage_index = {sid: i for i, (sid, _grp) in enumerate(norm)}
    if steward_active_through is not None and \
            steward_active_through not in stage_index:
        bad("memory_steward.active_through_stage %r is not a declared "
            "stage id (stages: %s)"
            % (steward_active_through, [s for s, _ in norm]))

    # ---- per-seat structure, handoffs, declarations -----------------------
    by_id = {}
    for s in seats:
        sid = s.get("id", "?")
        by_id[sid] = s
        for k in SEAT_KEYS:
            if k not in s:
                bad("seat %r missing key %r" % (sid, k))
        for fld in ("reads", "writes", "proposes", "applies_to"):
            v = s.get(fld)
            if v is not None and not (isinstance(v, list)
                                      and all(isinstance(x, str) for x in v)):
                bad("seat %r: %r must be a list of strings" % (sid, fld))
        both = set(s.get("writes") or []) & set(s.get("proposes") or [])
        if both:
            bad("seat %r declares %s in BOTH writes and proposes — pick one"
                % (sid, sorted(both)))
        ap = s.get("applies_to")
        if isinstance(ap, list):
            if not ap:
                bad("seat %r: applies_to is EMPTY — the seat would never "
                    "run for any profile" % sid)
            if profiles is None:
                bad("seat %r declares applies_to but the room declares no "
                    "'profiles' — conditional seats need the room-level "
                    "profile list" % sid)
            for p in ap:
                if p not in RECOGNIZED_PROFILES:
                    bad("seat %r applies_to unrecognized profile %r" % (sid, p))
                elif profiles is not None and p not in profiles:
                    bad("seat %r applies_to profile %r not declared in the "
                        "room's 'profiles'" % (sid, p))
        raw_tgt = s.get("handoff_to")
        if raw_tgt is not None and not isinstance(raw_tgt, (str, list)):
            bad("seat %r: handoff_to must be a seat id, a list of seat ids, "
                "or null" % sid)
        for tgt in handoff_targets(s):
            if tgt not in idset:
                bad("seat %r hands off to unknown seat %r" % (sid, tgt))
            elif tgt == steward_id and steward_unstaged:
                bad("seat %r hands off to the unstaged memory steward %r — "
                    "an out-of-band steward takes no handoffs" % (sid, tgt))
            elif sid in stage_of and tgt in stage_of:
                if stage_of[tgt] == stage_of[sid]:
                    bad("seat %r hands off to %r in the SAME stage — parallel seats "
                        "must hand off to a later stage (or split the stage)"
                        % (sid, tgt))
                elif stage_of[tgt] < stage_of[sid]:
                    bad("seat %r hands off BACKWARD to %r (stage %d -> %d) — loops "
                        "must use the explicit 'loop' block"
                        % (sid, tgt, stage_of[sid] + 1, stage_of[tgt] + 1))

    # ---- exit gate: EXACTLY ONE executor, no fallback ----------------------
    if not (isinstance(data.get("exit_criteria"), str)
            and data.get("exit_criteria").strip()):
        bad("missing non-empty 'exit_criteria'")
    gate = data.get("exit_gate", "__MISSING__")
    exit_seat_id = None
    if gate == "__MISSING__":
        bad("missing 'exit_gate' key (use null plus 'exit_gate_note' if a room is "
            "deliberately gateless)")
        gate = None
    elif gate is None:
        if not (isinstance(data.get("exit_gate_note"), str)
                and data.get("exit_gate_note").strip()):
            bad("'exit_gate' is null with no 'exit_gate_note' documenting why")
    elif not (isinstance(gate, str) and CMD_RE.match(gate)):
        bad("'exit_gate' %r is not a /plugin:command reference" % gate)
        gate = None
    if isinstance(gate, str):
        executors = [s for s in seats
                     if gate in (s.get("commands") or [])]
        if len(executors) == 0:
            bad("exit gate %s has NO executing seat — exactly one seat must "
                "list it in 'commands' (there is no last-stage fallback)" % gate)
        elif len(executors) > 1:
            bad("exit gate %s is executed by %d seats (%s) — exactly one "
                "seat must own the gate"
                % (gate, len(executors),
                   "/".join(str(s.get("id")) for s in executors)))
        else:
            exit_seat_id = executors[0].get("id")

    # ---- GRAPH MODEL: reachability + reaches-exit, per profile ------------
    def contracted_targets(seat_id, active, seen=None):
        """Active targets reachable from seat_id, skipping inactive seats."""
        if seen is None:
            seen = set()
        if seat_id in seen or seat_id not in by_id:
            return set()
        seen.add(seat_id)
        out = set()
        for t in handoff_targets(by_id[seat_id]):
            if t in active:
                out.add(t)
            elif t in by_id:
                out |= contracted_targets(t, active, seen)
        return out

    def check_graph(profile):
        if profile is None:
            active = {s.get("id") for s in seats}
            tag = ""
        else:
            active = {s.get("id") for s in seats
                      if not s.get("applies_to") or profile in s["applies_to"]}
            tag = " [profile %s]" % profile
        if steward_unstaged:
            active -= {steward_id}
        placed = [sid for sid in active if sid in stage_of]
        if not placed:
            bad("no active seats%s" % tag)
            return
        first_stage = min(stage_of[sid] for sid in placed)
        entries = {sid for sid in placed if stage_of[sid] == first_stage}
        # forward reachability from entries over contracted handoffs
        reach = set(entries)
        frontier = list(entries)
        while frontier:
            cur = frontier.pop()
            for t in contracted_targets(cur, active):
                if t not in reach:
                    reach.add(t)
                    frontier.append(t)
        for sid in sorted(set(placed) - reach):
            bad("seat %r is unreachable%s — no active seat hands off into it "
                "(skipped seats forward their handoffs; the graph model is "
                "entry-stage seats -> handoff edges -> exit seat)"
                % (sid, tag))
        # every active seat must reach the exit-gate executor
        if exit_seat_id is not None and exit_seat_id in active:
            reaches_exit = {exit_seat_id}
            changed = True
            while changed:
                changed = False
                for sid in placed:
                    if sid in reaches_exit:
                        continue
                    if contracted_targets(sid, active) & reaches_exit:
                        reaches_exit.add(sid)
                        changed = True
            for sid in sorted(set(placed) - reaches_exit):
                bad("seat %r cannot reach the exit-gate executor %r%s — "
                    "every active seat must flow into the gate"
                    % (sid, exit_seat_id, tag))
        elif exit_seat_id is not None:
            bad("the exit-gate executor %r is not active%s — the gate "
                "cannot run" % (exit_seat_id, tag))
        # dead ends: only the exit seat (or steward) may have no handoff
        for sid in sorted(placed):
            if sid == exit_seat_id or sid == steward_id:
                continue
            if exit_seat_id is not None and not handoff_targets(by_id[sid]):
                bad("seat %r has a null/empty handoff_to but is not the "
                    "exit-gate executor%s — dead end" % (sid, tag))
        return reach

    reach_all = check_graph(None)
    for prof in (profiles or []):
        check_graph(prof)

    # ---- effective writes: declared + implicit ----------------------------
    eff = {}
    for s in seats:
        sid = s.get("id", "?")
        declared = set(s.get("writes") or [])
        proposed = set(s.get("proposes") or [])
        implicit = implicit_writes_of(s.get("commands"))
        # An implicit effect declared under `proposes` is written to a
        # proposal payload for the steward; it is not a direct write to the
        # target artifact and therefore cannot collide as a same-stage writer.
        eff[sid] = declared | (implicit - proposed)
        undeclared = implicit - declared - proposed
        if sid == steward_id:
            undeclared -= steward_owns  # ownership is an explicit declaration
        if undeclared:
            steward_part = sorted(undeclared & steward_owns)
            other_part = sorted(undeclared - steward_owns)
            if steward_part:
                bad("seat %r: commands implicitly write steward-owned %s — "
                    "declare under 'proposes' (the steward merges them)"
                    % (sid, steward_part))
            if other_part:
                bad("seat %r: commands implicitly write %s — declare under "
                    "'writes'" % (sid, other_part))
        if proposed:
            if steward_cfg is None:
                bad("seat %r declares proposals %s but the room has no "
                    "memory_steward to merge them" % (sid, sorted(proposed)))
            else:
                unowned_proposals = sorted(proposed - steward_owns)
                if unowned_proposals:
                    bad("seat %r proposes %s but the memory steward does not "
                        "own those targets" % (sid, unowned_proposals))
        if steward_id is not None and sid != steward_id:
            direct_owned = declared & steward_owns
            if direct_owned:
                bad("seat %r writes steward-owned %s directly — use 'proposes'"
                    % (sid, sorted(direct_owned)))

    # ---- one writer per artifact per stage (on effective writes) ----------
    for si, (stage_id, group) in enumerate(norm):
        writers = {}
        for sid in group:
            if sid not in by_id:
                continue
            for w in sorted(eff.get(sid, ())):
                writers.setdefault(w, []).append(sid)
        for w, who in sorted(writers.items()):
            if len(who) > 1:
                if steward_cfg is not None and w in steward_owns:
                    continue  # both must propose; enforced above
                declared_by = [x for x in who
                               if w in set(by_id[x].get("writes") or [])]
                kind = "" if len(declared_by) > 1 else " (implicit command write)"
                bad("stage %d: artifact %r written by %s%s — one writer per "
                    "artifact per stage; route shared memory through the "
                    "memory steward via 'proposes'"
                    % (si + 1, w, " and ".join(who), kind))

    # ---- artifact locks ----------------------------------------------------
    locks = data.get("locks")
    if locks is not None:
        if not (isinstance(locks, dict)
                and all(isinstance(v, str) for v in locks.values())):
            bad("'locks' must map artifact -> owner seat id")
        else:
            for artifact, owner in sorted(locks.items()):
                if owner not in idset:
                    bad("lock on %r names unknown owner %r" % (artifact, owner))
                for sid, files in sorted(eff.items()):
                    if (artifact in files and sid not in (owner, steward_id)
                            and artifact not in set(
                                by_id.get(sid, {}).get("proposes") or [])):
                        bad("seat %r writes locked artifact %r owned by %r"
                            % (sid, artifact, owner))

    # ---- workspace ownership + WORKTREE EXECUTION CONTRACT -----------------
    worktree_seats = []
    for si, (stage_id, group) in enumerate(norm):
        code_writers = []
        for sid in group:
            s = by_id.get(sid)
            if not s:
                continue
            ws = s.get("workspace")
            if isinstance(ws, str) and ws.startswith("worktree:"):
                worktree_seats.append(sid)
            non_memory = [w for w in (s.get("writes") or [])
                          if not w.startswith(".solo/")]
            if non_memory or ws:
                code_writers.append(sid)
        if len(code_writers) > 1:
            spaces = {}
            for sid in code_writers:
                ws = by_id[sid].get("workspace")
                if not ws:
                    bad("stage %d: seats %s write non-memory artifacts in "
                        "parallel — seat %r must declare an owned 'workspace'"
                        % (si + 1, code_writers, sid))
                else:
                    spaces.setdefault(ws, []).append(sid)
            for ws, who in sorted(spaces.items()):
                if len(who) > 1:
                    bad("stage %d: workspace %r shared by %s — parallel "
                        "writers own distinct workspaces/worktrees"
                        % (si + 1, ws, " and ".join(who)))

    if worktree_seats:
        wt = data.get("worktrees")
        if not isinstance(wt, dict):
            bad("room has worktree seats %s but no 'worktrees' execution "
                "contract — required: base_sha (recorded BEFORE spawning; "
                "platform worktree agents branch from the DEFAULT branch, "
                "not the parent session HEAD), builder_payload, "
                "proposal_transport, integration, verify_at_integration_sha"
                % sorted(worktree_seats))
        else:
            bs = wt.get("base_sha")
            if not (isinstance(bs, dict)
                    and isinstance(bs.get("recorded_by"), str)
                    and bs.get("recorded_by").strip()
                    and isinstance(bs.get("rule"), str)
                    and bs.get("rule").strip()):
                bad("worktrees.base_sha must document who records the base "
                    "SHA before spawning and the rebase/ff rule builders "
                    "follow (they branch from the DEFAULT branch)")
            payload = wt.get("builder_payload")
            if not (isinstance(payload, list)
                    and all(isinstance(x, str) for x in payload)):
                bad("worktrees.builder_payload must be a list of strings")
            else:
                missing = BUILDER_PAYLOAD_REQUIRED - set(payload)
                if missing:
                    bad("worktrees.builder_payload missing required entries "
                        "%s — every builder must return its worktree path, "
                        "branch, clean commit SHA, tests, and proposal "
                        "payload" % sorted(missing))
            if not (isinstance(wt.get("proposal_transport"), str)
                    and wt.get("proposal_transport").strip()):
                bad("worktrees.proposal_transport must document how "
                    "proposals cross isolated worktrees (e.g. committed "
                    "into the builder branch; refs shared via the common "
                    "object store)")
            integ = wt.get("integration")
            integ_stage = None
            if not isinstance(integ, dict):
                bad("worktrees.integration must be an object "
                    "{seat, mode, ref}")
            else:
                iseat = integ.get("seat")
                if iseat not in idset:
                    bad("worktrees.integration.seat %r is not a defined seat"
                        % (iseat,))
                else:
                    integ_stage = stage_of.get(iseat)
                    for wsid in worktree_seats:
                        if (integ_stage is not None
                                and stage_of.get(wsid) is not None
                                and integ_stage <= stage_of[wsid]
                                and iseat != wsid):
                            bad("worktrees.integration.seat %r (stage %d) "
                                "must run AFTER worktree seat %r (stage %d)"
                                % (iseat, integ_stage + 1, wsid,
                                   stage_of[wsid] + 1))
                mode = integ.get("mode")
                if mode not in ("merge-exact-shas", "checkout-exact-sha"):
                    bad("worktrees.integration.mode must be "
                        "'merge-exact-shas' (integrator merges/cherry-picks "
                        "the builders' exact SHAs into ONE integration "
                        "commit) or 'checkout-exact-sha' (the verifier "
                        "checks out the fixer's exact commit)")
                elif mode == "checkout-exact-sha" and len(worktree_seats) > 1:
                    bad("worktrees.integration.mode 'checkout-exact-sha' is "
                        "only valid with EXACTLY ONE worktree seat — %d "
                        "parallel builders require 'merge-exact-shas' into "
                        "one integration commit" % len(worktree_seats))
                elif mode == "merge-exact-shas" and len(worktree_seats) == 1 \
                        and integ.get("seat") == worktree_seats[0]:
                    bad("worktrees.integration seat cannot be the sole "
                        "builder itself")
                if not (isinstance(integ.get("ref"), str)
                        and integ.get("ref").strip()):
                    bad("worktrees.integration.ref must name the "
                        "integration branch/ref")
            bs_stored = (bs or {}).get("stored_in") if isinstance(bs, dict) \
                else None
            if isinstance(bs_stored, str):
                if not _untracked_runtime(bs_stored):
                    bad("worktrees.base_sha.stored_in %r is not under "
                        ".solo/run-state/ — run SHAs live in UNTRACKED "
                        "runtime state (a commit cannot contain its own "
                        "SHA)" % bs_stored)
                for st in seats:
                    sid = st.get("id")
                    if isinstance(st.get("workspace"), str) \
                            and st["workspace"].startswith("worktree:"):
                        reads = st.get("reads") or []
                        if not any(isinstance(r, str)
                                   and r.startswith(".solo/run-state/")
                                   for r in reads):
                            bad("worktree seat %r does not READ the "
                                "runtime-state file — every builder must "
                                "receive BASE_SHA through %r"
                                % (sid, bs_stored))
            _ev_cfg = data.get("evidence")
            has_evidence = isinstance(_ev_cfg, dict)
            fin_seat_ref = _ev_cfg.get("finalizer") if has_evidence else None
            verify = wt.get("verify_at_integration_sha")
            if not (isinstance(verify, list) and verify
                    and all(isinstance(x, str) for x in verify)):
                bad("worktrees.verify_at_integration_sha must be a "
                    "non-empty list of seat ids")
            else:
                for v in verify:
                    if v not in idset:
                        bad("worktrees.verify_at_integration_sha names "
                            "unknown seat %r" % v)
                    elif (integ_stage is not None
                          and stage_of.get(v) is not None
                          and stage_of[v] < integ_stage):
                        bad("worktrees.verify_at_integration_sha seat %r "
                            "runs BEFORE the integration seat — it cannot "
                            "verify the integration SHA" % v)
                if has_evidence:
                    for v in verify:
                        if v in (exit_seat_id, fin_seat_ref):
                            bad("worktrees.verify_at_integration_sha lists "
                                "%r — the finalize/gate seats run AFTER "
                                "the freeze, where HEAD equals FINAL_SHA "
                                "(a DESCENDANT of the integration SHA), "
                                "so an INTEGRATION_SHA requirement is "
                                "unsatisfiable; list them under "
                                "verify_at_final_sha" % v)
                elif exit_seat_id is not None and exit_seat_id not in verify:
                    bad("worktrees.verify_at_integration_sha must include "
                        "the exit-gate executor %r — the gate must verify "
                        "the exact integration SHA" % exit_seat_id)
                for v in verify:
                    st = by_id.get(v)
                    if st is None:
                        continue
                    reads = st.get("reads") or []
                    if not any(isinstance(r, str)
                               and r.startswith(".solo/run-state/")
                               for r in reads):
                        bad("verify seat %r does not READ a "
                            ".solo/run-state/ file — every SHA consumer "
                            "must receive the exact SHA through untracked "
                            "runtime state" % v)
            vfin = wt.get("verify_at_final_sha")
            if has_evidence:
                if not (isinstance(vfin, list) and vfin
                        and all(isinstance(x, str) for x in vfin)):
                    bad("worktree rooms with an evidence lifecycle must "
                        "declare worktrees.verify_at_final_sha — the "
                        "finalize/gate seats verify FINAL_SHA, not "
                        "INTEGRATION_SHA")
                else:
                    for v in vfin:
                        if v not in idset:
                            bad("worktrees.verify_at_final_sha names "
                                "unknown seat %r" % v)
                            continue
                        reads = (by_id.get(v) or {}).get("reads") or []
                        if not any(isinstance(r, str)
                                   and r.startswith(".solo/run-state/")
                                   for r in reads):
                            bad("verify_at_final_sha seat %r does not "
                                "READ a .solo/run-state/ file — FINAL_SHA "
                                "travels only through untracked runtime "
                                "state" % v)
                    if exit_seat_id is not None and exit_seat_id not in vfin:
                        bad("worktrees.verify_at_final_sha must include "
                            "the exit-gate executor %r" % exit_seat_id)
                    if fin_seat_ref is not None and fin_seat_ref not in vfin:
                        bad("worktrees.verify_at_final_sha must include "
                            "the evidence finalizer %r" % fin_seat_ref)
            elif vfin is not None:
                bad("worktrees.verify_at_final_sha declared but the room "
                    "has no evidence lifecycle — there is no FINAL_SHA to "
                    "verify")
    elif data.get("worktrees") is not None:
        bad("'worktrees' contract declared but no seat has a "
            "'workspace: worktree:…' — remove one or the other")

    # ---- worktree seats must map to isolation-declaring agents -------------
    if agent_isolation_map is not None:
        for sid in worktree_seats:
            agent = (by_id.get(sid) or {}).get("agent")
            if isinstance(agent, str) and agent in agent_isolation_map \
                    and agent_isolation_map[agent] != "worktree":
                bad("seat %r has workspace 'worktree:…' but its agent %r "
                    "does not declare 'isolation: worktree' — the platform "
                    "would run it in the SHARED workspace" % (sid, agent))

    # ---- same-stage read-after-write dependencies --------------------------
    for si, (stage_id, group) in enumerate(norm):
        stage_writers = {}
        for sid in group:
            for w in (by_id.get(sid) or {}).get("writes") or []:
                stage_writers.setdefault(w, set()).add(sid)
        for sid in group:
            for r in (by_id.get(sid) or {}).get("reads") or []:
                writers = stage_writers.get(r, set()) - {sid, steward_id}
                if writers:
                    bad("stage %d: seat %r READS %r which %s WRITES in the "
                        "SAME stage — the data does not exist yet; move the "
                        "reader to a later stage"
                        % (si + 1, sid, r, "/".join(sorted(writers))))

    # ---- every seat maps to a real agent (or an explicit mapping note) -----
    for st in seats:
        sid = st.get("id", "?")
        agent = st.get("agent")
        note = st.get("agent_note")
        if not agent and not (isinstance(note, str) and note.strip()):
            bad("seat %r has no 'agent' (room-* definition) and no explicit "
                "'agent_note' mapping" % sid)
        elif agent is not None:
            if not isinstance(agent, str) or not agent.strip():
                bad("seat %r: 'agent' must be a non-empty string" % sid)
            elif known_agents_set is not None and agent not in known_agents_set:
                bad("seat %r maps to agent %r which does not exist in "
                    "plugins/*/agents/" % (sid, agent))

    # ---- gate evidence: readable by the executor + earlier producers -------
    gate_requires = data.get("gate_requires")
    assumes = data.get("assumes_preexisting")
    assumed = {}
    if assumes is not None:
        if not (isinstance(assumes, dict)
                and all(isinstance(v, str) and v.strip()
                        for v in assumes.values())):
            bad("'assumes_preexisting' must map artifact -> reason")
        else:
            assumed = dict(assumes)

    def assumed_covers(artifact):
        return any(path_match(artifact, pat) or path_match(pat, artifact)
                   for pat in assumed)

    # ---- READ PROVENANCE: every concrete .solo/ read needs a source --------
    # A read is satisfied by: an earlier-stage producer (write, or a
    # steward-merged proposal of a steward-owned file), the reading seat's
    # own write, the UNSTAGED steward's owned files, an assumes_preexisting
    # entry, or — for .solo/run-state/ — a structured SHA contract
    # (worktrees.base_sha / evidence.freeze, both orchestrator-produced
    # before the reader runs). Descriptive reads (with spaces/parentheses)
    # are not concrete paths and are skipped.
    _wt_cfg = data.get("worktrees")
    _ev_cfg2 = data.get("evidence")
    run_state_contract = False
    if isinstance(_wt_cfg, dict):
        _bs = _wt_cfg.get("base_sha")
        if isinstance(_bs, dict) and isinstance(_bs.get("stored_in"), str) \
                and _bs["stored_in"].startswith(".solo/run-state/"):
            run_state_contract = True
    if isinstance(_ev_cfg2, dict):
        _fr = _ev_cfg2.get("freeze")
        if isinstance(_fr, dict) \
                and isinstance(_fr.get("stored_in"), str) \
                and _fr["stored_in"].startswith(".solo/run-state/"):
            run_state_contract = True

    def _concrete_solo_read(r):
        return (isinstance(r, str) and r.startswith(".solo/")
                and " " not in r and "(" not in r)

    def _produced_before(reader_sid, reader_stage, artifact):
        for other in seats:
            oid = other.get("id")
            if oid == reader_sid:
                continue
            early = ((oid == steward_id and steward_unstaged)
                     or (oid in stage_of and reader_stage is not None
                         and stage_of[oid] < reader_stage))
            if not early:
                continue
            outs = list(other.get("writes") or [])
            for o in (other.get("proposes") or []):
                if isinstance(o, str) and any(
                        path_match(o, own) or o == own
                        for own in steward_owns):
                    outs.append(o)
            if oid == steward_id and steward_unstaged:
                outs = [o for o in outs if any(
                    path_match(o, own) or o == own
                    for own in steward_owns)]
            for o in outs:
                if isinstance(o, str) and (path_match(o, artifact)
                                           or path_match(artifact, o)):
                    return True
        return False

    for st in seats:
        sid = st.get("id", "?")
        reader_stage = stage_of.get(sid)
        if reader_stage is None and sid != steward_id:
            continue
        for r in (st.get("reads") or []):
            if not _concrete_solo_read(r):
                continue
            if r.startswith(".solo/run-state/"):
                if not run_state_contract:
                    bad("seat %r READS %r but the room declares no "
                        "structured SHA contract (worktrees.base_sha or "
                        "evidence.freeze) that produces run-state — the "
                        "read has no provenance" % (sid, r))
                continue
            if assumed_covers(r):
                continue
            own_writes = st.get("writes") or []
            if any(isinstance(w, str) and (path_match(w, r)
                                           or path_match(r, w))
                   for w in own_writes):
                continue
            if sid == steward_id and steward_unstaged and any(
                    path_match(r, own) or r == own
                    for own in steward_owns):
                continue
            if steward_unstaged and any(path_match(r, own) or r == own
                                        for own in steward_owns):
                continue
            if sid == steward_id and steward_unstaged:
                reader_stage_eff = len(norm)
            else:
                reader_stage_eff = reader_stage
            if _produced_before(sid, reader_stage_eff, r):
                continue
            bad("seat %r READS %r which NO earlier stage produces and no "
                "assumes_preexisting entry covers — declare a producer, "
                "or document it in 'assumes_preexisting' with a reason"
                % (sid, r))

    exec_seat = by_id.get(exit_seat_id) if exit_seat_id else None
    exec_stage = stage_of.get(exit_seat_id, len(norm)) \
        if exit_seat_id else len(norm)

    def produced_earlier(artifact, active=None, concrete_only=False):
        """An artifact is produced earlier iff a REACHABLE seat in a
        STRICTLY earlier stage (or the steward, for its owned files only)
        declares a WRITE that path_match()es it. The executor's own writes
        never count. PROPOSALS count ONLY for steward-owned artifacts —
        a proposal of anything else is never merged into a real file, so it
        is not production ("evidence from unmerged proposals").
        concrete_only additionally forbids glob outputs. Unreachable seats
        never count as producers — their work never happens."""
        for st in seats:
            sid = st.get("id")
            if sid == exit_seat_id:
                continue
            if active is not None and sid not in active and sid != steward_id:
                continue
            if sid != steward_id and sid not in reach_all:
                continue     # unreachable producer: its outputs never exist
            early = ((sid == steward_id and steward_unstaged)
                     or (sid in stage_of and stage_of[sid] < exec_stage))
            if not early:
                continue
            outs = list(st.get("writes") or [])
            for o in (st.get("proposes") or []):
                if isinstance(o, str) and any(
                        path_match(o, own) or o == own
                        for own in steward_owns):
                    outs.append(o)   # merged by the steward -> real file
            for o in outs:
                if not isinstance(o, str):
                    continue
                if (sid == steward_id and steward_unstaged and not any(
                        path_match(o, own) or o == own
                        for own in steward_owns)):
                    continue
                if concrete_only:
                    if ("*" not in o and "?" not in o
                            and o.strip() == artifact):
                        return True
                elif path_match(o, artifact) or path_match(artifact, o):
                    return True
        return False

    if gate_requires is not None:
        if not (isinstance(gate_requires, list)
                and all(isinstance(x, str) for x in gate_requires)):
            bad("'gate_requires' must be a list of artifact paths")
        elif isinstance(gate, str) and exec_seat is not None:
            readable = set(exec_seat.get("reads") or []) \
                | set(exec_seat.get("writes") or [])
            missing = [a for a in gate_requires
                       if not any(path_match(a, r) or r == a
                                  for r in readable)]
            if missing:
                bad("gate %s lacks evidence: executor %s cannot read %s — "
                    "add them to the gatekeeper's reads"
                    % (gate, exit_seat_id, missing))
            for a in gate_requires:
                if assumed_covers(a):
                    continue
                if not produced_earlier(a):
                    bad("gate %s requires %r but NO seat in an earlier stage "
                        "produces it (declare a producer or list it in "
                        "'assumes_preexisting' with a reason)" % (gate, a))

    # ---- gate_evidence_map: category-specific producers --------------------
    _GEM_VALUE_RE = re.compile(r"^[A-Za-z0-9_.\-/*]+$")
    gem = data.get("gate_evidence_map")
    if gem is not None:
        if not (isinstance(gem, dict)
                and all(isinstance(v, str) for v in gem.values())):
            bad("'gate_evidence_map' must map category -> artifact")
            gem = None
        else:
            for k in sorted(set(gem) - CATEGORIES):
                bad("gate_evidence_map key %r is not a gate category" % k)
            for k, v in sorted(gem.items()):
                if not (len(v) >= 3 and _GEM_VALUE_RE.match(v)
                        and ("/" in v or "." in v)):
                    bad("gate_evidence_map[%r] value %r is not a path-like "
                        "artifact reference (no spaces or prose)" % (k, v))

    # ---- EVIDENCE LIFECYCLE (rooms gated by /gate:production-ready) --------
    ev = data.get("evidence")
    if isinstance(gate, str) and gate == "/gate:production-ready" \
            and exec_seat is not None:
        if gem is None:
            bad("exit gate /gate:production-ready requires a "
                "'gate_evidence_map' covering all 14 categories")
        else:
            for cat in sorted(CATEGORIES - set(gem)):
                bad("gate_evidence_map does not cover category %r" % cat)
        if not isinstance(ev, dict):
            bad("exit gate /gate:production-ready requires the 'evidence' "
                "lifecycle block ({finalizer, final_sha_recorded_in, "
                "workflow: untracked}) — specialists must not mint final "
                "records against intermediate commits")
        else:
            fin_id = ev.get("finalizer")
            fin = by_id.get(fin_id)
            if fin is None:
                bad("evidence.finalizer %r is not a defined seat" % (fin_id,))
            else:
                if not (isinstance(fin.get("agent"), str)
                        and fin.get("agent").strip()):
                    bad("evidence.finalizer %r has no real 'agent' — an "
                        "agent_note is documentation, not an executable "
                        "seat; map the finalizer to a shipped room agent "
                        "(room-evidence-finalizer)" % fin_id)
                fin_commands = fin.get("commands")
                handoff = fin.get("human_handoff")
                has_manual_finalize = (
                    isinstance(handoff, dict)
                    and handoff.get("command") == "/gate:finalize-evidence"
                    and handoff.get("executor") == "user"
                    and handoff.get("preview_required") is True
                    and handoff.get("confirmation_required") is True
                    and isinstance(handoff.get("resume_on"), str)
                    and handoff.get("resume_on").strip())
                if fin_commands != []:
                    bad("evidence.finalizer %r must have commands: [] — it "
                        "coordinates the user-only manual finalization and "
                        "must never execute a command itself" % fin_id)
                if not has_manual_finalize:
                    bad("evidence.finalizer %r lacks the required user-only "
                        "/gate:finalize-evidence human_handoff contract"
                        % fin_id)
                if fin.get("applies_to"):
                    bad("evidence.finalizer %r must run for EVERY profile "
                        "(remove applies_to)" % fin_id)
                if fin_id not in reach_all:
                    bad("evidence.finalizer %r is unreachable — its records "
                        "would never exist" % fin_id)
                fin_stage = stage_of.get(fin_id)
                if fin_stage is None:
                    bad("evidence.finalizer %r is not placed in any stage"
                        % fin_id)
                else:
                    if fin_stage >= exec_stage:
                        bad("evidence.finalizer %r (stage %d) must run "
                            "BEFORE the gate executor (stage %d)"
                            % (fin_id, fin_stage + 1, exec_stage + 1))
                    for st in seats:
                        sid = st.get("id")
                        if sid == fin_id:
                            continue
                        if sid in stage_of and stage_of[sid] > fin_stage:
                            # NO exemptions — not the exit gate, not the
                            # steward: zero tracked writes after the freeze
                            declared = set(st.get("writes") or [])
                            implicit = implicit_writes_of(st.get("commands"))
                            tracked = sorted(
                                w for w in (declared | implicit)
                                if not _untracked_runtime(w))
                            if tracked:
                                bad("seat %r (stage %d) runs AFTER the "
                                    "evidence finalizer (stage %d) with "
                                    "tracked writes %s — after FINAL_SHA "
                                    "nothing tracked may change; move these "
                                    "updates BEFORE the freeze"
                                    % (sid, stage_of[sid] + 1,
                                       fin_stage + 1, tracked))
                            props = sorted(st.get("proposes") or [])
                            if props:
                                bad("seat %r (stage %d) PROPOSES %s after "
                                    "the evidence finalizer — the memory "
                                    "steward must not run after the "
                                    "finalizer, so nothing may be left to "
                                    "merge" % (sid, stage_of[sid] + 1,
                                               props))
                            if "/solo:handoff-memory" in (
                                    st.get("commands") or []):
                                bad("seat %r runs /solo:handoff-memory "
                                    "AFTER the finalizer — handoff memory "
                                    "is a tracked write and belongs BEFORE "
                                    "the freeze commit" % sid)
                fin_reads = fin.get("reads") or []
                if not any(isinstance(r, str)
                           and r.startswith(".solo/run-state/")
                           for r in fin_reads):
                    bad("evidence.finalizer %r does not READ the "
                        "runtime-state file carrying FINAL_SHA (%r)"
                        % (fin_id, ev.get("final_sha_recorded_in")))
                # ---- structured RELEASE-FREEZE contract --------------------
                freeze = ev.get("freeze")
                if not isinstance(freeze, dict):
                    bad("evidence.freeze is REQUIRED: the orchestrator's "
                        "structured release-freeze contract (commit "
                        "everything, verify a clean tree, record "
                        "FINAL_SHA in untracked run-state) — prose in a "
                        "deliverable is not a contract")
                else:
                    a = freeze.get("after_stage")
                    b = freeze.get("before_stage")
                    if a not in stage_index:
                        bad("evidence.freeze.after_stage %r is not a "
                            "declared stage id" % (a,))
                    if b not in stage_index:
                        bad("evidence.freeze.before_stage %r is not a "
                            "declared stage id" % (b,))
                    if a in stage_index and b in stage_index \
                            and stage_index[b] != stage_index[a] + 1:
                        bad("evidence.freeze must sit IMMEDIATELY between "
                            "its stages: before_stage %r (index %d) is "
                            "not directly after after_stage %r (index %d)"
                            % (b, stage_index[b], a, stage_index[a]))
                    if fin_stage is not None and b in stage_index \
                            and stage_index[b] != fin_stage:
                        bad("evidence.freeze.before_stage %r is not the "
                            "evidence finalizer's stage — FINAL_SHA must "
                            "be recorded immediately before finalization"
                            % (b,))
                    if freeze.get("stored_in") != \
                            ev.get("final_sha_recorded_in"):
                        bad("evidence.freeze.stored_in %r must equal "
                            "evidence.final_sha_recorded_in %r — one "
                            "carrier, one file"
                            % (freeze.get("stored_in"),
                               ev.get("final_sha_recorded_in")))
                # ---- structured steward cutoff ------------------------------
                if steward_cfg is not None:
                    if steward_active_through is None:
                        bad("room has a memory steward AND an evidence "
                            "finalizer but no "
                            "memory_steward.active_through_stage — the "
                            "runner needs the structured cutoff so the "
                            "steward can NEVER be invoked at or after "
                            "the finalize stage")
                    elif steward_active_through in stage_index \
                            and fin_stage is not None \
                            and stage_index[steward_active_through] >= \
                            fin_stage:
                        bad("memory_steward.active_through_stage %r "
                            "(stage index %d) is not STRICTLY BEFORE the "
                            "evidence finalizer's stage (index %d) — the "
                            "steward's last merge happens before the "
                            "freeze"
                            % (steward_active_through,
                               stage_index[steward_active_through],
                               fin_stage))
                fin_writes = set(fin.get("writes") or [])
                for cat in sorted(set(gem or {}) & CATEGORIES):
                    evidence_file = ".solo/gate-evidence/%s.json" % cat
                    if evidence_file not in fin_writes:
                        bad("category %r: the evidence finalizer %r does "
                            "not write the CONCRETE record %r — all 14 "
                            "records are minted by the finalizer at "
                            "FINAL_SHA (a glob or directory note does not "
                            "count)" % (cat, fin_id, evidence_file))
            # NO other seat may produce final records mid-flow
            for st in seats:
                sid = st.get("id")
                if sid == (ev.get("finalizer") if isinstance(ev, dict)
                           else None):
                    continue
                offending = [o for o in (list(st.get("writes") or [])
                                         + list(st.get("proposes") or []))
                             if isinstance(o, str)
                             and o.startswith(".solo/gate-evidence")]
                if offending:
                    bad("seat %r writes/proposes %s — final category "
                        "records against intermediate commits are invalid; "
                        "only the declared finalizer stage may carry records "
                        "created by the user-invoked command at FINAL_SHA"
                        % (sid, sorted(offending)))
    elif ev is not None:
        bad("'evidence' lifecycle block declared but the exit gate is not "
            "/gate:production-ready")

    # ---- command refs + manual-only execution boundary --------------------
    refs = []
    for s in seats:
        sid = s.get("id", "?")
        seat_commands = s.get("commands") or []
        refs += [(sid, c) for c in seat_commands]
        if manual_commands_set is not None:
            for c in seat_commands:
                if c in manual_commands_set:
                    bad("seat %r executes manual-only command %s — move it "
                        "to a structured human_handoff with executor 'user'"
                        % (sid, c))
        handoff = s.get("human_handoff")
        if isinstance(handoff, dict):
            hc = handoff.get("command")
            refs.append(("%s human_handoff" % sid, hc))
            if hc in seat_commands:
                bad("seat %r lists human_handoff command %s in executable "
                    "commands" % (sid, hc))
            if manual_commands_set is not None \
                    and hc not in manual_commands_set:
                bad("seat %r human_handoff command %s is not marked "
                    "disable-model-invocation: true in its own frontmatter"
                    % (sid, hc))
        if s.get("handoff_check") is not None:
            refs.append((sid, s.get("handoff_check")))
    if isinstance(gate, str):
        refs.append(("exit_gate", gate))
    for who, c in refs:
        if not (isinstance(c, str) and CMD_RE.match(c)):
            bad("%s: %r is not a /plugin:command reference" % (who, c))
        elif known is not None and c not in known:
            bad("%s: command %s does not exist in this suite" % (who, c))

    # ---- loops (must be bounded) -------------------------------------------
    loop = data.get("loop")
    if loop is not None and not isinstance(loop, dict):
        bad("'loop' must be an object")
        loop = None
    if loop is not None:
        rep = loop.get("repeat_stages")
        if not (isinstance(rep, list) and rep
                and all(isinstance(g, list) and g for g in rep)):
            bad("'loop.repeat_stages' must be a non-empty list of seat-id lists")
        else:
            stage_sets = [frozenset(grp) for _sid, grp in norm]
            for g in rep:
                for sid in g:
                    if sid not in idset:
                        bad("loop repeats unknown seat %r" % (sid,))
                if all(sid in idset for sid in g) \
                        and frozenset(g) not in stage_sets:
                    bad("loop.repeat_stages group %s does not correspond to "
                        "any stage's seat set — a loop repeats whole "
                        "stages, not arbitrary seat mixtures" % sorted(g))
        if not (isinstance(loop.get("until"), str) and loop.get("until").strip()):
            bad("'loop.until' must state the loop exit condition")
        mi = loop.get("max_iterations")
        if not (isinstance(mi, int) and not isinstance(mi, bool) and mi >= 1):
            bad("'loop.max_iterations' must be a positive integer — loops "
                "must be bounded")
    return problems


def validate_files(paths, suite_root=None, schema_path=None):
    known = known_commands(suite_root)
    manual = manual_only_commands(suite_root)
    agents = known_agents(suite_root)
    iso = agent_isolation(suite_root)
    try:
        schema = load_schema(schema_path)
    except Exception as e:
        schema = None
        schema_err = "cannot load agentroom-v1 schema: %s" % e
    else:
        schema_err = None
    problems = []
    for path in paths:
        label = os.path.basename(path)
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            problems.append("%s: invalid JSON (%s)" % (label, e))
            continue
        if schema_err:
            problems.append("%s: %s" % (label, schema_err))
        try:
            problems += validate_room(data, label, known,
                                      known_agents_set=agents, schema=schema,
                                      agent_isolation_map=iso,
                                      manual_commands_set=manual)
        except Exception as e:   # contract: errors, never crashes
            problems.append("%s: internal validator error (%s: %s) — "
                            "please report" % (label, type(e).__name__, e))
    return problems


def main(argv=None):
    here = os.path.dirname(os.path.abspath(__file__))
    # Keep --help usable on ordinary Windows consoles whose active encoding
    # is cp1252. The full module docstring intentionally contains rich
    # punctuation; argparse does not need to print all of it as CLI help.
    ap = argparse.ArgumentParser(
        description="Validate AgentRooms JSON templates against the bundled "
                    "schema and semantic rules.")
    ap.add_argument("rooms", nargs="*",
                    help="room JSON files (default: bundled agentsrooms/*.json)")
    ap.add_argument("--suite", default=None,
                    help="suite root for command-existence checks (default: auto)")
    ap.add_argument("--schema", default=None,
                    help="path to agentroom-v1.schema.json (default: bundled)")
    args = ap.parse_args(argv)
    rooms = args.rooms or sorted(glob.glob(os.path.join(here, "..", "agentsrooms", "*.json")))
    if not rooms:
        print("no room templates found")
        return 1
    suite = args.suite or find_suite(here)
    if not suite:
        print("note: suite root not found — command existence not checked")
    problems = validate_files(rooms, suite_root=suite,
                              schema_path=args.schema)
    print("== agentroom validation (schema %s + semantics) =="
          % ("via jsonschema" if _jsonschema else "via builtin evaluator"))
    for r in rooms:
        name = os.path.basename(r)
        mine = [p for p in problems if p.startswith(name + ":")]
        if not mine:
            print("PASS  %s" % name)
    for p in problems:
        print("FAIL  %s" % p)
    print("== %d template(s), %d problem(s) ==" % (len(rooms), len(problems)))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
