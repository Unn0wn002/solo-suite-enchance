#!/usr/bin/env python3
"""check_deps.py — inventory a project's dependencies across ecosystems:
direct vs transitive counts, version pinning, lockfile presence, and
dependency-tree size signals. Complements `npm audit` / `pip-audit`
(which provide the live CVE data this script does not).

Stdlib only. Usage:
    python3 check_deps.py /path/to/project

Exit 0 always (informational).

Exit codes: 0 = inventory produced, nothing left unverified; 2 = usage;
3 = inventory produced but vulnerability status is UNVERIFIED until the
listed ecosystem tools run.
"""
import sys
import os
import json
import re


def find(root, name):
    p = os.path.join(root, name)
    return p if os.path.exists(p) else None


def read_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


EXACT_VERSION = re.compile(
    r"^v?\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")


def pin_kind(spec):
    """Classify a semver range's strictness. A spec is 'exact' only when the
    WHOLE string is a single full version — ranges that merely BEGIN with a
    digit (1.x, 1.2.*, hyphen ranges, || unions, '1.2.3 - 2.0.0') are ranges."""
    s = str(spec).strip()
    if s in ("*", "latest", "") or s.startswith(("x", "X")):
        return "unpinned (*)"
    if s.startswith("^"):
        return "caret (^) — allows minor+patch"
    if s.startswith("~"):
        return "tilde (~) — allows patch"
    if s.startswith(("git", "http", "file:", "link:", "workspace:")):
        return "non-registry"
    if s.startswith("=") and EXACT_VERSION.match(s[1:]):
        return "exact (=)"
    if EXACT_VERSION.match(s):
        return "exact"
    if re.match(r"^v?\d", s):
        return "range"
    return "range"


def analyze_node(root, report):
    pkg_path = find(root, "package.json")
    if not pkg_path:
        return
    pkg = read_json(pkg_path)
    if not pkg:
        return
    report.append("=== Node / npm ===")
    deps = pkg.get("dependencies", {})
    dev = pkg.get("devDependencies", {})
    report.append(f"  Direct dependencies: {len(deps)}")
    report.append(f"  Dev dependencies:    {len(dev)}")

    # pinning breakdown
    kinds = {}
    for spec in deps.values():
        k = pin_kind(spec)
        kinds[k] = kinds.get(k, 0) + 1
    report.append("  Pinning (production deps):")
    for k, n in sorted(kinds.items(), key=lambda x: -x[1]):
        report.append(f"    {n:3d}  {k}")
    unpinned = kinds.get("unpinned (*)", 0)
    if unpinned:
        report.append(f"  [WARN] {unpinned} unpinned dependency(ies) — non-reproducible")

    # lockfile
    locks = [l for l in ("package-lock.json", "pnpm-lock.yaml",
                         "yarn.lock", "npm-shrinkwrap.json") if find(root, l)]
    if locks:
        report.append(f"  [ok] lockfile present: {', '.join(locks)}")
        # count transitive from package-lock if available
        pl = find(root, "package-lock.json")
        if pl:
            data = read_json(pl)
            if data and "packages" in data:
                total = len([k for k in data["packages"] if k])  # skip root ""
                report.append(f"  Total resolved packages (incl. transitive): {total}")
                ratio = total / max(len(deps) + len(dev), 1)
                if ratio > 15:
                    report.append(f"  [WARN] large tree: ~{round(ratio)}x direct "
                                  "deps — review for bloat / attack surface")
    else:
        report.append("  [FAIL] NO LOCKFILE — installs are not reproducible; "
                      "commit a lockfile and use `npm ci`")

    # install-script risk hint
    if "scripts" in pkg and any(k in pkg["scripts"]
                                for k in ("preinstall", "postinstall", "install")):
        report.append("  [note] this package defines install lifecycle scripts — "
                      "fine for your own, but a known malware vector in deps")
    report.append(f"  NEXT: run `npm audit` for live CVE data on these packages.")
    report.append("")


def analyze_python(root, report):
    files = [f for f in ("requirements.txt", "requirements-dev.lock",
                         "requirements.lock", "pyproject.toml", "Pipfile",
                         "setup.py", "setup.cfg") if find(root, f)]
    if not files:
        return
    report.append("=== Python ===")
    report.append(f"  Dependency files: {', '.join(files)}")

    # A metadata-only pyproject is a recognized Python project but declares no
    # dependency surface to audit.  Do not mark its vulnerability status as
    # unverified merely because no dependencies exist.
    if files == ["pyproject.toml"]:
        try:
            with open(find(root, "pyproject.toml"), encoding="utf-8") as f:
                pyproject_text = f.read().lower()
        except Exception:
            pyproject_text = ""
        if not any(marker in pyproject_text for marker in (
                "dependencies", "optional-dependencies", "requires =")):
            report.append("  No dependency declarations found.")
            report.append("")
            return

    req = find(root, "requirements.txt")
    if req:
        try:
            with open(req, encoding="utf-8") as f:
                lines = [l.strip() for l in f
                         if l.strip() and not l.strip().startswith("#")]
        except Exception:
            lines = []
        pinned = sum(1 for l in lines if "==" in l)
        unpinned = len(lines) - pinned
        report.append(f"  requirements.txt entries: {len(lines)} "
                      f"({pinned} exact-pinned, {unpinned} loose)")
        if unpinned:
            report.append(f"  [WARN] {unpinned} unpinned requirement(s) — "
                          "pin with == for reproducible installs")

    requirement_locks = [l for l in ("requirements-dev.lock",
                                     "requirements.lock") if find(root, l)]
    for lock in requirement_locks:
        records = []
        current = ""
        try:
            with open(find(root, lock), encoding="utf-8") as f:
                for raw in f:
                    line = raw.strip()
                    if not line or line.startswith("#"):
                        continue
                    current += (" " if current else "") + line
                    if current.endswith("\\"):
                        current = current[:-1].rstrip()
                        continue
                    records.append(current)
                    current = ""
            if current:
                records.append(current)
        except Exception:
            records = []
        requirements = [r for r in records if not r.startswith("--")]
        pinned = sum(1 for r in requirements if re.match(
            r"^[A-Za-z0-9_.-]+(?:\[[^]]+\])?==[^ ;\\]+", r))
        hashed = sum(1 for r in requirements if "--hash=sha256:" in r)
        report.append("  %s entries: %d (%d exact-pinned, %d hash-covered)"
                      % (lock, len(requirements), pinned, hashed))
        if requirements and pinned == len(requirements) and hashed == len(requirements):
            report.append("  [ok] hash-locked requirements file: %s" % lock)
        else:
            report.append("  [WARN] %s is not fully exact-pinned and hash-covered"
                          % lock)

    locks = requirement_locks + [l for l in (
        "poetry.lock", "Pipfile.lock", "pdm.lock", "uv.lock") if find(root, l)]
    if locks:
        report.append(f"  [ok] lockfile present: {', '.join(locks)}")
    elif not req or unpinned:
        report.append("  [WARN] no lockfile and loose pins — installs may drift")
    if requirement_locks:
        report.append("  NEXT: run `python -m pip_audit --require-hashes -r %s` "
                      "for live CVE data and hash validation."
                      % requirement_locks[0])
    else:
        report.append("  NEXT: run `pip-audit` for live CVE data.")
    report.append("")


def analyze_other(root, report):
    others = {
        "Cargo.toml": ("Rust", "Cargo.lock", "cargo audit"),
        "go.mod": ("Go", "go.sum", "govulncheck ./..."),
        "composer.json": ("PHP", "composer.lock", "composer audit"),
        "Gemfile": ("Ruby", "Gemfile.lock", "bundle audit"),
    }
    for manifest, (lang, lock, tool) in others.items():
        if find(root, manifest):
            report.append(f"=== {lang} ===")
            report.append(f"  Manifest: {manifest}"
                          f"   Lockfile: {'present' if find(root, lock) else 'MISSING'}")
            report.append(f"  NEXT: run `{tool}` for vulnerability data.")
            report.append("")


def main(root):
    if not os.path.isdir(root):
        print(f"Not a directory: {root}")
        return 2
    report = [f"Dependency inventory for: {root}\n"]
    analyze_node(root, report)
    analyze_python(root, report)
    analyze_other(root, report)
    if len(report) == 1:
        report.append("No recognized dependency manifests found at the project root.")
    nexts = sum(1 for line in report if line.strip().startswith("NEXT:"))
    report.append("Reminder: this script reports STRUCTURE (counts, pinning, "
                  "lockfiles). Vulnerability and license data come from the")
    report.append("ecosystem tools above and the dependency-audit skill's triage steps.")
    if nexts:
        report.append("[UNVERIFIED] vulnerability status of %d ecosystem(s) - "
                      "run the NEXT commands above" % nexts)
    report.append("RESULT: pass=%d warn=0 fail=0 unverified=%d"
                  % (1 if not nexts else 0, nexts))
    print("\n".join(report))
    return 3 if nexts else 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1]))
