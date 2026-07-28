#!/usr/bin/env python3
"""solo-suite self-check: verify the suite (or a single installed plugin) is
structurally healthy. Stdlib only.

Usage: python3 self_check.py [root] [project_root]
  root         = suite root (contains .claude-plugin/marketplace.json +
                 plugins/), auto-walked-up from the given path. If no suite
                 root is found but the path is a plugin directory (has
                 .claude-plugin/plugin.json), the check runs in
                 INSTALLED-PLUGIN MODE against that single plugin — the mode
                 used inside a plugin cache, where siblings and the
                 marketplace file are not present.
  project_root = folder that should contain .solo/ (default: cwd). Pass "-"
                 to skip memory checks.

HONESTY NOTE: these are static structure checks (manifests, frontmatter,
references, counts, schemas, helper paths). Passing means the suite's FILES
are consistent — it is NOT proof that the suite behaves correctly at
runtime. Exit 0 = no failures found by the static checks, 1 = failures.
"""
import json, os, re, sys, glob, zipfile

# ---------------------------------------------------------------------------
# frontmatter parsing: proper YAML when PyYAML is importable, otherwise a
# strict subset parser sufficient for official frontmatter (scalar values,
# quoted strings, booleans; one "key: value" per line).
try:
    import yaml as _yaml            # optional; never required
except Exception:                   # pragma: no cover
    _yaml = None

_KEY_RE = re.compile(r"^([A-Za-z0-9_-]+):(.*)$")
_CLOSE_RE = re.compile(r"^---\s*$")


def split_frontmatter(text):
    r"""LINE-ANCHORED frontmatter split. The opening delimiter is the very
    first line being exactly '---'; the closing delimiter is the next line
    matching ^---\s*$ ON ITS OWN LINE. A '---' glued to the end of a value
    line (e.g. `argument-hint: "[x]"---`) is NOT a delimiter — the official
    loader treats such a block as unterminated and silently drops all
    metadata, so we must reject it too.
    Returns (raw_frontmatter, body) or (None, reason)."""
    lines = text.split("\n")
    if not lines or lines[0].rstrip("\r") != "---":
        return None, "no frontmatter"
    for i in range(1, len(lines)):
        if _CLOSE_RE.match(lines[i].rstrip("\r")):
            return "\n".join(lines[1:i]), "\n".join(lines[i + 1:])
    return None, "unterminated frontmatter (closing --- must be a standalone line)"


def parse_frontmatter(text):
    """Return (dict_or_None, error_or_None, body). None dict = no/invalid
    frontmatter. Delimiters are line-anchored (see split_frontmatter)."""
    raw, rest = split_frontmatter(text)
    if raw is None:
        if rest == "no frontmatter":
            return None, None, text
        return None, rest, text
    body = rest
    if _yaml is not None:
        # STRICT: the official plugin loader parses frontmatter as YAML and
        # silently drops ALL metadata when it fails — so a YAML parse error
        # here is a real runtime defect, never something to paper over.
        try:
            data = _yaml.safe_load(raw) or {}
        except Exception as e:
            return None, "frontmatter is not valid YAML (the official " \
                         "loader would drop it): %s" % e, body
        if not isinstance(data, dict):
            return None, "frontmatter is not a mapping", body
        return {str(k): data[k] for k in data}, None, body
    # PyYAML unavailable: strict line-oriented subset approximation
    data = {}
    for line in raw.splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue
        if line[:1] in (" ", "\t"):
            continue                      # continuation of a block value
        m = _KEY_RE.match(line)
        if not m:
            return None, "invalid YAML line: %r" % line.strip(), body
        key, value = m.group(1), m.group(2).strip()
        if value and value[0] in "\"'" and value[-1:] == value[0]:
            value = value[1:-1]
        elif value.lower() in ("true", "false"):
            value = value.lower() == "true"
        if key in data:
            return None, "duplicate frontmatter key %r" % key, body
        data[key] = value
    return data, None, body


# Complete current Claude skill frontmatter set: Agent Skills open standard
# (agentskills.io: name, description, license, compatibility, metadata,
# allowed-tools) + Claude Code extensions (code.claude.com/docs/en/skills).
# Commands are merged into skills and take the same fields. Update here when
# the platform adds keys.
OFFICIAL_SKILL_KEYS = {"name", "description", "license", "compatibility",
                       "metadata", "allowed-tools", "argument-hint",
                       "arguments", "disable-model-invocation",
                       "user-invocable", "disallowed-tools", "model",
                       "effort", "context", "agent", "hooks", "paths",
                       "shell", "when_to_use"}
OFFICIAL_COMMAND_KEYS = set(OFFICIAL_SKILL_KEYS)
# The platform accepts more fields, but Solo Suite intentionally keeps shipped
# SKILL.md frontmatter deterministic. Safety and execution boundaries belong in
# the body and in user-facing command metadata, not in auto-routed skills.
SUITE_SKILL_KEYS = {"name", "description"}
# Subagent frontmatter per code.claude.com/docs/en/sub-agents (v2.1.x):
OFFICIAL_AGENT_KEYS = {"name", "description", "tools", "disallowedTools",
                       "model", "maxTurns", "skills", "memory",
                       "background", "effort", "isolation", "color",
                       "initialPrompt"}
# Fields the platform documents as IGNORED for PLUGIN-shipped subagents —
# carrying them is a defect (the author believes they do something):
PLUGIN_AGENT_REJECTED_KEYS = {"hooks", "mcpServers", "permissionMode"}
# Documented VALUES for enum-like frontmatter fields (validated, not just
# presence): isolation has exactly one documented value.
AGENT_FIELD_VALUES = {
    "isolation": {"worktree"},
    "memory": {"user", "project", "local"},
    "color": {"red", "blue", "green", "yellow", "purple", "orange",
              "pink", "cyan"},
    "effort": {"low", "medium", "high", "xhigh", "max"},
}
SKILL_FIELD_VALUES = {
    "context": {"fork"},
    # bash and powershell are the documented shells; `shell: none` is NOT a
    # documented value and must fail.
    "shell": {"bash", "powershell"},
}
PLUGIN_ROOT_REF = re.compile(r"\$\{CLAUDE_PLUGIN_ROOT\}/([^\s\"'`)\]]+)")
CWD_RELATIVE_HELPER = re.compile(r"python3?\s+scripts/[\w.-]+\.py")

# Official SchemaStore entries for Claude Code manifests (catalog-verified).
PLUGIN_SCHEMA_URL = "https://www.schemastore.org/claude-code-plugin-manifest.json"
MARKETPLACE_SCHEMA_URL = "https://www.schemastore.org/claude-code-marketplace.json"

MEMORY_FILES = ["project.md","stack.md","prd.md","architecture.md","api-contract.md",
 "data-contract.md","env-contract.md","design.md","tasks.md","decisions.md","risks.md",
 "bugs.md","tests.md","release.md","monitoring.md","handoff.md"]


def find_suite(start):
    d = os.path.abspath(start)
    while True:
        if os.path.isfile(os.path.join(d, ".claude-plugin", "marketplace.json")):
            return d
        parent = os.path.dirname(d)
        if parent == d: return None
        d = parent


# Markdown links we can resolve offline. External schemes are deliberately
# excluded: reachability is a network question and this checker is offline.
MD_LINK = re.compile(r"\[[^\]]*\]\(\s*([^)\s]+?)\s*(?:\"[^\"]*\")?\s*\)")
_EXTERNAL_SCHEME = re.compile(r"^(?:https?|mailto|tel|ftp|data):", re.I)
HEADING = re.compile(r"^#{1,6}\s+(.+?)\s*$", re.M)


def _anchor_slug(text):
    """GitHub-style heading slug: lowercase, strip punctuation, spaces->'-'."""
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"\*\*?([^*]*)\*\*?", r"\1", text)
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    return re.sub(r"\s+", "-", text)


def _portability_checks(rel, body, plug_root, fail):
    """T-017: helper-path portability, applied to EVERY component type.

    These two guards used to live inside the skills-only loop, so a
    CWD-relative helper or a dangling ${CLAUDE_PLUGIN_ROOT} path in a command
    or an agent was never inspected.
    """
    bad = 0
    for m in CWD_RELATIVE_HELPER.finditer(body):
        fail("%s: CWD-relative helper invocation %r — use "
             '"${CLAUDE_PLUGIN_ROOT}/..." instead' % (rel, m.group(0)))
        bad += 1
    for m in PLUGIN_ROOT_REF.finditer(body):
        target = m.group(1).rstrip('."')
        if not os.path.exists(os.path.join(plug_root, target)):
            fail("%s: ${CLAUDE_PLUGIN_ROOT}/%s does not exist in plugin"
                 % (rel, target))
            bad += 1
    return bad


def _markdown_link_checks(rel, body, source_path, fail):
    """T-022: local markdown links must resolve, relative to the FILE.

    Only offline-resolvable targets are checked; http/https/mailto are
    skipped because their availability is a network fact. An anchor is
    verified only when the target is a markdown file we can read, so the
    check stays deterministic.
    """
    bad = 0
    base = os.path.dirname(os.path.abspath(source_path))
    for m in MD_LINK.finditer(body):
        href = m.group(1)
        if not href or _EXTERNAL_SCHEME.match(href) or href.startswith("<"):
            continue
        path_part, _, anchor = href.partition("#")
        if not path_part:
            # same-file anchor
            path_part, target_text = source_path, body
        else:
            if path_part.startswith("/") or "${" in path_part:
                continue          # absolute/templated: not resolvable here
            target = os.path.normpath(os.path.join(base, path_part))
            if not os.path.exists(target):
                fail("%s: markdown link -> %r does not exist (resolved from "
                     "%s to %s)" % (rel, href, os.path.basename(source_path),
                                    target))
                bad += 1
                continue
            if not (anchor and target.lower().endswith(".md")):
                continue
            try:
                with open(target, encoding="utf-8") as fh:
                    target_text = fh.read()
            except OSError:
                continue
            path_part = target
        if anchor:
            slugs = {_anchor_slug(h) for h in HEADING.findall(target_text)}
            if _anchor_slug(anchor) not in slugs:
                fail("%s: markdown link -> %r has no matching heading in %s"
                     % (rel, href, os.path.basename(path_part)))
                bad += 1
    return bad


def check_plugin_content(plug_root, plug_label, fail, warn, passes):
    """Shared per-plugin checks: commands, skills, helper refs,
    ${CLAUDE_PLUGIN_ROOT} paths. Used by both suite and installed modes."""
    bad = 0
    cmds = sorted(p.replace(os.sep, "/") for p in
                  glob.glob(os.path.join(plug_root, "commands", "*.md")))
    for f in cmds:
        with open(f, encoding="utf-8") as fh:
            s = fh.read()
        fm, err, body = parse_frontmatter(s)
        rel = "%s/commands/%s" % (plug_label, os.path.basename(f))
        if fm is None:
            fail("%s: no/invalid frontmatter (%s)" % (rel, err or "missing")); bad += 1; continue
        if not str(fm.get("description", "")).strip():
            fail("%s: no description (purpose)" % rel); bad += 1
        # T-022: the hint and the body must describe the SAME argument
        # behaviour. A command that genuinely takes no arguments is valid and
        # must simply declare neither -- advertising a placeholder hint like
        # "[no arguments]" is the lie this replaced.
        hint = str(fm.get("argument-hint", "")).strip()
        consumes = bool(re.search(r"\$ARGUMENTS|\$\{ARGUMENTS\}|\$[1-9]\b",
                                  body))
        if hint and not consumes:
            fail("%s: declares argument-hint %r but the body never consumes "
                 "$ARGUMENTS or $1..$9 — either use the argument or delete "
                 "the hint" % (rel, hint)); bad += 1
        if consumes and not hint:
            fail("%s: the body consumes arguments but no argument-hint "
                 "documents them — users get no hint in the picker" % rel)
            bad += 1
        if "## Output" not in body and "## Status" not in body:
            fail("%s: no output format section" % rel); bad += 1
        unknown = set(fm) - OFFICIAL_COMMAND_KEYS
        if unknown:
            fail("%s: unknown frontmatter keys %s" % (rel, sorted(unknown))); bad += 1
        # T-017: portability guards apply to commands too, not only skills.
        bad += _portability_checks(rel, body, plug_root, fail)
        bad += _markdown_link_checks(rel, body, f, fail)
    sdirs = sorted(d for d in glob.glob(os.path.join(plug_root, "skills", "*"))
                   if os.path.isdir(d))
    for d in sdirs:
        sm = os.path.join(d, "SKILL.md")
        rel = "%s/skills/%s" % (plug_label, os.path.basename(d))
        if not os.path.isfile(sm):
            fail("%s: SKILL.md missing" % rel); bad += 1; continue
        with open(sm, encoding="utf-8") as fh:
            fm, err, body = parse_frontmatter(fh.read())
        if fm is None:
            fail("%s: no/invalid frontmatter (%s)" % (rel, err or "missing")); bad += 1; continue
        for k in ("name", "description"):
            if not str(fm.get(k, "")).strip():
                fail("%s: frontmatter missing %r" % (rel, k)); bad += 1
        extra = set(fm) - SUITE_SKILL_KEYS
        if extra:
            fail("%s: skill frontmatter must be exactly name + description; "
                 "remove %s" % (rel, sorted(extra))); bad += 1
        for key, allowed in SKILL_FIELD_VALUES.items():
            if key in fm and str(fm[key]) not in allowed:
                fail("%s: frontmatter %s=%r is not a documented value %s"
                     % (rel, key, fm[key], sorted(allowed))); bad += 1
        if str(fm.get("name", "")) != os.path.basename(d):
            warn("%s: frontmatter name %r != directory name" % (rel, fm.get("name")))
        # helper references + plugin-root existence (shared with commands and
        # agents since T-017 -- these used to run only here)
        bad += _portability_checks(rel, body, plug_root, fail)
        bad += _markdown_link_checks(rel, body, sm, fail)
        # scripts referenced in prose must ship
        for sname in set(re.findall(r"scripts/([\w-]+\.py)", body)):
            if not (os.path.isfile(os.path.join(d, "scripts", sname))
                    or glob.glob(os.path.join(plug_root, "*", "scripts", sname))
                    or glob.glob(os.path.join(plug_root, "skills", "*", "scripts", sname))):
                fail("%s: references scripts/%s which does not exist" % (rel, sname)); bad += 1
    agents = sorted(p.replace(os.sep, "/") for p in
                    glob.glob(os.path.join(plug_root, "agents", "*.md")))
    for f in agents:
        rel = "%s/agents/%s" % (plug_label, os.path.basename(f))
        with open(f, encoding="utf-8") as fh:
            fm, err, body = parse_frontmatter(fh.read())
        if fm is None:
            fail("%s: no/invalid frontmatter (%s)" % (rel, err or "missing")); bad += 1; continue
        for k in ("name", "description"):
            if not str(fm.get(k, "")).strip():
                fail("%s: agent frontmatter missing %r" % (rel, k)); bad += 1
        ignored = set(fm) & PLUGIN_AGENT_REJECTED_KEYS
        if ignored:
            fail("%s: %s are IGNORED on plugin-shipped agents — remove "
                 "them (they silently do nothing here)"
                 % (rel, sorted(ignored))); bad += 1
        unknown = set(fm) - OFFICIAL_AGENT_KEYS - PLUGIN_AGENT_REJECTED_KEYS
        if unknown:
            fail("%s: non-official agent frontmatter keys %s" % (rel, sorted(unknown))); bad += 1
        for key, allowed in AGENT_FIELD_VALUES.items():
            if key in fm and str(fm[key]) not in allowed:
                fail("%s: agent frontmatter %s=%r is not a documented value %s"
                     % (rel, key, fm[key], sorted(allowed))); bad += 1
        if str(fm.get("name", "")) != os.path.basename(f)[:-3]:
            warn("%s: agent name %r != filename" % (rel, fm.get("name")))
        # T-017: agents get the same portability and link guards.
        bad += _portability_checks(rel, body, plug_root, fail)
        bad += _markdown_link_checks(rel, body, f, fail)
    return bad, len(cmds), len(sdirs) + len(agents)


def installed_mode(plug_root, fails, warns, passes):
    def fail(m): fails.append(m)
    def warn(m): warns.append(m)
    pj = os.path.join(plug_root, ".claude-plugin", "plugin.json")
    try:
        with open(pj, encoding="utf-8") as fh:
            d = json.load(fh)
        for k in ("name", "version", "description"):
            if k not in d:
                fail("plugin.json missing key %s" % k)
        name = d.get("name", os.path.basename(plug_root))
    except Exception as e:
        fail("invalid plugin.json: %s" % e)
        name = os.path.basename(plug_root)
    bad, ncmd, nskill = check_plugin_content(plug_root, name, fail, warn, passes)
    if not bad:
        passes.append("installed plugin %r: %d commands + %d skills structurally valid"
                      % (name, ncmd, nskill))


def main():
    arg_root = sys.argv[1] if len(sys.argv) > 1 else "."
    proj = sys.argv[2] if len(sys.argv) > 2 else "."
    fails, warns, passes = [], [], []
    def fail(m): fails.append(m)
    def warn(m): warns.append(m)

    suite = find_suite(arg_root)
    if not suite:
        cand = os.path.abspath(arg_root)
        if os.path.isfile(os.path.join(cand, ".claude-plugin", "plugin.json")):
            print("== solo-suite self-check (INSTALLED-PLUGIN MODE) ==")
            installed_mode(cand, fails, warns, passes)
            for m in passes: print("PASS  " + m)
            for m in warns:  print("WARN  " + m)
            for m in fails:  print("FAIL  " + m)
            print("== %d pass, %d warn, %d fail ==" % (len(passes), len(warns), len(fails)))
            print("note: static structure checks only — passing is NOT proof of runtime health")
            sys.exit(1 if fails else 0)
        fail("no suite root (.claude-plugin/marketplace.json) or plugin root "
             "(.claude-plugin/plugin.json) found from %r" % arg_root)
        suite = "."
    if suite != ".":
        os.chdir(suite)

    # 1) plugin.json all valid (+ recommended metadata fields)
    pjs = sorted(glob.glob("plugins/*/.claude-plugin/plugin.json"))
    bad = 0
    for f in pjs:
        try:
            with open(f, encoding="utf-8") as fh:
                d = json.load(fh)
            for k in ("name","version","description"):
                if k not in d: fail("%s missing key %s" % (f,k)); bad += 1
            for k in ("$schema", "displayName", "license", "repository", "homepage"):
                if k not in d: warn("%s missing recommended key %s" % (f, k))
            if d.get("$schema") not in (None, PLUGIN_SCHEMA_URL):
                fail("%s $schema %r != SchemaStore %s"
                     % (f, d.get("$schema"), PLUGIN_SCHEMA_URL)); bad += 1
        except Exception as e:
            fail("invalid JSON %s: %s" % (f,e)); bad += 1
    if not bad: passes.append("all %d plugin.json valid" % len(pjs))

    # 2+3) per-plugin content: commands, skills, frontmatter (proper YAML;
    # suite skills use exactly name + description), helper references,
    # ${CLAUDE_PLUGIN_ROOT} paths
    cmds = sorted(p.replace(os.sep, "/") for p in glob.glob("plugins/*/commands/*.md"))
    total_bad = 0
    for plug_dir in sorted(glob.glob("plugins/*")):
        if not os.path.isdir(plug_dir): continue
        b, _, _ = check_plugin_content(plug_dir, plug_dir.replace(os.sep, "/"),
                                       fail, warn, passes)
        total_bad += b
    sdirs = sorted(d for d in glob.glob("plugins/*/skills/*") if os.path.isdir(d))
    if not total_bad:
        passes.append("all %d commands + %d skills/agents structurally valid "
                      "(skill frontmatter exactly name + description; command/"
                      "agent frontmatter uses official keys; helper paths "
                      "resolve via ${CLAUDE_PLUGIN_ROOT})" % (len(cmds), len(sdirs)))

    # 4+5) README + marketplace counts match reality
    real = dict(plugins=len(glob.glob("plugins/*/.claude-plugin/plugin.json")),
                skills=len(glob.glob("plugins/*/skills/*/SKILL.md")),
                commands=len(cmds),
                scripts=len(glob.glob("plugins/*/skills/*/scripts/*.py")),
                agents=len(glob.glob("plugins/*/agents/*.md")))
    if os.path.isfile("README.md"):
        with open("README.md", encoding="utf-8") as fh:
            rd = fh.read()
        m = re.search(r"\*\*(\d+) plugins\*\*.*?\*\*(\d+) skills\*\*.*?\*\*(\d+) slash commands\*\*.*?\*\*(\d+) stdlib.*?\*\*(\d+) room-\* agents\*\*", rd, re.S)
        if not m: warn("README: counts line not found to verify")
        else:
            claimed = dict(zip(("plugins","skills","commands","scripts","agents"), map(int, m.groups())))
            diff = {k: (claimed[k], real[k]) for k in real if claimed[k] != real[k]}
            if diff: fail("README counts mismatch (claimed, real): %s" % diff)
            else: passes.append("README counts match reality %s" % real)
        # standalone-skill claim must document the shared url_guard dependency
        cm = re.search(r"\*\*Prefer no plugin\?\*\*.*?(?:\n\n|\Z)", rd, re.S)
        if cm and "url_guard" not in cm.group(0):
            fail("README standalone-copy claim does not document the shared "
                 "lib/url_guard.py dependency of the script-bundling skills")
        elif cm:
            passes.append("README standalone-copy claim documents the url_guard dependency")
    # Every shipped url_guard.py must be byte-identical to the canonical one.
    # Plugins install independently, so the SSRF guard is mirrored rather than
    # shared; mirroring is only safe if divergence fails closed here.
    guard_copies = sorted(
        p.replace("\\", "/") for p in glob.glob("plugins/*/lib/url_guard.py"))
    if len(guard_copies) > 1:
        # site-doctor's copy is canonical when present; otherwise compare the
        # copies against each other. A suite that ships none (or exactly one)
        # has nothing that can drift.
        canonical = "plugins/site-doctor/lib/url_guard.py"
        if canonical not in guard_copies:
            canonical = guard_copies[0]
        with open(canonical, "rb") as fh:
            canonical_bytes = fh.read()
        drifted = []
        for path in guard_copies:
            with open(path, "rb") as fh:
                if fh.read() != canonical_bytes:
                    drifted.append(path)
        if drifted:
            fail("url_guard.py copies have drifted from %s: %s"
                 % (canonical, drifted))
        else:
            passes.append("all %d url_guard.py copies are byte-identical"
                          % len(guard_copies))
    with open(".claude-plugin/marketplace.json", encoding="utf-8") as fh:
        mk = json.load(fh)
    if mk.get("$schema") not in (None, MARKETPLACE_SCHEMA_URL):
        fail("marketplace $schema %r != SchemaStore %s"
             % (mk.get("$schema"), MARKETPLACE_SCHEMA_URL))
    if len(mk.get("plugins", [])) != real["plugins"]:
        fail("marketplace lists %d plugins, filesystem has %d" % (len(mk.get("plugins",[])), real["plugins"]))
    else: passes.append("marketplace lists all %d plugins" % real["plugins"])
    md = mk.get("metadata", {})
    # Count fields were REMOVED from marketplace metadata in v1.0.15: the
    # CLI treats them as unknown fields and warns. The canonical counts now
    # live in the README line (verified above against the filesystem) and
    # in tests/test_inventory.py's pinned literals. Their PRESENCE here is
    # now the defect:
    for k in ("plugins", "skills", "commands", "scripts", "agents",
              "license"):
        if k in md:
            fail("marketplace metadata carries unsupported field %r — the "
                 "CLI warns on it; counts belong in README + "
                 "tests/test_inventory.py" % k)
    missing_src = [p.get("source") for p in mk.get("plugins",[]) if not os.path.isdir(p.get("source","").lstrip("./"))]
    if missing_src: fail("marketplace sources missing on disk: %s" % missing_src)

    # 6) duplicate command names (same plugin = error; cross-plugin is fine)
    seen = {}
    for f in cmds:
        plug = f.split("/")[1]; name = os.path.basename(f)
        seen.setdefault((plug,name), []).append(f)
    dups = {k:v for k,v in seen.items() if len(v) > 1}
    if dups: fail("duplicate command names: %s" % dups)
    else: passes.append("no duplicate command names")

    # 7) no broken references between commands (slash refs + **skill** refs)
    skills = {os.path.basename(os.path.dirname(p)) for p in glob.glob("plugins/*/skills/*/SKILL.md")}
    cmdset = {"/%s:%s" % (f.split("/")[1], os.path.basename(f)[:-3]) for f in cmds}
    bad = 0
    for f in cmds + sorted(glob.glob("plugins/*/skills/*/SKILL.md")):
        with open(f, encoding="utf-8") as fh:
            body = fh.read()
        for ref in set(re.findall(r"(?<![A-Za-z0-9])(/[a-z][a-z0-9-]*:(?:[a-z][a-z0-9-]*\*?|\*))", body)):
            if re.search(re.escape(ref) + r"[a-z0-9-]", body): continue
            plug, rest = ref[1:].split(":", 1)
            if rest.endswith("*"):
                prefix = rest[:-1]
                if not any(c.startswith("/%s:%s" % (plug, prefix)) for c in cmdset):
                    fail("%s: wildcard %s matches no existing command" % (f, ref)); bad += 1
            elif ref not in cmdset:
                fail("%s references missing command %s" % (f, ref)); bad += 1
        for m in re.findall(r"\*\*([a-z][a-z0-9-]+)\*\* skill", body):
            if m not in skills: fail("%s references missing skill %s" % (f, m)); bad += 1
        for m in re.findall(r"[Uu]se the `?([a-z][a-z0-9]*(?:-[a-z0-9]+)+)`? skill", body):
            if m not in skills: fail("%s references missing skill %s (unbolded)" % (f, m)); bad += 1
    if not bad: passes.append("no broken command/skill references (wildcards resolved)")

    # 7b) marketplace descriptions reference only existing commands
    bad = 0
    descs = [("metadata", md.get("description",""))] + \
            [(p.get("name"), p.get("description","")) for p in mk.get("plugins", [])]
    for name, desc in descs:
        for ref in set(re.findall(r"(?<![A-Za-z0-9])(/[a-z][a-z0-9-]*:(?:[a-z][a-z0-9-]*\*?|\*))", desc)):
            plug, rest = ref[1:].split(":", 1)
            if rest.endswith("*"):
                if not any(c.startswith("/%s:%s" % (plug, rest[:-1])) for c in cmdset):
                    fail("marketplace %s description: wildcard %s matches nothing" % (name, ref)); bad += 1
            elif ref not in cmdset:
                fail("marketplace %s description references missing command %s" % (name, ref)); bad += 1
    if not bad: passes.append("marketplace descriptions reference only existing commands")

    # 7b2) EVERY count-bearing description matches the filesystem (v1.0.17,
    # blocker 2): the root metadata, every marketplace entry, and every
    # plugins/*/.claude-plugin/plugin.json description — never only the
    # root description. Patterns cover the suite's narrative counts
    # (room-* agents, plugins, skills, commands, stdlib scripts,
    # agentsrooms templates, gate categories, .solo memory files).
    def _counts_for(plug=None):
        base = os.path.join("plugins", plug) if plug else "plugins/*"
        return {
            "plugins": real["plugins"],
            "skills": len(glob.glob(os.path.join(base, "skills", "*",
                                                 "SKILL.md"))),
            "commands": len(glob.glob(os.path.join(base, "commands",
                                                   "*.md"))),
            "scripts": len(glob.glob(os.path.join(base, "skills", "*",
                                                  "scripts", "*.py"))),
            "agents": real["agents"],
            "rooms": len(glob.glob("plugins/ai/skills/agent-room-templates/"
                                   "agentsrooms/*.json")),
        }
    _gate_schema = os.path.join("plugins", "gate", "skills",
                                "production-readiness-reviewer", "schema",
                                "gate-evidence-v1.schema.json")
    _n_categories = None
    if os.path.isfile(_gate_schema):
        try:
            with open(_gate_schema, encoding="utf-8") as fh:
                _n_categories = len(json.load(fh)["definitions"]
                                    ["category"]["enum"])
        except Exception:
            _n_categories = None

    def _desc_count_claims(desc, plug=None):
        inv = _counts_for(plug)
        claims = []
        for m in re.finditer(r"(\d+) room-\* agents?", desc):
            claims.append((int(m.group(1)), inv["agents"],
                           "room-* agents"))
        for m in re.finditer(r"(\d+) component plugins", desc):
            claims.append((int(m.group(1)), inv["plugins"] - 1,
                           "component plugins"))
        for m in re.finditer(r"(?<!component )(\d+) plugins\b", desc):
            claims.append((int(m.group(1)), inv["plugins"], "plugins"))
        for m in re.finditer(r"(\d+) (?:[a-z][a-z/-]* ){0,3}skills\b",
                             desc):
            claims.append((int(m.group(1)), inv["skills"], "skills"))
        for m in re.finditer(r"(\d+) (?:slash )?commands\b", desc):
            claims.append((int(m.group(1)), inv["commands"], "commands"))
        for m in re.finditer(r"(\d+) stdlib (?:helper )?scripts\b", desc):
            claims.append((int(m.group(1)), inv["scripts"],
                           "stdlib scripts"))
        for m in re.finditer(r"(\d+) agentsrooms/\*\.json rooms", desc):
            claims.append((int(m.group(1)), inv["rooms"], "agentsrooms"))
        if _n_categories is not None:
            for m in re.finditer(r"(\d+) categories\b", desc):
                claims.append((int(m.group(1)), _n_categories,
                               "gate categories"))
        for m in re.finditer(r"(\d+)-file \.solo/", desc):
            claims.append((int(m.group(1)), len(MEMORY_FILES),
                           ".solo memory files"))
        for m in re.finditer(r"(\d+)-role cycle", desc):
            claims.append((int(m.group(1)), inv["plugins"] - 1,
                           "role cycle (= component plugins)"))
        return claims

    bad = 0
    checked_claims = 0
    described = [("marketplace metadata", md.get("description", ""), None)]
    described += [("marketplace entry %r" % p_.get("name"),
                   p_.get("description", ""),
                   p_.get("source", "").lstrip("./").split("/")[-1] or None)
                  for p_ in mk.get("plugins", [])]
    for pjf in pjs:
        with open(pjf, encoding="utf-8") as fh:
            d_ = json.load(fh)
        described.append(("%s description" % pjf,
                          d_.get("description", ""),
                          pjf.split("/")[1] if "/" in pjf
                          else pjf.split(os.sep)[1]))
    for where, desc, plug in described:
        for claimed, actual, label in _desc_count_claims(desc, plug):
            checked_claims += 1
            if claimed != actual:
                fail("%s claims %d %s but the filesystem has %d"
                     % (where, claimed, label, actual)); bad += 1
    if not bad and checked_claims:
        passes.append("all %d count-bearing description claims match the "
                      "filesystem (metadata + every marketplace entry + "
                      "every plugin.json)" % checked_claims)

    # 7c) versions agree: CHANGELOG top entry == metadata.version; the top
    # entry's "### Versions" plugin bumps must match plugin.json reality
    mv = md.get("version")
    if os.path.isfile("CHANGELOG.md"):
        with open("CHANGELOG.md", encoding="utf-8") as fh:
            ch = fh.read()
        top = re.search(r"^## (\d+\.\d+\.\d+)", ch, re.M)
        if not top: warn("CHANGELOG.md has no '## x.y.z' entry to verify")
        elif mv and top.group(1) != mv:
            fail("CHANGELOG top entry %s != marketplace metadata.version %s" % (top.group(1), mv))
        else: passes.append("CHANGELOG top entry matches metadata.version (%s)" % mv)
        # LINE-ANCHORED top-entry extraction (v1.0.17): the old
        # substring split broke at the first "###" subsection (its text
        # contains "## "), so a "### Versions" section was never parsed.
        _secs = re.split(r"(?m)^## ", ch)
        top_section = _secs[1] if len(_secs) > 1 else ""
        vers = dict((n, v) for n, v in re.findall(
            r"\b([a-z][a-z-]*) [0-9.]+ (?:->|→) ([0-9.]+)", top_section))
        for pjf in pjs:
            with open(pjf, encoding="utf-8") as fh:
                d = json.load(fh)
            n = d.get("name")
            if n in vers and vers[n] != d.get("version"):
                fail("CHANGELOG says %s -> %s but plugin.json has %s"
                     % (n, vers[n], d.get("version")))
    else: warn("CHANGELOG.md missing — version bumps are undocumented")
    for dx in glob.glob("*.docx"):
        if "site-doctor" not in dx: continue
        try:
            x = zipfile.ZipFile(dx).read("word/document.xml").decode("utf-8", "ignore")
            got = re.search(r"v(\d+\.\d+\.\d+)", x)
            with open("plugins/site-doctor/.claude-plugin/plugin.json", encoding="utf-8") as fh:
                sd = json.load(fh).get("version")
            if got and sd:
                if got.group(1) != sd: warn("%s says v%s but site-doctor is %s" % (dx, got.group(1), sd))
                else: passes.append("%s version matches site-doctor (%s)" % (dx, sd))
        except Exception as e: warn("could not read %s: %s" % (dx, e))

    # bundled JSON resources (agentsrooms templates, schemas) all parse
    bundled = [j for j in glob.glob("plugins/*/skills/*/**/*.json", recursive=True)]
    badj = 0
    for j in bundled:
        try:
            with open(j, encoding="utf-8") as fh:
                json.load(fh)
        except Exception as e: fail("bundled JSON invalid %s: %s" % (j, e)); badj += 1
    if bundled and not badj: passes.append("all %d bundled JSON resources parse" % len(bundled))

    # 7d) agentroom templates pass the static room validator (+ schema ships)
    rooms = sorted(p.replace(os.sep, "/") for p in glob.glob("plugins/*/skills/*/agentsrooms/*.json"))
    vpath = os.path.join("plugins", "ai", "skills", "agent-room-templates", "scripts", "validate_rooms.py")
    spath = os.path.join("plugins", "ai", "skills", "agent-room-templates", "schema", "agentroom-v1.schema.json")
    if rooms and os.path.isfile(vpath):
        if not os.path.isfile(spath):
            warn("agentroom schema file missing: %s" % spath)
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location("validate_rooms", vpath)
            vr = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(vr)
            problems = vr.validate_files(rooms, suite_root=".")
            for m in problems:
                fail("agentroom %s" % m)
            if not problems:
                passes.append("all %d agentroom templates pass validate_rooms "
                              "(schema, graph, steward, implicit writes, gates)" % len(rooms))
        except Exception as e:
            warn("could not run validate_rooms.py: %s" % e)
    elif rooms:
        warn("agentroom templates present but validate_rooms.py not found")

    # 8) .solo memory files
    if proj != "-":
        solo = os.path.join(os.path.abspath(proj), ".solo")
        if not os.path.isdir(solo):
            warn(".solo/ not found at %s — run /solo:start-session to initialize (skip with '-')" % proj)
        else:
            missing = [f for f in MEMORY_FILES if not os.path.isfile(os.path.join(solo, f))]
            if missing: warn(".solo/ missing files (created on first write): %s" % ", ".join(missing))
            else: passes.append(".solo/ has all %d standard memory files" % len(MEMORY_FILES))

    print("== solo-suite self-check ==")
    for m in passes: print("PASS  " + m)
    for m in warns:  print("WARN  " + m)
    for m in fails:  print("FAIL  " + m)
    print("== %d pass, %d warn, %d fail ==" % (len(passes), len(warns), len(fails)))
    print("note: static structure checks only — passing is NOT proof of runtime health")
    sys.exit(1 if fails else 0)

def _harden_streams():
    """Never abort a report on a character the console cannot encode.

    Claude Code captures helper stdout through a pipe, so on Windows the
    stream encoding is the ANSI codepage (cp1252) rather than UTF-8. A CJK
    path, an emoji, or a "→" in captured content then raises
    UnicodeEncodeError mid-write -- the tool announces a finding and dies
    before printing where it is. Escaping instead of raising keeps ASCII
    output byte-identical while making that class of crash impossible.

    Called from __main__ only: importing this module (as the tests do) must
    never mutate the importing process's streams.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="backslashreplace")
        except (AttributeError, ValueError, OSError):
            pass


if __name__ == "__main__":
    _harden_streams()
    main()
