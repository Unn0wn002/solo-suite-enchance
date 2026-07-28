#!/usr/bin/env python3
r"""gate_policy.py — the SINGLE shared policy module for solo-suite gate
evidence. Used by BOTH record_evidence.py (the only writer of verified
records) and check_evidence.py (the gate) so the two can never drift.
Stdlib only.

WHAT LIVES HERE
  * the 14 ordered categories, 6 profiles, MANDATORY set, N/A applicability
    matrix, score denominator, launch thresholds, and launch-status decision.
    Direct gates and AgentRoom validators import these objects; there is no
    second profile/scoring policy to keep in sync.
  * the per-category COMMAND POLICY: full-argv validators, not prefixes.
    `git log`/`git ls-files` are NOT evidence of anything. --help,
    --version, dry-runs, list-only modes, unrelated paths, and arbitrary
    suffixes are rejected.
  * CANONICAL EXECUTABLE IDENTITY for EVERY accepted family: argv[0] is
    resolved through PATH (shutil.which) or must be an absolute path;
    unresolved executables and executables resolving inside the project/
    runtime directories are rejected; the recorder executes and records
    the RESOLVED absolute path and the checker re-validates it.
  * LIVE-TARGET + RUN BINDING: URL/domain evidence must aim at hosts
    recorded in the COMMITTED .solo/stack.md at HEAD; gh-run evidence must
    carry --json headSha,conclusion,status and its captured output must
    name the derived HEAD with conclusion "success".
  * ENDPOINT CONTRACTS (v1.0.17): deployment curl evidence must hit the
    COMMITTED `version-endpoint:` from .solo/stack.md with a bounded
    timeout, and the captured response (headers/body) must contain the
    derived HEAD — the deployed result is BOUND to FINAL_SHA, a generic
    200 proves nothing. Monitoring curl evidence must hit the COMMITTED
    `health-endpoint:` with a bounded timeout and the captured response
    must satisfy an EXPLICIT health contract (JSON status/state/health in
    the OK set, or the committed `health-expect:` marker) — a generic
    homepage response is refused.
  * git source identity helpers: HEAD and the COMMITTED-tree digest are
    derived from git objects (`git rev-parse`, `git ls-tree -r HEAD`),
    never from caller assertions or mutable working-tree bytes
  * the working-tree cleanliness rule: any modified/deleted/untracked path
    outside the generated runtime directories disqualifies the state.
    ONLY these two generated runtime paths are excluded, ever:
    .solo/gate-evidence/ and .solo/run-state/ (UNTRACKED_RUNTIME_DIRS).
  * the single supported EVIDENCE WORKFLOW: .solo/gate-evidence/ AND
    .solo/run-state/ stay UNTRACKED (gitignored). Runtime state tracked
    in HEAD is an unsupported state that both tools refuse.
  * a built-in strict JSON-Schema evaluator (draft-07 subset with $ref)
    so records are ALWAYS validated against the bundled schema — the
    external `jsonschema` package is optional, never required
  * `verify-artifact` CLI mode: the executable CATEGORY-SPECIFIC content
    check used as the evidence command for document-backed categories
    (product, architecture, design, documentation — deployment and
    monitoring are NOT document-backed and never pass on
    release.md/monitoring.md content alone). v1.0.17: each category has
    required headings, substantive-content thresholds (bytes, words,
    vocabulary), placeholder/filler rejection, and required
    identifier/decision fields — "200 bytes and two headings" is gone.

TRUST MODEL — SELF-ATTESTED LOCAL EVIDENCE. These records are NOT
cryptographic attestations: they are unsigned JSON written by a local
tool. They make honest workflows mechanically checkable (real exit codes,
digests recomputed from git objects and artifact bytes) but a hostile
actor with repo access can fabricate them. Treat acceptance as
"self-attested local evidence verified against the current checkout"; a
trusted CI identity/signature is the upgrade path.
"""
import argparse
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.parse

CATEGORY_ORDER = (
    "product", "architecture", "design", "frontend", "backend", "database",
    "security", "testing", "performance", "seo", "analytics", "deployment",
    "monitoring", "documentation",
)
CATEGORY_LABELS = {
    category: ("SEO" if category == "seo" else category.title())
    for category in CATEGORY_ORDER
}
CATEGORY_LABEL_ORDER = tuple(CATEGORY_LABELS[item] for item in CATEGORY_ORDER)
LABEL_CATEGORIES = {label: category for category, label in CATEGORY_LABELS.items()}
CATEGORIES = frozenset(CATEGORY_ORDER)

PROFILE_ORDER = (
    "public-marketing-site", "saas-application", "e-commerce",
    "internal-application", "api-service", "library-package",
)
RECOGNIZED_PROFILES = frozenset(PROFILE_ORDER)
MANDATORY = frozenset({
    "product", "architecture", "security", "testing", "deployment",
    "monitoring", "documentation",
})
NA_ALLOWED = {
    "design": frozenset({"api-service", "library-package"}),
    "frontend": frozenset({"api-service", "library-package"}),
    "backend": frozenset({"public-marketing-site", "library-package"}),
    "database": frozenset({"public-marketing-site", "library-package"}),
    "performance": frozenset({"library-package"}),
    "seo": frozenset({"internal-application", "api-service", "library-package"}),
    "analytics": frozenset({"internal-application", "api-service", "library-package"}),
}
assert not (set(NA_ALLOWED) & MANDATORY)
assert set(NA_ALLOWED) | MANDATORY == CATEGORIES
PROFILE_NA_ALLOWED = {
    profile: frozenset(
        category for category in CATEGORY_ORDER
        if profile in NA_ALLOWED.get(category, ())
    )
    for profile in PROFILE_ORDER
}

POINTS_PER_CATEGORY = 10
BLOCKED_BELOW_SCORE = 70
SAFE_TO_LAUNCH_SCORE = 85
SAFE_TO_LAUNCH_CATEGORY_MINIMUM = 7
LAUNCH_STATUSES = frozenset({
    "BLOCKED", "SAFE WITH WARNINGS", "SAFE TO LAUNCH",
})


def normalized_score(total_score, applicable_category_count):
    """Return the one canonical N/A-adjusted production score.

    An evidence-only score may have zero applicable categories; it normalizes
    to zero and must be labelled insufficient by its caller.  A production
    profile can never reach zero because the seven mandatory categories may
    not be N/A.
    """
    if (not isinstance(total_score, int) or isinstance(total_score, bool) or
            not isinstance(applicable_category_count, int) or
            isinstance(applicable_category_count, bool)):
        raise ValueError("score and applicable category count must be integers")
    if applicable_category_count < 0 or applicable_category_count > len(CATEGORY_ORDER):
        raise ValueError("applicable category count is outside the production contract")
    applicable_max = applicable_category_count * POINTS_PER_CATEGORY
    if total_score < 0 or total_score > applicable_max:
        raise ValueError("total score is outside the applicable denominator")
    if applicable_max == 0:
        return 0
    return round(total_score / applicable_max * 100)


def expected_launch_status(normalized, applicable_scores, blockers=(), warnings=()):
    """Derive the only permitted launch status from validated gate facts."""
    if (not isinstance(normalized, int) or isinstance(normalized, bool) or
            normalized < 0 or normalized > 100):
        raise ValueError("normalized score must be an integer from 0 to 100")
    scores = tuple(applicable_scores)
    if (not scores or any(not isinstance(score, int) or isinstance(score, bool)
                          or score < 0 or score > POINTS_PER_CATEGORY
                          for score in scores)):
        raise ValueError("applicable scores must be non-empty integers from 0 to 10")
    if blockers or normalized < BLOCKED_BELOW_SCORE:
        return "BLOCKED"
    if (normalized >= SAFE_TO_LAUNCH_SCORE and
            min(scores) >= SAFE_TO_LAUNCH_CATEGORY_MINIMUM and
            not warnings):
        return "SAFE TO LAUNCH"
    return "SAFE WITH WARNINGS"


def evaluate_production_gate(scores, profile, not_applicable=(), blockers=(),
                             warnings=()):
    """Apply the shared profile, denominator, threshold, and status policy.

    ``scores`` is keyed by the lowercase canonical categories.  N/A category
    values are ignored, but callers should carry zero in serialized evidence
    so a skipped control can never inflate ``total_score``.
    """
    if profile not in RECOGNIZED_PROFILES:
        raise ValueError("unrecognized project profile: %r" % profile)
    if not isinstance(scores, dict) or set(scores) != CATEGORIES:
        raise ValueError("scores must cover the exact 14 production categories")
    na_categories = frozenset(not_applicable)
    unknown_na = na_categories - CATEGORIES
    if unknown_na:
        raise ValueError("unknown N/A categories: %s" % sorted(unknown_na))
    forbidden_na = na_categories - PROFILE_NA_ALLOWED[profile]
    if forbidden_na:
        raise ValueError(
            "profile %r does not permit N/A for: %s" %
            (profile, ", ".join(sorted(forbidden_na)))
        )
    applicable = tuple(
        category for category in CATEGORY_ORDER if category not in na_categories
    )
    applicable_scores = []
    for category in applicable:
        score = scores[category]
        if (not isinstance(score, int) or isinstance(score, bool) or
                score < 0 or score > POINTS_PER_CATEGORY):
            raise ValueError("score for %s must be an integer from 0 to 10" % category)
        applicable_scores.append(score)
    total = sum(applicable_scores)
    normalized = normalized_score(total, len(applicable))
    return {
        "profile": profile,
        "not_applicable_categories": tuple(
            category for category in CATEGORY_ORDER if category in na_categories
        ),
        "applicable_categories": applicable,
        "applicable_category_count": len(applicable),
        "applicable_max": len(applicable) * POINTS_PER_CATEGORY,
        "total_score": total,
        "normalized_score": normalized,
        "launch_status": expected_launch_status(
            normalized, applicable_scores, blockers, warnings,
        ),
    }


# A category record proves one captured command, not every independent launch
# control associated with that category.  These controls therefore require
# separately cited command/live-test evidence in the human launch review.  The
# direct checker exposes this list machine-readably, while the launch reviewer
# fails closed when an applicable item remains unverified.
REVIEWER_REQUIRED_CONTROLS = {
    "accessibility-core-flows": "blocking WCAG failures on core flows",
    "authentication": "required authentication and session behavior",
    "backup-restore": "a current backup plus a tested restore result",
    "committed-secrets": "a dedicated repository secret scan",
    "error-tracking": "live error capture and alert delivery",
    "mobile-core-flows": "core flows at the required mobile breakpoints",
    "payments": "the applicable payment flow and failure handling",
    "rls-authorization": "live authorization/RLS behavior where applicable",
    "rollback": "a tested rollback result, not only a written plan",
    "transactional-email": "actual delivery behavior, not only DNS records",
}


EVIDENCE_DIR = ".solo/gate-evidence"
RUN_STATE_DIR = ".solo/run-state"
PROJECT_PROFILE_SOURCE = ".solo/project.md"
# Untracked-by-design runtime directories: evidence records and run SHAs
# (BASE/INTEGRATION/FINAL) live here so that writing them never changes the
# commit they describe. Both must be gitignored.
UNTRACKED_RUNTIME_DIRS = (EVIDENCE_DIR, RUN_STATE_DIR)
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")

# ---------------------------------------------------------------------------
# COMMAND POLICY — full-argv validation, never prefix matching
# ---------------------------------------------------------------------------
# Tokens that turn any command into a no-op / info query. Rejected anywhere.
DENY_TOKENS = {"--help", "-h", "--version", "-V", "--dry-run", "--dryRun",
               "--collect-only", "--co", "--collectonly", "--list",
               "--list-only", "--listTests", "--showConfig", "--show-config",
               # zero-test escape hatches: a runner that PASSES with no
               # tests proves nothing (Jest/Vitest/Playwright & friends)
               "--passWithNoTests", "--pass-with-no-tests",
               "--passwithnotests", "--allow-no-tests", "--allowNoTests",
               "--no-tests=pass", "--if-present", "--ignore-scripts"}


def _deny_normalized(tok):
    """Case-insensitive, '='-suffix-insensitive deny check so
    --passWithNoTests=true or --PASS-WITH-NO-TESTS cannot sneak by."""
    base = tok.split("=", 1)[0].strip().lower()
    return base in {t.split("=", 1)[0].lower() for t in DENY_TOKENS}
_PY = ("python", "python3")
_MODULE_RE = re.compile(r"^[A-Za-z_][\w.]*$")
_URL_RE = re.compile(r"^https?://[^\s]+$")
_DOMAIN_RE = re.compile(r"^[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")


def _safe_http_url_shape(url):
    """Pure, offline URL checks shared by policy validation and execution.

    Credentials and secret-like query parameters must never enter evidence
    argv/JSON/artifacts.  DNS/IP checks live in ``check_http_targets_safe`` so
    the evidence checker can revalidate an existing record without network
    access.
    """
    if not isinstance(url, str) or not _URL_RE.match(url):
        return False, "target must be one http(s) URL"
    try:
        parts = urllib.parse.urlsplit(url)
        _ = parts.port  # force invalid-port validation
    except ValueError as e:
        return False, "invalid URL: %s" % e
    if not parts.hostname:
        return False, "URL has no hostname"
    if parts.username is not None or parts.password is not None:
        return False, "URL userinfo/credentials are forbidden"
    if parts.fragment:
        return False, "URL fragments are not permitted in evidence commands"
    sensitive = re.compile(
        r"(?i)(?:^|[_-])(token|secret|password|passwd|pwd|api[_-]?key|"
        r"signature|credential|authorization)(?:$|[_-])")
    for key, _value in urllib.parse.parse_qsl(parts.query,
                                               keep_blank_values=True):
        if sensitive.search(key):
            return False, ("URL query parameter %r looks credential-bearing; "
                           "credentials must not be placed in argv" % key)
    return True, None


_URL_GUARD = None


def _load_url_guard():
    """Load the bundled site-doctor URL guard without changing sys.path."""
    global _URL_GUARD
    if _URL_GUARD is not None:
        return _URL_GUARD
    path = os.path.join(_suite_root(), "plugins", "site-doctor", "lib",
                        "url_guard.py")
    if not os.path.isfile(path):
        raise RuntimeError("bundled site-doctor url_guard.py is missing")
    spec = importlib.util.spec_from_file_location("solo_suite_url_guard", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load bundled site-doctor url_guard.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _URL_GUARD = module
    return module


def check_http_targets_safe(argv):
    """Resolve and reject private/metadata HTTP targets before execution.

    This intentionally runs only immediately before a command is executed;
    ``validate_command`` remains an offline/reproducible checker.  The shared
    site-doctor guard validates schemes, blocked hostnames, every DNS answer,
    loopback/private/link-local/metadata/routedness, and malformed ports.
    Curl redirect-following flags are not accepted by the Gate policy, so
    there is no unvalidated redirect hop.
    """
    urls = [t for t in argv[1:] if isinstance(t, str) and _URL_RE.match(t)]
    if not urls:
        return True, None
    try:
        guard = _load_url_guard()
    except Exception as e:
        return False, "URL safety guard unavailable (fail closed): %s" % e
    for url in urls:
        ok, why = _safe_http_url_shape(url)
        if not ok:
            return False, why
        try:
            guard.check_url(url, allow_http=True)
        except Exception as e:
            return False, "unsafe HTTP target %r: %s" % (url, e)
    return True, None


def _deny_hit(argv):
    return next((t for t in argv if t in DENY_TOKENS
                 or _deny_normalized(t)), None)


def _norm_exe(tok):
    base = os.path.basename(tok).lower()
    return base[:-4] if base.endswith(".exe") else base


def _inside(path, root):
    rp, rr = os.path.realpath(path), os.path.realpath(root)
    return rp == rr or rp.startswith(rr + os.sep)


def resolve_executable(tok, root):
    """CANONICAL EXECUTABLE IDENTITY for argv[0] of EVERY accepted command
    family (python/python3, pytest, npm, npx, go, cargo, make, curl, gh,
    pip-audit, govulncheck, alembic, ...) — basenames are never trusted
    alone, and this rule applies uniformly:

      * a BARE token (no path separator) is resolved through PATH with
        shutil.which(); an unresolved token is refused;
      * a token WITH a path separator must be an ABSOLUTE path to an
        existing executable file (relative paths are refused);
      * whatever it resolves to, the realpath must lie OUTSIDE the project
        root — a repository (including .solo/gate-evidence/ and
        .solo/run-state/) can carry a fake `python`/`npm`/`gh`, so
        project-local resolution is refused, never silently accepted.

    Returns (resolved_absolute_realpath, None) or (None, reason). Callers
    EXECUTE and RECORD the resolved path, not the original token; the
    checker re-resolves and re-validates the recorded identity."""
    if not isinstance(tok, str) or not tok.strip():
        return None, "empty executable token"
    has_sep = ("/" in tok or "\\" in tok
               or (os.sep in tok) or (os.altsep and os.altsep in tok))
    if has_sep:
        if not os.path.isabs(tok):
            return None, ("relative-path executable %r is refused — use a "
                          "bare PATH name or an absolute path outside the "
                          "project" % tok)
        found = tok if os.path.isfile(tok) else shutil.which(tok)
        if found is None or not os.path.isfile(found):
            return None, ("%r does not resolve to an existing executable "
                          "file" % tok)
    else:
        found = shutil.which(tok)
        if found is None:
            return None, ("%r does not resolve on PATH — an unresolvable "
                          "executable cannot produce evidence" % tok)
    resolved = os.path.realpath(found)
    if _inside(resolved, root):
        return None, ("executable %r resolves INSIDE the project root "
                      "(%r) — executables carried by the repository under "
                      "test are untrusted, whatever their name" %
                      (tok, resolved))
    return resolved, None


def _is_py(tok, root):
    """Interpreter SHAPE check used inside validators: the token must be a
    python/python3 basename and either a bare PATH name or an absolute
    path outside the project. Full identity (PATH resolution, existence,
    project-local rejection) is enforced centrally by
    resolve_executable() in validate_command()."""
    if _norm_exe(tok) not in _PY:
        return False
    if "/" not in tok and "\\" not in tok and os.sep not in tok:
        return True
    if not os.path.isabs(tok):
        return False
    return not _inside(tok, root)


def _suite_root():
    return os.path.normpath(os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))


def _sd(skill, name):
    return os.path.join(_suite_root(), "plugins", "site-doctor", "skills",
                        skill, "scripts", name)


# The ONLY helper scripts the policy accepts, mapped to their canonical
# installed locations. A helper argument must BE the installed helper.
BUNDLED_HELPERS = {
    "gate_policy.py": os.path.abspath(__file__),
    "scan_secrets.py": _sd("security-review", "scan_secrets.py"),
    "check_headers.py": _sd("website-audit", "check_headers.py"),
    "extract_meta.py": _sd("seo-optimization", "extract_meta.py"),
    "scan_trackers.py": _sd("compliance-check", "scan_trackers.py"),
    "check_email_dns.py": _sd("email-deliverability", "check_email_dns.py"),
}


def canonical_helper(name):
    """Absolute path of the installed helper, or None when this gate copy
    cannot see it (split plugin installs) — callers FAIL CLOSED."""
    p = BUNDLED_HELPERS.get(name)
    return p if (p and os.path.isfile(p)) else None


def _helper_ok(tok, name, root):
    """CANONICAL HELPER IDENTITY. The token must resolve to the installed
    helper: exact canonical realpath, or a byte-identical (sha256) copy
    that lives OUTSIDE the project root. Helpers resolved inside the
    project — including .solo/gate-evidence/ — are refused regardless of
    content; a missing canonical reference refuses (fail closed)."""
    if os.path.basename(tok).lower() != name.lower():
        return False, "not %s" % name
    ref = canonical_helper(name)
    if ref is None:
        return False, ("cannot locate the installed reference copy of %s "
                       "to verify against — refusing (fail closed)" % name)
    cand = tok if os.path.isabs(tok) else os.path.join(root, tok)
    cand = os.path.realpath(cand)
    if _inside(cand, root):
        return False, ("%r resolves INSIDE the project root — helper "
                       "scripts carried by the repository under test are "
                       "untrusted, whatever their name or content" % tok)
    if cand == os.path.realpath(ref):
        return True, None
    try:
        if os.path.isfile(cand) and sha256_file(cand) == sha256_file(ref):
            return True, None
    except OSError:
        pass
    return False, ("%r is not the installed %s (canonical path %r; digest "
                   "mismatch)" % (tok, name, ref))


def _safe_rel_path(tok, root, must_exist=True):
    """A path argument must stay inside root (and exist when required)."""
    if not isinstance(tok, str) or not tok or tok.startswith("-"):
        return False
    if os.path.isabs(tok):
        cand = os.path.realpath(tok)
    else:
        cand = os.path.realpath(os.path.join(root, tok))
    root_abs = os.path.realpath(root)
    if not (cand == root_abs or cand.startswith(root_abs + os.sep)):
        return False
    return os.path.exists(cand) if must_exist else True


def _v_pytest(argv, root):
    """python(3) -m pytest [safe display/stop flags] [project paths]."""
    if _is_py(argv[0], root) and argv[1:3] == ["-m", "pytest"]:
        rest = argv[3:]
    elif os.path.basename(argv[0]) == "pytest":
        rest = argv[1:]
    else:
        return False, "not pytest"
    safe_flags = {"-q", "--quiet", "-v", "--verbose", "-x",
                  "--exitfirst", "--strict-markers", "--strict-config"}
    for t in rest:
        if t.startswith("-"):
            if t in safe_flags or re.match(r"^--maxfail=[1-9][0-9]*$", t):
                continue
            return False, ("pytest flag %r is not in the evidence-safe "
                           "allowlist (config/plugin/output overrides are "
                           "refused)" % t)
        if not _safe_rel_path(t, root):
            return False, "pytest target %r is not an existing path under the project root" % t
    return True, "pytest"


def _v_unittest(argv, root):
    if not (_is_py(argv[0], root) and argv[1:3] == ["-m", "unittest"]):
        return False, "not unittest"
    if argv[3:] == ["discover"]:
        return True, "unittest discover"
    return False, ("unittest evidence must be exactly: python -m unittest "
                   "discover (custom discovery/config arguments are refused)")


def _v_exact(*want):
    def v(argv, root):
        if argv == list(want):
            return True, " ".join(want)
        return False, "must be exactly: %s" % " ".join(want)
    return v


def _v_npm_test(argv, root):
    if argv == ["npm", "test"] or argv == ["npm", "t"]:
        return True, "npm test"
    return False, "must be exactly: npm test"


def _v_npx_runner(name, *fixed):
    def v(argv, root):
        head = ["npx", "--no-install", name] + list(fixed)
        if argv != head:
            return False, ("npx requires exactly: %s (the mandatory --no-install "
                           "prevents registry download; arbitrary runner "
                           "flags/config are not evidence-safe)"
                           % " ".join(head))
        return True, " ".join(head)
    return v


def _v_go_test(argv, root):
    if argv == ["go", "test", "./..."]:
        return True, "go test ./..."
    return False, ("must be exactly: go test ./... (flags such as -exec can "
                   "change what executable is run)")


def _v_bundled(script, arg_kind):
    """python(3) <the INSTALLED script — canonical path/digest verified>
    <one target> [flags]"""
    def v(argv, root):
        if not (len(argv) >= 2 and _is_py(argv[0], root)):
            return False, "not %s" % script
        ok, why = _helper_ok(argv[1], script, root)
        if not ok:
            return False, why
        permitted_flags = {"--json"} if script == "scan_secrets.py" else set()
        unknown_flags = [t for t in argv[2:] if t.startswith("-")
                         and t not in permitted_flags]
        if unknown_flags:
            return False, "%s flag(s) %r not permitted" % (script,
                                                            unknown_flags)
        targets = [t for t in argv[2:] if not t.startswith("-")]
        if len(targets) != 1:
            return False, "%s needs exactly one target" % script
        t = targets[0]
        if arg_kind == "url" and not _URL_RE.match(t):
            return False, "%s target must be an http(s) URL" % script
        if arg_kind == "path" and not _safe_rel_path(t, root):
            return False, "%s target %r must be an existing path under the project root" % (script, t)
        if arg_kind == "domain" and not _DOMAIN_RE.match(t):
            return False, "%s target must be a bare domain" % script
        return True, script
    return v


def _v_curl(flags_required):
    def v(argv, root):
        if os.path.basename(argv[0]) != "curl":
            return False, "not curl"
        letters, timeout, urls, bad = _parse_curl_argv(argv)
        if bad:
            return False, bad
        if len(urls) != 1:
            return False, "curl needs exactly one http(s) URL"
        ok, why = _safe_http_url_shape(urls[0])
        if not ok:
            return False, why
        missing = set(flags_required) - letters
        if missing:
            return False, "curl must fail on HTTP errors (-%s)" % flags_required
        extra = letters - set(flags_required)
        if extra:
            return False, "curl flag letter(s) %s not permitted" % sorted(extra)
        if timeout is None or not 1 <= timeout <= CURL_TIMEOUT_MAX:
            return False, "curl requires a timeout of 1..%d seconds" % CURL_TIMEOUT_MAX
        return True, "curl -" + flags_required
    return v


def _v_npm_audit(argv, root):
    if argv[:2] != ["npm", "audit"]:
        return False, "not npm audit"
    for t in argv[2:]:
        if not re.match(r"^--audit-level=(low|moderate|high|critical)$", t) \
                and t != "--omit=dev":
            return False, "npm audit flag %r not permitted" % t
    return True, "npm audit"


PIP_AUDIT_REQUIREMENT_TARGETS = {
    "requirements.txt": False,
    "requirements-dev.lock": True,
    "requirements.lock": True,
}


def _requirement_records(text):
    """Return non-comment logical requirement records (``\\`` joined)."""
    records = []
    current = ""
    for raw in text.splitlines():
        line = raw.strip()
        if not line or (not current and line.startswith("#")):
            continue
        current += (" " if current else "") + line
        if current.endswith("\\"):
            current = current[:-1].rstrip()
            continue
        records.append(current)
        current = ""
    if current:
        records.append(current)
    return records


def _validate_committed_requirement_target(target, root):
    """Validate the exact file the audit process will read.

    Gate dependency evidence is limited to three recognized root manifests.
    The target must be a regular, non-symlink file, tracked in HEAD, byte-equal
    to that committed blob, UTF-8, and non-empty.  Hash-lock targets must also
    contain only exact, SHA-256-covered requirement records.
    """
    hash_lock = PIP_AUDIT_REQUIREMENT_TARGETS.get(target)
    if hash_lock is None:
        return False, ("pip-audit target must be one recognized project "
                       "requirements file: %s" % ", ".join(sorted(
                           PIP_AUDIT_REQUIREMENT_TARGETS)))
    path = os.path.join(root, target)
    if (not _safe_rel_path(target, root) or os.path.islink(path)
            or not os.path.isfile(path)):
        return False, ("pip-audit target %r must be a regular project file"
                       % target)
    try:
        rc, committed = _git(root, "show", "HEAD:%s" % target)
    except (OSError, subprocess.SubprocessError) as exc:
        return False, ("cannot verify committed pip-audit target %r: %s" %
                       (target, exc))
    if rc != 0:
        return False, ("pip-audit target %r must be committed in HEAD" %
                       target)
    try:
        with open(path, "rb") as stream:
            current = stream.read(8 * 1024 * 1024 + 1)
    except OSError as exc:
        return False, "cannot read pip-audit target %r: %s" % (target, exc)
    if len(current) > 8 * 1024 * 1024 or len(committed) > 8 * 1024 * 1024:
        return False, "pip-audit target %r exceeds the 8 MiB policy cap" % target
    if current != committed:
        return False, ("pip-audit target %r differs from its committed HEAD "
                       "blob" % target)
    try:
        text = committed.decode("utf-8", "strict")
    except UnicodeDecodeError:
        return False, "pip-audit target %r must be UTF-8" % target
    records = _requirement_records(text)
    option_records = [record for record in records
                      if record.startswith("-")]
    if option_records:
        return False, ("pip-audit target %r may not contain requirement-file "
                       "options or recursive includes" % target)
    requirements = [record for record in records
                    if not record.startswith(("#", "-"))]
    if not requirements:
        return False, ("pip-audit target %r has no dependency requirements"
                       % target)
    requirement_head = re.compile(
        r"^[A-Za-z0-9][A-Za-z0-9._-]*(?:\[[A-Za-z0-9_,.-]+\])?"
        r"(?:\s*@\s*https://|\s*(?:===|==|~=|>=|<=|!=|>|<))?")
    if any(not requirement_head.match(record) for record in requirements):
        return False, ("pip-audit target %r contains an unsupported "
                       "requirement record" % target)
    if hash_lock:
        exact = re.compile(
            r"^[A-Za-z0-9][A-Za-z0-9._-]*(?:\[[A-Za-z0-9_,.-]+\])?"
            r"==[^\s;\\]+")
        hashed = re.compile(r"(?:^|\s)--hash=sha256:[0-9a-fA-F]{64}(?:\s|$)")
        if any(not exact.match(record) or not hashed.search(record)
               for record in requirements):
            return False, ("pip-audit hash-lock target %r must contain only "
                           "exact pins with SHA-256 hashes" % target)
    return True, hash_lock


def _v_pip_audit(argv, root):
    if os.path.basename(argv[0]) != "pip-audit":
        return False, "not pip-audit"
    target = None
    seen_flags = set()
    i = 1
    while i < len(argv):
        t = argv[i]
        if t == "-r":
            if target is not None:
                return False, "pip-audit accepts exactly one -r target"
            if i + 1 >= len(argv):
                return False, "pip-audit -r needs a requirements target"
            target = argv[i + 1]
            i += 2
            continue
        if t in ("--strict", "--progress-spinner=off", "--require-hashes"):
            if t in seen_flags:
                return False, "duplicate pip-audit flag %r" % t
            seen_flags.add(t)
            i += 1
            continue
        return False, "pip-audit flag %r not permitted" % t
    if target is None:
        return False, ("pip-audit evidence requires exactly one recognized, "
                       "committed project requirements/lock target via -r")
    ok, detail = _validate_committed_requirement_target(target, root)
    if not ok:
        return False, detail
    if detail and "--require-hashes" not in seen_flags:
        return False, ("pip-audit hash-lock target %r requires "
                       "--require-hashes" % target)
    return True, "pip-audit -r %s" % target


# JSON fields the gh-run binding needs in the captured output. The recorder
# and checker BOTH parse the output and require headSha == derived HEAD and
# conclusion == "success" — an arbitrary old run can never prove the
# current commit, and a red run can never prove deployment/monitoring.
GH_RUN_JSON_FIELDS = {"headSha", "conclusion", "status"}
GH_RUN_COMMAND_ID = "gh run view --exit-status --json"


def _v_gh_run_view(argv, root):
    """gh run view <NUMERIC-ID> --exit-status --json headSha,conclusion,
    status — an EXACT run, a STATUS-SENSITIVE flag, and machine-readable
    output the recorder/checker BIND to the current HEAD and a successful
    conclusion. `gh run list` proves only that runs exist; a run without
    the --json binding fields is not deployment or monitoring evidence."""
    if argv[:3] != ["gh", "run", "view"]:
        return False, "not gh run view"
    rest = argv[3:]
    ids = [t for t in rest if re.match(r"^\d+$", t)]
    flags = [t for t in rest if not re.match(r"^\d+$", t)]
    if len(ids) != 1:
        return False, ("gh run view needs exactly one NUMERIC run id — "
                       "an exact run, not a listing")
    if "--exit-status" not in flags:
        return False, ("gh run view must carry --exit-status so the "
                       "command FAILS when the run failed")

    def fields_ok(spec):
        fields = {x.strip() for x in spec.split(",") if x.strip()}
        return GH_RUN_JSON_FIELDS <= fields

    i, saw_json = 0, False
    while i < len(flags):
        f = flags[i]
        if f == "--exit-status":
            i += 1
            continue
        if f == "--json":
            if i + 1 >= len(flags) or not fields_ok(flags[i + 1]):
                return False, ("gh run view --json must include %s so the "
                               "output can be bound to HEAD and a "
                               "successful conclusion"
                               % ",".join(sorted(GH_RUN_JSON_FIELDS)))
            saw_json = True
            i += 2
            continue
        if f.startswith("--json="):
            if not fields_ok(f[len("--json="):]):
                return False, ("gh run view --json must include %s so the "
                               "output can be bound to HEAD and a "
                               "successful conclusion"
                               % ",".join(sorted(GH_RUN_JSON_FIELDS)))
            saw_json = True
            i += 1
            continue
        return False, "gh run view flag %r not permitted" % f
    if not saw_json:
        return False, ("gh run view must carry --json %s — without the "
                       "binding fields an old or foreign run could 'prove' "
                       "the current commit"
                       % ",".join(sorted(GH_RUN_JSON_FIELDS)))
    return True, GH_RUN_COMMAND_ID


def bind_gh_run_output(stdout_bytes, head, root=None):
    """POST-EXECUTION binding for gh-run evidence: the captured JSON must
    name the derived HEAD as headSha and a successful conclusion. Returns
    (ok, reason). `root` is accepted for signature parity with the
    endpoint binders (unused here)."""
    try:
        data = json.loads(stdout_bytes.decode("utf-8", "replace"))
    except Exception as e:
        return False, ("gh run view output is not parseable JSON (%s) — "
                       "cannot bind the run to HEAD" % e)
    if not isinstance(data, dict):
        return False, "gh run view JSON is not an object"
    got_sha = data.get("headSha")
    if got_sha != head:
        return False, ("gh run headSha %r != derived HEAD %s — a run from "
                       "another commit is not evidence for this one"
                       % (got_sha, head[:12]))
    if data.get("conclusion") != "success":
        return False, ("gh run conclusion %r is not 'success' — an "
                       "unsuccessful run proves nothing"
                       % (data.get("conclusion"),))
    return True, None


# command_id -> output-binding callable(stdout_bytes, head, root) applied by
# the recorder AFTER execution and re-applied by the checker from the hashed
# artifact bytes. (The endpoint binders are defined below and registered
# right after their definitions.)
OUTPUT_BINDINGS = {GH_RUN_COMMAND_ID: bind_gh_run_output}

_CAPTURE_STDERR_SEP = b"\n--- stderr ---\n"


def extract_captured_stdout(artifact_bytes):
    """Recover the raw captured stdout from a record_evidence.py artifact:
    strip the '# ...' header block (ends at the first blank line) and the
    optional stderr section. Returns bytes."""
    body = artifact_bytes
    sep = body.find(b"\n\n")
    if sep != -1 and body[:1] == b"#":
        body = body[sep + 2:]
    return body.split(_CAPTURE_STDERR_SEP, 1)[0]


# ---------------------------------------------------------------------------
# live-target binding: URL/domain evidence must aim at the project's own
# recorded stack, read from the COMMITTED .solo/stack.md at HEAD — evidence
# against someone else's (always-green) site proves nothing about this one.
# ---------------------------------------------------------------------------
_HOSTISH_RE = re.compile(
    r"(?:https?://)?("
    r"(?:[A-Za-z0-9][A-Za-z0-9.-]*\.[A-Za-z]{2,})|"
    r"localhost|"
    r"(?:\d{1,3}\.){3}\d{1,3}|"
    r"\[[0-9A-Fa-f:.]+\]"
    r")(?::\d+)?", re.I)


def committed_stack_hosts(root):
    """Set of lowercase hosts mentioned in the COMMITTED .solo/stack.md at
    HEAD (never the mutable working tree). None when HEAD has no readable
    .solo/stack.md — callers FAIL CLOSED."""
    rc, out = _git(root, "show", "HEAD:.solo/stack.md")
    if rc != 0:
        return None
    text = out.decode("utf-8", "replace")
    hosts = set()
    for m in _HOSTISH_RE.finditer(text):
        h = (m.group(1) or m.group(0)).strip("[]").lower()
        if h:
            hosts.add(h)
    return hosts


def _host_of_token(tok):
    m = re.match(r"^https?://([^/:?#]+)(?::\d+)?", tok, re.I)
    if m:
        return m.group(1).strip("[]").lower()
    if _DOMAIN_RE.match(tok):
        return tok.lower()
    return None


def check_live_target_binding(argv, root):
    """Every URL/domain token in an accepted argv must name a host recorded
    in the committed .solo/stack.md at HEAD (exact host, or a subdomain of
    a recorded host). Returns (ok, reason). Fails closed when stack.md is
    absent from HEAD."""
    # A requirements filename such as ``requirements-dev.lock`` is
    # syntactically domain-like.  It is nevertheless a validated local path,
    # not a live network target.  Exclude only the exact ``pip-audit -r``
    # operand; all actual domain-taking commands remain bound to stack.md.
    local_targets = set()
    if os.path.basename(argv[0]) == "pip-audit":
        local_targets.update(argv[index + 1]
                             for index, token in enumerate(argv[:-1])
                             if token == "-r")
    targets = [t for t in argv[1:] if t not in local_targets and (
        _URL_RE.match(t) or
        (_DOMAIN_RE.match(t) and not t.endswith(".py")))]
    if not targets:
        return True, None
    hosts = committed_stack_hosts(root)
    if hosts is None:
        return False, ("live-target binding: HEAD has no committed "
                       ".solo/stack.md — record the stack (with its URLs/"
                       "domains) and commit it before minting live "
                       "evidence (fail closed)")
    for t in targets:
        h = _host_of_token(t)
        if h is None:
            return False, "live-target binding: %r has no parseable host" % t
        if h in hosts or any(h.endswith("." + s) for s in hosts):
            continue
        return False, ("live-target binding: host %r is not recorded in "
                       "the committed .solo/stack.md at HEAD (%s) — "
                       "evidence must target the project's own stack"
                       % (h, ", ".join(sorted(hosts)[:5]) or "empty"))
    return True, None


# ---------------------------------------------------------------------------
# committed endpoint contracts (v1.0.17): deployment and monitoring curl
# evidence is bound to endpoints DECLARED in the committed .solo/stack.md at
# HEAD — `version-endpoint:` / `health-endpoint:` / optional `health-expect:`.
# A generic page fetch is never deployment or monitoring evidence.
# ---------------------------------------------------------------------------
_STACK_KV_RE = re.compile(
    r"(?im)^[\s>*+-]*`?(version[-_ ]endpoint|health[-_ ]endpoint|"
    r"health[-_ ]expect)`?\s*:\s*(\S(?:.*\S)?)\s*$")
CURL_TIMEOUT_MAX = 300


def committed_stack_endpoints(root):
    """Endpoint contract keys ('version-endpoint', 'health-endpoint',
    'health-expect') -> values, parsed from the COMMITTED .solo/stack.md at
    HEAD (never the mutable working tree). None when HEAD has no readable
    .solo/stack.md — callers FAIL CLOSED."""
    rc, out = _git(root, "show", "HEAD:.solo/stack.md")
    if rc != 0:
        return None
    text = out.decode("utf-8", "replace")
    found = {}
    for m in _STACK_KV_RE.finditer(text):
        key = m.group(1).lower().replace("_", "-").replace(" ", "-")
        found.setdefault(key, m.group(2).strip().strip("`").strip())
    return found


def _parse_curl_argv(argv):
    """Parse curl argv[1:] into (letter_flags, timeout_seconds, urls,
    error). Accepts single-dash letter groups (-sSf), `-m N`,
    `--max-time N` and `--max-time=N`. Anything else is an error."""
    letters, timeout, urls = set(), None, []
    i = 1
    while i < len(argv):
        t = argv[i]
        if t in ("-m", "--max-time"):
            if i + 1 >= len(argv) or not re.match(r"^\d+$", argv[i + 1]):
                return None, None, None, ("%s needs a whole-second count"
                                          % t)
            timeout = int(argv[i + 1])
            i += 2
            continue
        if t.startswith("--max-time="):
            v = t.split("=", 1)[1]
            if not re.match(r"^\d+$", v):
                return None, None, None, ("--max-time needs a whole-second "
                                          "count")
            timeout = int(v)
            i += 1
            continue
        if re.match(r"^-[A-Za-z]+$", t):
            if "m" in t[1:]:
                return None, None, None, ("give the curl timeout its own "
                                          "token (-m <seconds> or "
                                          "--max-time <seconds>), not a "
                                          "combined letter group")
            letters.update(t[1:])
            i += 1
            continue
        if t.startswith("-"):
            return None, None, None, "curl flag %r not permitted" % t
        urls.append(t)
        i += 1
    return letters, timeout, urls, None


def _v_curl_endpoint(kind):
    """curl -sSf with a MANDATORY bounded timeout, aimed at EXACTLY the
    committed endpoint from .solo/stack.md at HEAD:
      deployment -> `version-endpoint:` (response must name the derived
                     HEAD — see bind_version_endpoint_output)
      monitoring -> `health-endpoint:` (response must satisfy an explicit
                     health contract — see bind_health_endpoint_output)
    A curl at any other URL — including the site homepage — is refused."""
    key = "version-endpoint" if kind == "deployment" else "health-endpoint"
    cid = "curl %s" % key

    def v(argv, root):
        """curl -sSf [-i] (-m|--max-time) <1..300s> <the COMMITTED
        version-/health-endpoint from .solo/stack.md at HEAD> — bound
        endpoint evidence, never a generic page fetch"""
        if os.path.basename(argv[0]) != "curl":
            return False, "not curl"
        letters, timeout, urls, bad = _parse_curl_argv(argv)
        if bad:
            return False, bad
        missing = [ch for ch in "sSf" if ch not in letters]
        if missing:
            return False, ("curl must fail on HTTP errors and stay quiet "
                           "(-sSf) — missing -%s" % "".join(missing))
        extra = letters - set("sSfi")
        if extra:
            return False, ("curl flag letter(s) %s not permitted for %s "
                           "evidence (only -sSf plus optional -i)"
                           % (sorted(extra), kind))
        if timeout is None:
            return False, ("%s evidence must carry a bounded timeout "
                           "(-m <seconds> or --max-time <seconds>)" % kind)
        if not 1 <= timeout <= CURL_TIMEOUT_MAX:
            return False, ("curl timeout must be 1..%d seconds"
                           % CURL_TIMEOUT_MAX)
        if len(urls) != 1 or not _URL_RE.match(urls[0]):
            return False, "curl needs exactly one http(s) URL"
        safe, reason = _safe_http_url_shape(urls[0])
        if not safe:
            return False, reason
        eps = committed_stack_endpoints(root)
        if eps is None:
            return False, ("HEAD has no committed .solo/stack.md — declare "
                           "the %s there and commit it before minting %s "
                           "evidence (fail closed)" % (key, kind))
        want = eps.get(key)
        if not want:
            return False, ("the committed .solo/stack.md at HEAD declares "
                           "no '%s:' — a generic page fetch is not %s "
                           "evidence; declare the endpoint and commit it"
                           % (key, kind))
        if urls[0].rstrip("/") != want.rstrip("/"):
            return False, ("curl target %r is not the committed %s %r — "
                           "%s evidence must hit the declared endpoint "
                           "exactly" % (urls[0], key, want, kind))
        return True, cid
    return v


VERSION_ENDPOINT_COMMAND_ID = "curl version-endpoint"
HEALTH_ENDPOINT_COMMAND_ID = "curl health-endpoint"
_HEALTH_OK_VALUES = ("ok", "pass", "up", "healthy", "green", "alive")


def _response_bodies(stdout_bytes):
    """Candidate payloads from a captured curl response: the full text and
    (when -i included headers) the segment after each blank line."""
    text = stdout_bytes.decode("utf-8", "replace").strip()
    cands = [text]
    for sep in ("\r\n\r\n", "\n\n"):
        if sep in text:
            cands.append(text.split(sep)[-1].strip())
    return cands


def bind_version_endpoint_output(stdout_bytes, head, root=None):
    """POST-EXECUTION deployment binding: the captured version-endpoint
    response (headers and/or body) must contain the derived HEAD — the
    deployed result is bound to FINAL_SHA through a committed version
    endpoint / response contract. Returns (ok, reason)."""
    text = stdout_bytes.decode("utf-8", "replace")
    if head and head.lower() in text.lower():
        return True, None
    return False, ("version-endpoint response does not contain the derived "
                   "HEAD %s… — the deployed result is not bound to this "
                   "commit (deploy the freeze commit and expose its SHA "
                   "through the committed version endpoint)" % head[:12])


def bind_health_endpoint_output(stdout_bytes, head, root=None):
    """POST-EXECUTION monitoring binding: the captured health-endpoint
    response must satisfy an EXPLICIT health contract — JSON whose
    status/state/health value is in _HEALTH_OK_VALUES, or (when the
    committed stack.md declares `health-expect:`) a body containing that
    marker. A generic homepage response is refused. Returns (ok, reason)."""
    expect = None
    if root is not None:
        eps = committed_stack_endpoints(root)
        if eps:
            expect = eps.get("health-expect")
    for cand in _response_bodies(stdout_bytes):
        if expect and expect in cand:
            return True, None
        try:
            data = json.loads(cand)
        except ValueError:
            continue
        if isinstance(data, dict):
            for k in ("status", "state", "health"):
                val = data.get(k)
                if isinstance(val, str) \
                        and val.strip().lower() in _HEALTH_OK_VALUES:
                    return True, None
    return False, ("health-endpoint response is not an explicit health "
                   "contract (JSON status/state/health in %s, or the "
                   "committed 'health-expect:' marker) — a generic page "
                   "response is not monitoring evidence"
                   % (sorted(_HEALTH_OK_VALUES),))


OUTPUT_BINDINGS[VERSION_ENDPOINT_COMMAND_ID] = bind_version_endpoint_output
OUTPUT_BINDINGS[HEALTH_ENDPOINT_COMMAND_ID] = bind_health_endpoint_output


def _v_verify_artifact(category):
    def v(argv, root):
        me = os.path.basename(__file__)
        if not (len(argv) >= 4 and _is_py(argv[0], root)
                and argv[2] == "verify-artifact"
                and argv[3] == category):
            return False, ("must be: python3 <installed %s> verify-artifact "
                           "%s [--root DIR]" % (me, category))
        ok, why = _helper_ok(argv[1], me, root)
        if not ok:
            return False, why
        rest = argv[4:]
        if rest and rest != ["--root", "."] and not (
                len(rest) == 2 and rest[0] == "--root"
                and _safe_rel_path(rest[1], root)):
            return False, "only --root <dir> is permitted after the category"
        return True, "verify-artifact %s" % category
    return v


def _v_markdownlint(argv, root):
    if argv[:3] != ["npx", "--no-install", "markdownlint"] and \
            argv[:3] != ["npx", "--no-install", "markdownlint-cli2"]:
        return False, "not markdownlint"
    targets = argv[3:]
    if not targets:
        return False, "markdownlint needs explicit targets"
    for t in targets:
        if t.startswith("-"):
            return False, "markdownlint flags/config overrides are not permitted"
        base = t.split("*", 1)[0].rstrip("/")
        if "*" in t:
            if base and not _safe_rel_path(base, root):
                return False, "markdownlint glob %r escapes the project root" % t
        elif not _safe_rel_path(t, root):
            return False, "markdownlint target %r is not an existing path" % t
    return True, "markdownlint"


def _v_doctest(argv, root):
    if not (_is_py(argv[0], root) and argv[1:3] == ["-m", "doctest"]):
        return False, "not doctest"
    flags = [t for t in argv[3:] if t.startswith("-")]
    if any(t != "-v" for t in flags):
        return False, "doctest permits only optional -v plus file targets"
    targets = [t for t in argv[3:] if not t.startswith("-")]
    if not targets:
        return False, "doctest needs explicit file targets"
    for t in targets:
        if not _safe_rel_path(t, root):
            return False, "doctest target %r is not an existing path" % t
    return True, "doctest"


_TEST_RUNNERS = [_v_pytest, _v_unittest, _v_npm_test,
                 _v_npx_runner("vitest", "run"), _v_npx_runner("jest"),
                 _v_npx_runner("playwright", "test"), _v_go_test,
                 _v_exact("cargo", "test"), _v_exact("make", "test")]

# category -> list of full-argv validators. NO git commands anywhere:
# `git log`/`git ls-files` prove nothing about product quality, security,
# testing, deployment, monitoring, or documentation.
COMMAND_POLICY = {
    "product": [_v_verify_artifact("product")],
    "architecture": [_v_verify_artifact("architecture")],
    "design": [_v_verify_artifact("design")],
    "frontend": [_v_exact("npm", "run", "build"),
                 _v_exact("npm", "run", "lint"), _v_npm_test,
                 _v_npx_runner("vitest", "run"), _v_npx_runner("jest"),
                 _v_npx_runner("playwright", "test")],
    "backend": list(_TEST_RUNNERS),
    "database": [_v_exact("npx", "--no-install", "prisma", "migrate",
                          "status"),
                 _v_exact("npx", "--no-install", "supabase", "db", "lint"),
                 _v_exact("alembic", "check"),
                 _v_exact("alembic", "current")],
    "security": [_v_npm_audit, _v_pip_audit, _v_exact("cargo", "audit"),
                 _v_exact("govulncheck", "./..."),
                 _v_bundled("scan_secrets.py", "path"),
                 _v_bundled("check_headers.py", "url")],
    "testing": list(_TEST_RUNNERS),
    "performance": [_v_bundled("lighthouse_is_npx", "url"),  # placeholder, replaced below
                    ],
    "seo": [_v_bundled("extract_meta.py", "url"), _v_curl("sSfI")],
    "analytics": [_v_bundled("scan_trackers.py", "url")],
    # deployment/monitoring are NOT document-backed: release.md /
    # monitoring.md content alone (bytes/headings) is never their
    # evidence. Deployment = a CI run bound to HEAD + success, or the
    # COMMITTED version-endpoint answering with the derived HEAD (the
    # deployed result is bound to FINAL_SHA — a generic 200 proves
    # nothing). Monitoring = the COMMITTED health-endpoint answering an
    # explicit status/body/JSON health contract under a bounded timeout.
    # Email DNS authentication is deliverability configuration, not evidence
    # that uptime/error monitoring is live. A generic homepage curl and
    # `gh run view` were removed from monitoring in v1.0.17 (a green CI run
    # is not a monitor). `gh release view` was removed earlier: an arbitrary
    # old release cannot prove the current commit. When the health contract
    # is not executable, the category stays UNVERIFIED and the gate is
    # BLOCKED — by design.
    "deployment": [_v_gh_run_view, _v_curl_endpoint("deployment")],
    "monitoring": [_v_curl_endpoint("monitoring")],
    "documentation": [_v_markdownlint, _v_doctest,
                      _v_verify_artifact("documentation")],
}


def _v_npx_url(name):
    def v(argv, root):
        if argv[:3] != ["npx", "--no-install", name]:
            return False, "not npx %s" % name
        urls = argv[3:]
        if len(urls) != 1:
            return False, "%s needs exactly one http(s) URL" % name
        ok, why = _safe_http_url_shape(urls[0])
        if not ok:
            return False, why
        return True, "npx " + name
    return v


COMMAND_POLICY["performance"] = [_v_npx_url("lighthouse"),
                                  _v_npx_url("unlighthouse"),
                                  _v_exact("npx", "--no-install", "@lhci/cli",
                                           "autorun")]


def validate_command(category, argv, root):
    """Full-argv validation. Returns (ok, command_id_or_reason). A shape
    match is not enough: argv[0] must ALSO resolve through
    resolve_executable() (PATH-resolved, existing, outside the project),
    and any URL/domain target must pass the live-target binding against
    the committed .solo/stack.md at HEAD."""
    if category not in CATEGORIES:
        return False, "unknown category %r" % (category,)
    if not (isinstance(argv, list) and argv
            and all(isinstance(t, str) and t for t in argv)):
        return False, "command_argv must be a non-empty list of strings"
    for token in argv[1:]:
        if _URL_RE.match(token):
            safe, reason = _safe_http_url_shape(token)
            if not safe:
                return False, reason
    hit = _deny_hit(argv)
    if hit:
        return False, ("token %r turns the command into a no-op/info query "
                       "— that is not evidence" % hit)
    reasons = []
    for v in COMMAND_POLICY[category]:
        ok, why = v(argv, root)
        if ok:
            _exe, err = resolve_executable(argv[0], root)
            if err:
                return False, "executable identity: %s" % err
            bound, berr = check_live_target_binding(argv, root)
            if not bound:
                return False, berr
            return True, why
        reasons.append(why)
    # surface SPECIFIC rejections (identity/argument problems from a
    # validator that recognized the command shape) before generic
    # shape mismatches like "not pytest"
    specific = [r for r in reasons
                if not (r.startswith("not ") or r.startswith("must be"))]
    ordered = specific + [r for r in reasons if r not in specific]
    return False, ("argv %r matches no %r policy entry (closest rejections: "
                   "%s)" % (argv, category, "; ".join(ordered[:3])))


def describe_policy(category):
    return [v.__doc__ or getattr(v, "__name__", "rule")
            for v in COMMAND_POLICY.get(category, [])]


# ---------------------------------------------------------------------------
# git source identity — derived from git OBJECTS, never the working tree
# ---------------------------------------------------------------------------
def _git(root, *args):
    r = subprocess.run(["git"] + list(args), cwd=root,
                       capture_output=True, timeout=60)
    return r.returncode, r.stdout


def git_head(root):
    """Full 40-hex HEAD, or None outside a git checkout."""
    rc, out = _git(root, "rev-parse", "HEAD")
    if rc != 0:
        return None
    head = out.decode("ascii", "replace").strip()
    return head if SHA_RE.match(head) else None


def committed_project_profile(root):
    """Return the one authoritative project profile committed at HEAD.

    N/A evidence changes the denominator of the production gate, so its
    profile may not come from a caller-selected file or mutable working-tree
    bytes.  The canonical source is the regular git blob
    ``HEAD:.solo/project.md`` and it must contain exactly one standalone line
    of the form ``Project profile: <recognized-slug>``.  Returns
    ``(profile, None)`` or ``(None, reason)`` and always fails closed.
    """
    rc, listing = _git(root, "ls-tree", "-z", "HEAD", "--",
                       PROJECT_PROFILE_SOURCE)
    if rc != 0:
        return None, "could not inspect %s in the committed tree" % \
            PROJECT_PROFILE_SOURCE
    entries = [entry for entry in listing.split(b"\0") if entry]
    if len(entries) != 1:
        return None, ("%s must exist exactly once as a committed regular "
                      "file" % PROJECT_PROFILE_SOURCE)
    try:
        meta, raw_path = entries[0].split(b"\t", 1)
        mode, obj_type, _sha = meta.decode("ascii").split()
        rel = raw_path.decode("utf-8", "strict")
    except (UnicodeDecodeError, ValueError):
        return None, "malformed git metadata for %s" % PROJECT_PROFILE_SOURCE
    if (rel != PROJECT_PROFILE_SOURCE or obj_type != "blob"
            or mode not in {"100644", "100755"}):
        return None, ("%s must be a committed regular file (symlinks and "
                      "other git object types are refused)" %
                      PROJECT_PROFILE_SOURCE)
    rc, raw = _git(root, "show", "HEAD:%s" % PROJECT_PROFILE_SOURCE)
    if rc != 0:
        return None, "could not read HEAD:%s" % PROJECT_PROFILE_SOURCE
    try:
        text = raw.decode("utf-8", "strict")
    except UnicodeDecodeError:
        return None, "%s is not valid UTF-8" % PROJECT_PROFILE_SOURCE
    lines = text.splitlines()
    declaration = re.compile(r"^[ \t]*Project profile[ \t]*:")
    declarations = [line for line in lines if declaration.match(line)]
    field = re.compile(r"^Project profile:[ \t]*([^ \t\r\n]+)[ \t]*$")
    values = [match.group(1) for line in lines
              for match in [field.match(line)] if match]
    if len(declarations) != 1 or len(values) != 1:
        return None, ("%s must contain exactly one canonical line "
                      "`Project profile: <recognized-slug>` (found %d "
                      "profile declaration(s), %d canonical)" %
                      (PROJECT_PROFILE_SOURCE, len(declarations),
                       len(values)))
    profile = values[0]
    if profile not in RECOGNIZED_PROFILES:
        return None, ("%s records unrecognized project profile %r; choose "
                      "one of %s" % (PROJECT_PROFILE_SOURCE, profile,
                                     sorted(RECOGNIZED_PROFILES)))
    return profile, None


def _excluded(rel):
    rel = rel.replace(os.sep, "/")
    return any(rel == d or rel.startswith(d + "/")
               for d in UNTRACKED_RUNTIME_DIRS)


def committed_tree_digest(root):
    """SHA-256 over the COMMITTED tree at HEAD: sorted (path, blob-sha)
    pairs from `git ls-tree -r HEAD`, excluding ONLY the two generated
    runtime paths .solo/gate-evidence/** and .solo/run-state/**
    (UNTRACKED_RUNTIME_DIRS — pathological tracked copies are ignored so
    the digest stays stable across the supported and unsupported states).
    Derived entirely from git objects — mutating working-tree files cannot
    change it. Returns None outside a git checkout."""
    rc, out = _git(root, "ls-tree", "-r", "-z", "HEAD")
    if rc != 0:
        return None
    entries = []
    for rec in out.split(b"\0"):
        if not rec:
            continue
        try:
            meta, path = rec.split(b"\t", 1)
            _mode, _type, sha = meta.decode("ascii").split()
        except ValueError:
            continue
        rel = path.decode("utf-8", "replace")
        if _excluded(rel):
            continue
        entries.append((rel, sha))
    h = hashlib.sha256()
    for rel, sha in sorted(entries):
        h.update(rel.encode("utf-8"))
        h.update(b"\0")
        h.update(sha.encode("ascii"))
        h.update(b"\n")
    return h.hexdigest()


def _name_status_entries(out_bytes):
    """Parse `git diff --name-status -z` output into (status, [paths]).
    R/C entries carry BOTH the source and destination path."""
    fields = [f.decode("utf-8", "replace")
              for f in out_bytes.split(b"\0") if f]
    entries, i = [], 0
    while i < len(fields):
        status = fields[i]
        i += 1
        if not status or not status[0].isalpha():
            continue
        if status[0] in ("R", "C"):
            if i + 1 >= len(fields):
                return None          # truncated output: fail closed
            entries.append((status, [fields[i], fields[i + 1]]))
            i += 2
        else:
            if i >= len(fields):
                return None
            entries.append((status, [fields[i]]))
            i += 1
    return entries


def repo_state(root):
    """FAIL-CLOSED repository cleanliness. Returns a dict or None — and
    None ALWAYS means 'could not verify', never 'clean'. Three independent
    checks, each from its own plumbing command:

      staged     index vs HEAD      `git diff --cached --name-status -z -M -C HEAD`
                 EVERY staged entry is dirt — additions, modifications,
                 deletions, renames, and copies, with BOTH the source and
                 destination of a rename/copy evaluated. There is NO
                 evidence-directory exemption on the index side: staging
                 anything (including a rename INTO .solo/gate-evidence/)
                 means HEAD no longer describes the next commit.
      unstaged   working tree vs index  `git diff --name-status -z -M`
                 dirt when any touched path lies outside the untracked
                 runtime dirs (.solo/gate-evidence/, .solo/run-state/).
      untracked  `git ls-files --others --exclude-standard -z`
                 dirt when outside the runtime dirs.

    IGNORED-FILE POLICY (explicit, by design): paths matched by the
    project's gitignore rules are EXEMPT from the untracked check. The
    .gitignore files are themselves tracked, reviewed content — ignoring
    production.env is a deliberate, visible decision recorded in the
    commit under review, not an invisible hole. Consequence: evidence
    claims cover the committed tree plus non-ignored files only; audit
    your .gitignore as part of the security category.
    """
    rc, head_out = _git(root, "rev-parse", "HEAD")
    if rc != 0:
        return None
    rc, staged_out = _git(root, "diff", "--cached", "--name-status", "-z",
                          "-M", "-C", "HEAD")
    if rc != 0:
        return None
    staged_entries = _name_status_entries(staged_out)
    if staged_entries is None:
        return None
    rc, unstaged_out = _git(root, "diff", "--name-status", "-z", "-M")
    if rc != 0:
        return None
    unstaged_entries = _name_status_entries(unstaged_out)
    if unstaged_entries is None:
        return None
    rc, untracked_out = _git(root, "ls-files", "--others",
                             "--exclude-standard", "-z")
    if rc != 0:
        return None
    dirty = []
    for status, paths in staged_entries:
        # index-side dirt is unconditional: both rename/copy sides shown
        dirty.append("staged:%s %s" % (status, " -> ".join(paths)))
    for status, paths in unstaged_entries:
        offending = [p for p in paths if not _excluded(p)]
        if offending:
            dirty.append("unstaged:%s %s" % (status, " -> ".join(paths)))
    for f in untracked_out.split(b"\0"):
        if not f:
            continue
        rel = f.decode("utf-8", "replace")
        if not _excluded(rel):
            dirty.append("untracked:?? %s" % rel)
    return {"head": head_out.decode("ascii", "replace").strip(),
            "dirty": dirty}


def dirty_paths_outside_evidence(root):
    """Back-compat wrapper over repo_state(). None = git failure (callers
    must FAIL, never treat as clean); else the dirt list."""
    state = repo_state(root)
    return None if state is None else state["dirty"]


def evidence_tracked_in_head(root):
    """True when .solo/gate-evidence OR .solo/run-state files are COMMITTED
    — unsupported states (both runtime dirs stay untracked/gitignored).
    Returns None on git failure (callers fail closed)."""
    rc, out = _git(root, "ls-tree", "-r", "--name-only", "-z", "HEAD",
                   "--", *UNTRACKED_RUNTIME_DIRS)
    if rc != 0:
        return None
    return any(p for p in out.split(b"\0") if p)


def tracked_in_head(root, rel):
    """True when rel is tracked in HEAD; None on git failure (fail closed)."""
    rc, out = _git(root, "ls-tree", "--name-only", "-z", "HEAD", "--", rel)
    if rc != 0:
        return None
    return any(p for p in out.split(b"\0") if p)


def safe_evidence_path(root, candidate, kind):
    """Resolve an output path and REQUIRE it inside
    <root>/.solo/gate-evidence/ (symlink-aware). Rejects absolute outside
    paths, '..' escapes, symlink/junction escapes (the deepest existing
    ancestor is realpath-resolved), and tracked source files. Returns
    (absolute_path, None) or (None, reason)."""
    root_real = os.path.realpath(root)
    ev_real = os.path.join(root_real, *EVIDENCE_DIR.split("/"))
    raw = candidate if os.path.isabs(candidate) \
        else os.path.join(root_real, candidate)
    raw = os.path.normpath(raw)
    # resolve through the deepest EXISTING ancestor so a symlinked parent
    # cannot smuggle the write outside the evidence directory
    probe, tail = raw, []
    while probe and not os.path.lexists(probe):
        probe, last = os.path.split(probe)
        if not last:
            break
        tail.append(last)
    resolved = os.path.join(os.path.realpath(probe), *reversed(tail)) \
        if probe else raw
    resolved = os.path.normpath(resolved)
    is_junction = getattr(os.path, "isjunction", lambda _p: False)
    if os.path.lexists(raw) and (os.path.islink(raw) or is_junction(raw)):
        resolved = os.path.realpath(raw)
    if not (resolved == ev_real or resolved.startswith(ev_real + os.sep)):
        return None, ("%s %r resolves to %r — outside "
                      "<root>/%s/ (absolute outside paths, '..', and "
                      "symlink escapes are refused)"
                      % (kind, candidate, resolved, EVIDENCE_DIR))
    rel = os.path.relpath(resolved, root_real).replace(os.sep, "/")
    tracked = tracked_in_head(root, rel)
    if tracked is None:
        return None, "%s %r: git tracking check failed (fail closed)" % (
            kind, candidate)
    if tracked:
        return None, ("%s %r is TRACKED in HEAD — evidence outputs may "
                      "never overwrite tracked files" % (kind, candidate))
    return resolved, None


def safe_run_state_path(root, candidate, kind):
    """Resolve a path inside <root>/.solo/run-state, rejecting traversal,
    tracked-file overwrite, dangling/ordinary symlinks, and Windows junction
    escapes.  This mirrors ``safe_evidence_path`` for the second generated
    runtime directory.
    """
    root_real = os.path.realpath(root)
    state_real = os.path.join(root_real, *RUN_STATE_DIR.split("/"))
    raw = candidate if os.path.isabs(candidate) \
        else os.path.join(root_real, candidate)
    raw = os.path.normpath(raw)
    is_junction = getattr(os.path, "isjunction", lambda _p: False)
    if os.path.lexists(raw) and (os.path.islink(raw) or is_junction(raw)):
        return None, ("%s %r is a symlink/junction; run-state paths must "
                      "name their final object directly" % (kind, candidate))
    probe, tail = raw, []
    while probe and not os.path.lexists(probe):
        probe, last = os.path.split(probe)
        if not last:
            break
        tail.append(last)
    resolved = os.path.join(os.path.realpath(probe), *reversed(tail)) \
        if probe else raw
    resolved = os.path.normpath(resolved)
    if not (resolved == state_real or
            resolved.startswith(state_real + os.sep)):
        return None, ("%s %r resolves outside <root>/%s; traversal, absolute "
                      "outside paths, symlinks and junctions are refused"
                      % (kind, candidate, RUN_STATE_DIR))
    rel = os.path.relpath(resolved, root_real).replace(os.sep, "/")
    tracked = tracked_in_head(root, rel)
    if tracked is None:
        return None, "%s %r: git tracking check failed (fail closed)" % (
            kind, candidate)
    if tracked:
        return None, ("%s %r is TRACKED in HEAD; run-state outputs never "
                      "overwrite tracked files" % (kind, candidate))
    return resolved, None


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# built-in strict JSON-Schema evaluation (draft-07 subset + local $ref)
# ---------------------------------------------------------------------------
def schema_path():
    return os.path.normpath(os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "skills",
        "production-readiness-reviewer", "schema",
        "gate-evidence-v1.schema.json"))


def load_schema(path=None):
    with open(path or schema_path(), encoding="utf-8") as f:
        return json.load(f)


def _resolve_ref(ref, doc):
    if not ref.startswith("#/"):
        raise ValueError("only local $ref supported: %r" % ref)
    node = doc
    for part in ref[2:].split("/"):
        node = node[part]
    return node


def _type_ok(value, t):
    if t == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if t == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if t == "boolean":
        return isinstance(value, bool)
    if t == "object":
        return isinstance(value, dict)
    if t == "array":
        return isinstance(value, list)
    if t == "string":
        return isinstance(value, str)
    if t == "null":
        return value is None
    return True


def _eval(value, schema, doc, path, errors):
    if not isinstance(schema, dict):
        return
    if "$ref" in schema:
        _eval(value, _resolve_ref(schema["$ref"], doc), doc, path, errors)
        return
    where = path or "$"
    if "const" in schema and value != schema["const"]:
        errors.append("%s: must be %r" % (where, schema["const"]))
        return
    if "enum" in schema and value not in schema["enum"]:
        errors.append("%s: %r not in enum" % (where, value))
        return
    if "oneOf" in schema:
        matches, briefs = 0, []
        for i, sub in enumerate(schema["oneOf"]):
            e = []
            _eval(value, sub, doc, path, e)
            if not e:
                matches += 1
            else:
                briefs.append("[%d] %s" % (i, e[0]))
        if matches != 1:
            errors.append("%s: matches %d oneOf branches (need 1): %s"
                          % (where, matches, "; ".join(briefs[:2])))
        return
    t = schema.get("type")
    if t is not None:
        types = t if isinstance(t, list) else [t]
        if not any(_type_ok(value, x) for x in types):
            errors.append("%s: expected %s, got %s"
                          % (where, "/".join(types), type(value).__name__))
            return
    if isinstance(value, str):
        if "minLength" in schema and len(value) < schema["minLength"]:
            errors.append("%s: shorter than minLength %d"
                          % (where, schema["minLength"]))
        if "pattern" in schema and not re.search(schema["pattern"], value):
            errors.append("%s: %r fails pattern" % (where, value[:60]))
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append("%s: below minimum %s" % (where, schema["minimum"]))
    if isinstance(value, list):
        if "minItems" in schema and len(value) < schema["minItems"]:
            errors.append("%s: fewer than minItems %d"
                          % (where, schema["minItems"]))
        if "items" in schema:
            for i, item in enumerate(value):
                _eval(item, schema["items"], doc,
                      "%s[%d]" % (where, i), errors)
    if isinstance(value, dict):
        for k in schema.get("required", ()):
            if k not in value:
                errors.append("%s: missing required %r" % (where, k))
        props = schema.get("properties", {})
        for k, v in value.items():
            if k in props:
                _eval(v, props[k], doc, "%s.%s" % (where, k), errors)
            elif isinstance(schema.get("additionalProperties"), dict):
                _eval(v, schema["additionalProperties"], doc,
                      "%s.%s" % (where, k), errors)
            elif schema.get("additionalProperties") is False:
                errors.append("%s: unknown property %r" % (where, k))


def schema_validate(record, schema=None):
    """Strict validation against the bundled schema using the BUILT-IN
    evaluator (always runs — jsonschema is never required). Returns a list
    of error strings."""
    doc = schema if schema is not None else load_schema()
    errors = []
    try:
        _eval(record, doc, doc, "$", errors)
    except Exception as e:   # never crash on validator internals
        errors.append("schema evaluation failed: %s" % e)
    return errors


# ---------------------------------------------------------------------------
# verify-artifact: the executable evidence command for document categories
# ---------------------------------------------------------------------------
# Document-backed categories ONLY. deployment and monitoring were REMOVED
# in v1.0.16: a release.md/monitoring.md with enough bytes and headings is
# a plan, not a deployment or a monitor — those categories require live,
# bound evidence (see COMMAND_POLICY) and stay UNVERIFIED without it.
#
# v1.0.17 — CATEGORY-SPECIFIC requirements replace the old generic
# "200 bytes and two headings" check. Every document category now requires:
#   * its REQUIRED HEADINGS (each a regex over markdown heading lines);
#   * SUBSTANTIVE CONTENT (minimum bytes, words, and distinct vocabulary —
#     "content content content …" filler fails the vocabulary floor);
#   * NO PLACEHOLDER/FILLER markers (TBD/TODO/lorem ipsum/... anywhere);
#   * its REQUIRED IDENTIFIER/DECISION FIELDS where applicable (acceptance
#     criteria/story IDs for product, recorded decisions for architecture,
#     concrete breakpoints for design, runnable examples for docs).
PLACEHOLDER_RE = re.compile(
    r"(?i)\b(tbd|todo|fixme|xxx+|lorem ipsum|placeholder|"
    r"fill (?:this |me |it )?in|to be (?:written|determined|defined|"
    r"documented|decided)|coming soon|write me|wip)\b")
_HEADING_RE = re.compile(r"(?m)^#{1,6}[ \t].*$")
_WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9'-]*")
_LIST_ITEM_RE = re.compile(r"(?m)^\s*(?:[-*+]|\d+\.)\s+\S")

ARTIFACT_REQUIREMENTS = {
    "product": {
        "path": ".solo/prd.md",
        "min_bytes": 500, "min_words": 80, "min_unique_words": 30,
        "required_headings": [
            (r"(?i)(problem|goal|overview|summary|why)",
             "a problem/goals heading"),
            (r"(?i)(scope|mvp|feature)", "a scope/MVP heading"),
            (r"(?i)(acceptance|user stor|criteria|requirement)",
             "an acceptance-criteria / user-stories heading"),
            (r"(?i)non-?goals?", "a non-goals heading"),
        ],
        "required_fields": [
            (lambda text: len(_LIST_ITEM_RE.findall(text)) >= 3,
             "at least three list items (stories / acceptance criteria / "
             "non-goals as concrete bullets)"),
        ],
    },
    "architecture": {
        "path": ".solo/architecture.md",
        "min_bytes": 400, "min_words": 60, "min_unique_words": 30,
        "required_headings": [
            (r"(?i)(component|module|structure|overview|diagram|system)",
             "a components/structure heading"),
            (r"(?i)(data|storage|database|api|contract)",
             "a data/API-contract heading"),
            (r"(?i)(decision|trade-?off|rationale|adr)",
             "a decisions/tradeoffs heading"),
        ],
        "required_fields": [
            (lambda text: bool(re.search(
                r"(?im)(\b(?:ADR|DEC|D)-\d+\b|^\s*(?:[-*+]\s*)?"
                r"(?:\*\*)?decision(?:\*\*)?\s*[:—-])", text)),
             "at least one recorded decision (an ADR-n/DEC-n identifier "
             "or an explicit 'Decision:' field)"),
        ],
    },
    "design": {
        "path": ".solo/design.md",
        "min_bytes": 400, "min_words": 60, "min_unique_words": 30,
        "required_headings": [
            (r"(?i)(flow|journey|screen|page)", "a user-flows heading"),
            (r"(?i)(mobile|responsive|breakpoint)",
             "a mobile/responsive heading"),
            (r"(?i)(state|empty|loading|error|component)",
             "a states/components heading"),
        ],
        "required_fields": [
            (lambda text: bool(re.search(
                r"\b(320|360|375|390|414|768|1024|1280|1440)\b", text)),
             "at least one concrete breakpoint width (e.g. 320/375/768)"),
        ],
    },
    "documentation": {
        "path": "README.md",
        "min_bytes": 400, "min_words": 60, "min_unique_words": 30,
        "required_headings": [
            (r"(?i)(install|set ?up|getting started|quick ?start)",
             "an install/setup heading"),
            (r"(?i)(usage|api|command|example|how)", "a usage heading"),
        ],
        "required_fields": [
            (lambda text: bool(re.search(r"(?m)^(```|~~~|    \S)", text)),
             "a runnable example (fenced or indented code block)"),
        ],
    },
}


def verify_artifact(category, root):
    """Exit-code-real CATEGORY-SPECIFIC content check: the category's
    artifact must exist, carry the category's required headings, be
    substantive (bytes/words/vocabulary floors), contain no
    placeholder/filler markers, and carry the category's required
    identifier/decision fields. Prints findings; returns 0/1 (2 = the
    category is not document-backed)."""
    spec = ARTIFACT_REQUIREMENTS.get(category)
    if not spec:
        print("verify-artifact: category %r has no document requirement — "
              "use its tool-based evidence commands instead" % category)
        return 2
    rel = spec["path"]
    full = os.path.join(root, rel)
    if not os.path.isfile(full):
        print("[FAIL] %s: missing" % rel)
        return 1
    with open(full, "rb") as f:
        data = f.read()
    text = data.decode("utf-8", "replace")
    failures = []
    # -- substantive content ------------------------------------------------
    words = _WORD_RE.findall(text)
    unique = {w.lower() for w in words}
    if len(data) < spec["min_bytes"]:
        failures.append("only %d bytes (< %d) — not substantive"
                        % (len(data), spec["min_bytes"]))
    if len(words) < spec["min_words"]:
        failures.append("only %d words (< %d) — not substantive"
                        % (len(words), spec["min_words"]))
    if len(unique) < spec["min_unique_words"]:
        failures.append("only %d distinct words (< %d) — repeated filler "
                        "is not substantive content"
                        % (len(unique), spec["min_unique_words"]))
    # -- placeholder/filler rejection ----------------------------------------
    hits = sorted({m.group(0).lower()
                   for m in PLACEHOLDER_RE.finditer(text)})
    if hits:
        failures.append("placeholder/filler markers present: %s — finish "
                        "the document before minting evidence" % hits)
    # -- required headings ----------------------------------------------------
    headings = _HEADING_RE.findall(text)
    for pattern, label in spec["required_headings"]:
        if not any(re.search(pattern, h) for h in headings):
            failures.append("missing required heading: %s" % label)
    # -- required identifier / decision fields --------------------------------
    for predicate, label in spec.get("required_fields", ()):
        if not predicate(text):
            failures.append("missing required field: %s" % label)
    if failures:
        for msg in failures:
            print("[FAIL] %s: %s" % (rel, msg))
        return 1
    print("[PASS] %s: %d bytes, %d words (%d distinct), %d headings — all "
          "category-specific requirements met"
          % (rel, len(data), len(words), len(unique), len(headings)))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="gate_policy.py")
    sub = ap.add_subparsers(dest="mode")
    va = sub.add_parser("verify-artifact",
                        help="executable content check for document-backed "
                             "categories")
    va.add_argument("category", choices=sorted(CATEGORIES))
    va.add_argument("--root", default=".")
    args = ap.parse_args(argv)
    if args.mode == "verify-artifact":
        return verify_artifact(args.category, os.path.abspath(args.root))
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
