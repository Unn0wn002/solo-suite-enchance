#!/usr/bin/env python3
r"""check_evidence.py — validate solo-suite gate-evidence records and REJECT
stale, incomplete, duplicated, or unverifiable evidence. Stdlib only.

TRUST MODEL — SELF-ATTESTED LOCAL EVIDENCE. Records are unsigned JSON. The
supported workflow creates them through record_evidence.py, but the copyable
``recorder`` label cannot prove which process wrote a conforming record. This
checker validates content against the current checkout; it does NOT verify
cryptographic origin or attestations. A trusted CI identity/signature is the
upgrade path.

THE CATEGORY-EVIDENCE CONTRACT (exit 0 only when ALL hold):
  * the checker DERIVES HEAD ITSELF (`git rev-parse HEAD` in --root).
    --commit is optional and, when given, must EXACTLY equal derived HEAD
    (usage error otherwise) — caller-provided commits are never trusted.
  * the working tree is CLEAN outside the generated runtime directories
    (no modified, deleted, or untracked paths; ONLY .solo/gate-evidence/
    and .solo/run-state/ are excluded) and neither .solo/gate-evidence
    nor .solo/run-state is tracked in HEAD — the single supported
    workflow keeps both generated runtime directories untracked.
  * every record STRICTLY validates against the bundled
    gate-evidence-v1.schema.json using the built-in evaluator (the
    external jsonschema package is never required)
  * every one of the 14 categories has EXACTLY ONE accepted record —
    either a verified evidence record or a machine-readable N/A record;
    duplicates are rejected (all of them)
  * verified records: status=verified, recorder, command_argv RE-VALIDATED
    against the shared per-category command policy (gate_policy.py — the
    same module the recorder uses), resolved_executable RE-DERIVED via the
    canonical PATH resolver and required to match (project-local or
    unresolvable executables are rejected), commit EXACTLY equals derived
    HEAD, tree_digest equals the recomputed COMMITTED-tree digest at HEAD,
    exit_code 0, non-empty reviewer, fresh timestamps, artifact inside
    --root with a matching recomputed SHA-256, and — for bound command
    ids like gh run view — the captured output re-parsed and re-bound to
    the derived HEAD and a successful conclusion
  * N/A records: the supported workflow uses the canonical
    record_evidence.py --not-applicable operation; the schema requires its
    recorder format label, but that copyable value is not proof of origin;
    matrix-permitted category/profile (the seven MANDATORY categories —
    product, architecture, security, testing, deployment, monitoring,
    documentation — are never N/A), recognized profile matching both the
    required --profile cross-check and the canonical field in committed
    HEAD:.solo/project.md, substantive reason (>= 20 chars, >= 4 words),
    structured applicability evidence, non-empty reviewer, exact HEAD

Usage:
    python3 check_evidence.py <evidence-dir-or-file...>
        --root <dir> --environment <env> --project <name>
        --profile <profile> [--commit <sha-that-must-equal-HEAD>]
        [--max-age-days 7] [--json]

Exit 0 = the 14-category record set is complete and verified to the limits of
each captured command. It is necessary, NOT sufficient, for a launch verdict:
the reviewer-required controls exposed in gate_policy.py still need separate
cited evidence. Exit 1 = any rejection, missing category, or unverifiable
working state; 2 = usage error.
"""
import argparse
import datetime
import glob
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(_HERE, "..", "..", "..", "lib")))
try:
    import gate_policy as gp
except ImportError:
    sys.exit("gate_policy.py not found — run from an intact gate plugin "
             "(plugins/gate/lib/gate_policy.py ships beside this skill)")

# re-exported so tests and siblings have one import point
CATEGORIES = gp.CATEGORIES
ORDERED_CATEGORIES = gp.CATEGORY_ORDER
REVIEWER_REQUIRED_CONTROLS = gp.REVIEWER_REQUIRED_CONTROLS
RECOGNIZED_PROFILES = gp.RECOGNIZED_PROFILES
MANDATORY = gp.MANDATORY
NA_ALLOWED = gp.NA_ALLOWED
PROFILE_NA_ALLOWED = gp.PROFILE_NA_ALLOWED
evaluate_production_gate = gp.evaluate_production_gate
SHA_RE = gp.SHA_RE
DIGEST_RE = gp.DIGEST_RE

MIN_REASON_CHARS = 20
MIN_REASON_WORDS = 4


def parse_ts(value):
    if not isinstance(value, str):
        return None
    v = value.strip().replace("Z", "+00:00")
    try:
        dt = datetime.datetime.fromisoformat(v)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    return dt


def check_common(rec, head, environment, now, max_age_days, project):
    """Identity + freshness checks shared by evidence and N/A records.
    `head` is the checker-DERIVED HEAD; records must match it EXACTLY."""
    reasons = []
    if project is not None and rec.get("project") != project:
        reasons.append("WRONG PROJECT: record project %r != %r"
                       % (rec.get("project"), project))
    c = rec.get("commit")
    if not (isinstance(c, str) and SHA_RE.match(c)):
        reasons.append("commit is not a full 40-hex git SHA")
    elif c != head:
        reasons.append("STALE: record commit %s != derived HEAD %s "
                       "(the checker derives HEAD itself; caller-provided "
                       "commits are never trusted)" % (c[:12], head[:12]))
    if rec.get("environment") != environment:
        reasons.append("STALE: evidence environment %r != target %r"
                       % (rec.get("environment"), environment))
    ts = parse_ts(rec.get("timestamp"))
    exp = parse_ts(rec.get("expires"))
    if ts is None:
        reasons.append("timestamp is not ISO-8601")
    if exp is None:
        reasons.append("expires is not ISO-8601")
    if exp is not None and exp <= now:
        reasons.append("STALE: evidence expired at %s" % rec.get("expires"))
    if ts is not None:
        age = now - ts
        max_age = datetime.timedelta(days=max_age_days)
        if age > max_age:
            reasons.append("STALE: evidence is more than %d days old "
                           "(exact %d-day freshness limit)"
                           % (max_age_days, max_age_days))
        if age.total_seconds() < 0:
            reasons.append("timestamp is in the future")
    rv = rec.get("reviewer")
    if not (isinstance(rv, str) and rv.strip()):
        reasons.append("reviewer must be a non-empty string (got %r)" % (rv,))
    return reasons


def check_na_applicability(rec, profile):
    reasons = []
    cat = rec.get("category")
    prof = rec.get("profile")
    if cat not in CATEGORIES:
        reasons.append("unknown category %r" % (cat,))
        return reasons
    if cat in MANDATORY:
        reasons.append("category %r is MANDATORY and may never be N/A "
                       "(mandatory: %s)" % (cat, sorted(MANDATORY)))
    if prof not in RECOGNIZED_PROFILES:
        reasons.append("N/A profile %r is not a recognized project profile "
                       "%s" % (prof, sorted(RECOGNIZED_PROFILES)))
    else:
        if profile is None:
            reasons.append("N/A profile cannot be accepted without the "
                           "committed project profile binding")
        elif prof != profile:
            reasons.append("N/A profile %r != the project's profile %r"
                           % (prof, profile))
        if cat not in MANDATORY and prof not in NA_ALLOWED.get(cat, ()):
            reasons.append(
                "the applicability matrix does not permit N/A for category "
                "%r under profile %r (permitted profiles: %s)"
                % (cat, prof, sorted(NA_ALLOWED.get(cat, ())) or "none"))
    reason = rec.get("reason")
    if not (isinstance(reason, str)
            and len(reason.strip()) >= MIN_REASON_CHARS
            and len(reason.split()) >= MIN_REASON_WORDS):
        reasons.append("N/A reason must be substantive (>= %d chars and "
                       ">= %d words); got %r"
                       % (MIN_REASON_CHARS, MIN_REASON_WORDS, reason))
    app = rec.get("applicability")
    if not isinstance(app, dict):
        reasons.append("N/A record must carry a structured 'applicability' "
                       "object (matrix, profile_source, checked)")
        return reasons
    want_matrix = "%s:%s" % (cat, prof)
    if app.get("matrix") != want_matrix:
        reasons.append("applicability.matrix must be %r (got %r)"
                       % (want_matrix, app.get("matrix")))
    ps = app.get("profile_source")
    if ps != gp.PROJECT_PROFILE_SOURCE:
        reasons.append("applicability.profile_source must be the canonical "
                       "committed source %r (got %r)" %
                       (gp.PROJECT_PROFILE_SOURCE, ps))
    checked = app.get("checked")
    if not (isinstance(checked, list) and checked
            and all(isinstance(x, str) and x.strip() for x in checked)):
        reasons.append("applicability.checked must be a non-empty list of "
                       "non-empty strings describing what was inspected")
    return reasons


def check_record(rec, head, environment, now, max_age_days,
                 project=None, root=None, profile=None,
                 expected_tree=None, schema=None):
    """Return list of rejection reasons for ONE record (empty = accepted).
    STRICT bundled-schema validation runs FIRST via the built-in evaluator;
    semantic checks (exact HEAD, tree digest, command-policy revalidation,
    artifact recomputation) follow."""
    if not isinstance(rec, dict):
        return ["record is not an object"]
    schema_errs = gp.schema_validate(rec, schema)
    if schema_errs:
        return ["SCHEMA: %s" % e for e in schema_errs[:12]]

    if rec.get("status") == "not-applicable":
        reasons = check_common(rec, head, environment, now, max_age_days,
                               project)
        reasons += check_na_applicability(rec, profile)
        return reasons

    # verified branch (schema guarantees shape, recorder const, argv list)
    reasons = check_common(rec, head, environment, now, max_age_days,
                           project)
    if rec["exit_code"] != 0:
        reasons.append("evidence command FAILED (exit_code %s)"
                       % rec["exit_code"])
    # ---- command policy REVALIDATION (shared module with the recorder) ----
    if root is not None:
        ok, why = gp.validate_command(rec["category"], rec["command_argv"],
                                      root)
        if not ok:
            reasons.append("COMMAND POLICY: %s" % why)
        else:
            if rec.get("command_id") != why:
                reasons.append("COMMAND ID MISMATCH: record says %r but the "
                               "policy derives %r from command_argv — the "
                               "id is recomputed, never trusted"
                               % (rec.get("command_id"), why))
        canonical = " ".join(rec["command_argv"])
        if rec.get("command") != canonical:
            reasons.append("COMMAND DISPLAY MISMATCH: %r != canonical %r "
                           "(the display string must be exactly the joined "
                           "argv)" % (rec.get("command"), canonical[:80]))
        # ---- executable identity REVALIDATION -----------------------------
        # The recorded resolved_executable is re-derived NOW from argv[0]
        # with the same canonical resolver: it must still resolve, must
        # resolve OUTSIDE the project, and must equal what the recorder
        # executed — a swapped PATH or project-local executable is caught.
        recorded_exe = rec.get("resolved_executable")
        now_exe, err = gp.resolve_executable(rec["command_argv"][0], root)
        if err:
            reasons.append("EXECUTABLE IDENTITY: %s" % err)
        elif not (isinstance(recorded_exe, str)
                  and os.path.isabs(recorded_exe)):
            reasons.append("EXECUTABLE IDENTITY: resolved_executable %r is "
                           "not an absolute path" % (recorded_exe,))
        elif os.path.realpath(recorded_exe) != now_exe:
            reasons.append("EXECUTABLE IDENTITY MISMATCH: record says %r "
                           "but argv[0] resolves to %r now — the identity "
                           "is re-derived, never trusted"
                           % (recorded_exe, now_exe))
    if expected_tree is not None:
        if rec["tree_digest"].lower() != expected_tree:
            reasons.append("TREE MISMATCH: recorded tree_digest %s… != "
                           "committed-tree digest at HEAD %s…"
                           % (rec["tree_digest"][:12], expected_tree[:12]))
    # ---- artifact verification: exists, inside root, digest matches -------
    if root is not None:
        artifact = str(rec["artifact"]).split("#", 1)[0]
        root_abs = os.path.realpath(root)
        cand = artifact if os.path.isabs(artifact) \
            else os.path.join(root_abs, artifact)
        cand = os.path.realpath(cand)
        if not (cand == root_abs or cand.startswith(root_abs + os.sep)):
            reasons.append("artifact %r resolves OUTSIDE the project root"
                           % artifact)
        elif not os.path.isfile(cand):
            reasons.append("artifact %r missing (not a readable file)"
                           % artifact)
        else:
            try:
                actual = gp.sha256_file(cand)
            except OSError as e:
                reasons.append("artifact %r unreadable: %s" % (artifact, e))
            else:
                if actual != rec["artifact_sha256"].lower():
                    reasons.append("DIGEST MISMATCH: artifact %r recomputed "
                                   "sha256 %s… != recorded %s…"
                                   % (artifact, actual[:12],
                                      rec["artifact_sha256"][:12]))
                else:
                    # ---- output-binding RE-CHECK from the hashed bytes ----
                    binder = gp.OUTPUT_BINDINGS.get(rec.get("command_id"))
                    if binder is not None:
                        try:
                            with open(cand, "rb") as fh:
                                captured = gp.extract_captured_stdout(
                                    fh.read())
                        except OSError as e:
                            reasons.append("artifact %r unreadable for "
                                           "output binding: %s"
                                           % (artifact, e))
                        else:
                            bound, breason = binder(captured, head, root)
                            if not bound:
                                reasons.append("OUTPUT BINDING: %s"
                                               % breason)
    return reasons


def collect(paths):
    files = []
    for p in paths:
        if os.path.isdir(p):
            files += sorted(f for f in glob.glob(os.path.join(p, "*.json"))
                            if os.path.isfile(f))
        else:
            files.append(p)
    return files


def bounded_max_age(value):
    days = int(value)
    if not 1 <= days <= 7:
        raise argparse.ArgumentTypeError("must be between 1 and 7 days")
    return days


def main(argv=None, _test_now=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+",
                    help="evidence JSON files or directories of them")
    ap.add_argument("--root", required=True,
                    help="project root (a git checkout) — HEAD, the "
                         "committed-tree digest, and working-tree "
                         "cleanliness are all derived here")
    ap.add_argument("--environment", required=True)
    ap.add_argument("--project", required=True)
    ap.add_argument("--profile", required=True,
                    choices=sorted(RECOGNIZED_PROFILES),
                    help="required cross-check against the canonical "
                         "Project profile: field committed in "
                         ".solo/project.md at HEAD")
    ap.add_argument("--commit", default=None,
                    help="OPTIONAL cross-check: must EXACTLY equal the "
                         "HEAD the checker derives itself (usage error "
                         "otherwise). Never a source of truth.")
    ap.add_argument("--max-age-days", type=bounded_max_age, default=7,
                    help="freshness window (1-7 days; cannot loosen policy)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    if not os.path.isdir(args.root):
        print("--root must be an existing directory")
        return 2
    head = gp.git_head(args.root)
    if head is None:
        print("--root %r is not a git checkout — the checker derives HEAD "
              "itself and cannot proceed without one" % args.root)
        return 2
    if args.commit is not None and args.commit != head:
        print("--commit %r does not EXACTLY equal derived HEAD %s — "
              "caller-provided commits are never trusted" %
              (args.commit, head))
        return 2
    committed_profile, profile_err = gp.committed_project_profile(args.root)
    if profile_err:
        print("committed project profile unavailable: %s" % profile_err)
        return 2
    if args.profile != committed_profile:
        print("--profile %r does not match %r recorded in the committed %s "
              "at HEAD" % (args.profile, committed_profile,
                            gp.PROJECT_PROFILE_SOURCE))
        return 2
    now = (_test_now if _test_now is not None else
           datetime.datetime.now(datetime.timezone.utc))
    if (not isinstance(now, datetime.datetime) or now.tzinfo is None or
            now.utcoffset() is None):
        print("internal test clock must be a timezone-aware datetime")
        return 2
    try:
        schema = gp.load_schema()
    except Exception as e:
        print("cannot load bundled gate-evidence schema: %s" % e)
        return 2
    expected_tree = gp.committed_tree_digest(args.root)
    if expected_tree is None:
        print("cannot read the committed tree at HEAD")
        return 2

    # ---- unverifiable working states fail the gate outright ---------------
    problems = []
    tracked = gp.evidence_tracked_in_head(args.root)
    if tracked is None:
        problems.append("git runtime-state tracking check FAILED — an "
                        "unverifiable tracking state fails the gate "
                        "(fail closed, never treated as untracked)")
    elif tracked:
        problems.append(".solo/gate-evidence or .solo/run-state files are "
                        "TRACKED in HEAD — unsupported state; the only "
                        "supported workflow keeps both generated runtime "
                        "directories untracked/gitignored")
    state = gp.repo_state(args.root)
    if state is None:
        problems.append("git repository-state check FAILED — an "
                        "unverifiable working state fails the gate "
                        "(fail closed, never treated as clean)")
    elif state["dirty"]:
        problems.append("repository is not clean: %d staged/unstaged/"
                        "untracked path(s) outside the untracked runtime "
                        "dirs (e.g. %s) — the checkout no longer matches "
                        "HEAD, so no evidence can be verified against it"
                        % (len(state["dirty"]),
                           "; ".join(state["dirty"][:3])))

    files = collect(args.paths)
    ev_real = os.path.join(os.path.realpath(args.root),
                           *gp.EVIDENCE_DIR.split("/"))
    for path in files:
        rp = os.path.realpath(path)
        if not (rp == ev_real or rp.startswith(ev_real + os.sep)):
            print("input record %r resolves outside <root>/%s/ — evidence "
                  "must be read from the evidence directory only"
                  % (path, gp.EVIDENCE_DIR))
            return 2
    results, by_category = [], {}
    rejected = 0
    for path in files:
        try:
            with open(path, encoding="utf-8") as fh:
                rec = json.load(fh)
        except Exception as e:
            results.append({"file": path, "accepted": False,
                            "category": None, "status": None,
                            "reasons": ["invalid JSON: %s" % e]})
            rejected += 1
            continue
        reasons = check_record(rec, head, args.environment, now,
                               args.max_age_days, project=args.project,
                               root=args.root, profile=committed_profile,
                               expected_tree=expected_tree, schema=schema)
        cat = rec.get("category") if isinstance(rec, dict) else None
        entry = {"file": path, "category": cat,
                 "status": rec.get("status") if isinstance(rec, dict)
                 else None,
                 "accepted": not reasons, "reasons": reasons}
        results.append(entry)
        if not reasons and cat:
            by_category.setdefault(cat, []).append(entry)
        rejected += 1 if reasons else 0

    for cat, entries in sorted(by_category.items()):
        if len(entries) > 1:
            for e in entries:
                e["accepted"] = False
                e["reasons"].append("DUPLICATE: category %r has %d records — "
                                    "exactly one is required"
                                    % (cat, len(entries)))
            problems.append("duplicate records for category %r (%d)"
                            % (cat, len(entries)))
            rejected += len(entries)
    accepted = {c: e[0] for c, e in by_category.items()
                if len(e) == 1 and e[0]["accepted"]}
    verified_cats = sorted(c for c, e in accepted.items()
                           if e["status"] != "not-applicable")
    na_cats = sorted(c for c, e in accepted.items()
                     if e["status"] == "not-applicable")
    missing = sorted(CATEGORIES - set(accepted))
    for cat in missing:
        problems.append("category %r has NO accepted record (evidence or "
                        "N/A) — the gate must not pass" % cat)
    applicable = len(CATEGORIES) - len(na_cats)
    applicable_max = applicable * gp.POINTS_PER_CATEGORY

    ok = (not rejected and not missing and tracked is False
          and state is not None and not state["dirty"])
    if args.json:
        print(json.dumps({"checked": len(files), "rejected": rejected,
                          "derived_head": head,
                          "committed_tree_sha256": expected_tree,
                          "workspace_clean": bool(state) and not state["dirty"],
                          "evidence_tracked_in_head": tracked,
                          "missing_categories": missing,
                          "verified_categories": verified_cats,
                          "na_categories": na_cats,
                          "applicable_categories": applicable,
                          "applicable_max": applicable_max,
                          "scope": ("category-record evidence; necessary "
                                    "but not sufficient for launch"),
                          "reviewer_required_controls": sorted(
                              REVIEWER_REQUIRED_CONTROLS),
                          "complete": ok, "results": results}, indent=2))
    else:
        for r in results:
            mark = "PASS  " if r["accepted"] else "REJECT"
            extra = "" if r["accepted"] else "  <- " + "; ".join(r["reasons"])
            print("%s %s [%s]%s" % (mark, r["file"], r["category"], extra))
        for p in problems:
            print("FAIL   %s" % p)
        print("== HEAD %s | %d record(s), %d rejected, %d verified + %d N/A "
              "= %d/14 categories accepted (%d applicable; score denominator /%d) =="
              % (head[:12], len(files), rejected, len(verified_cats),
                 len(na_cats), len(accepted), applicable, applicable_max))
        print("SCOPE  14/14 verifies category records only; launch review "
              "still requires separate evidence for: %s"
              % ", ".join(sorted(REVIEWER_REQUIRED_CONTROLS)))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
