#!/usr/bin/env python3
"""build_release.py — package solo-suite for release. Stdlib only.

PACKAGING MODEL: files are read by object ID from one selected, immutable Git
commit, filtered through an explicit ALLOWLIST, and materialized in a clean
temporary staging directory. No content is copied from the live checkout.
Ignored files and worktree-only artifacts therefore cannot ship:
`.coverage`, `scan.json`, `__pycache__`, `dist/`, `.pytest_cache`,
`node_modules`, `.solo/`, editor droppings, and `*.pyc` are excluded by
construction, and the builder additionally ASSERTS none of the forbidden
names appear in the final archive.

Produces in --out (default dist/):
  solo-suite-plugin-v<version>.zip   one enclosing top-level folder
  SHA256SUMS                         checksum of the zip + every packaged file
  sbom.json                          CycloneDX-style dependency inventory
  provenance.json                    build metadata: version, exact source
                                     commit/tree/blob object IDs, staged tree
                                     digest, time, builder, artifact digest

Version comes from .claude-plugin/marketplace.json.
"""
import argparse
import base64
import binascii
import datetime
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import urllib.parse
import zipfile

# ---- the allowlist: everything shipped is named here ----------------------
ALLOW_DIRS = (".claude-plugin", ".github", "plugins", "release", "tests")
ALLOW_FILES = (".gitattributes", "CHANGELOG.md", "CONTRIBUTING.md", "LICENSE", "README.md",
               "SECURITY.md", "site-doctor-cheatsheet.docx", "ci-requirements.txt",
               "requirements-dev.lock")
# ---- denied even inside allowlisted dirs -----------------------------------
EXCLUDE_DIRS = {"__pycache__", ".git", "dist", ".pytest_cache",
                "node_modules", ".solo", ".venv", "venv", ".cache",
                ".mypy_cache", ".ruff_cache"}
EXCLUDE_EXT = {".pyc", ".pyo", ".orig", ".rej"}
EXCLUDE_FILES = {".coverage", "scan.json", "coverage.xml", ".DS_Store",
                 "Thumbs.db"}
FORBIDDEN_IN_ZIP = (".coverage", "scan.json", "__pycache__", ".pyc",
                    ".pytest_cache", "node_modules")
REGULAR_GIT_MODES = {"100644", "100755"}
RELEASE_VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
CLAUDE_CLI_PACKAGE = "@anthropic-ai/claude-code"
CLAUDE_CLI_LOCK_PATH = "release/claude-cli/package-lock.json"
UNRELEASED_REMEDIATION_PATH = "release/unreleased-remediation.json"


class ReleaseBuildError(RuntimeError):
    """The selected Git source cannot be packaged safely."""


def strict_release_version(value):
    """Return an ASCII numeric x.y.z release version or fail closed.

    The marketplace value becomes both a ZIP member prefix and an output
    filename.  It is therefore validated before either path is constructed
    (and before the output directory is created).
    """
    if not isinstance(value, str) or not RELEASE_VERSION_RE.fullmatch(value):
        raise ReleaseBuildError(
            "marketplace metadata.version must match "
            "^[0-9]+\\.[0-9]+\\.[0-9]+$ (got %r)" % (value,))
    return value


def _safe_git_env():
    """Return an environment that cannot redirect or rewrite Git inputs.

    All inherited ``GIT_*`` variables are removed.  In particular this
    neutralizes GIT_DIR/GIT_WORK_TREE/object-directory/config-count and
    config-file overrides.  Replacement objects are then explicitly disabled
    and ambient system/global configuration is suppressed.  Repository-local
    object-format/config remains available because the selected repository is
    the source being attested.
    """
    env = {key: value for key, value in os.environ.items()
           if not key.upper().startswith("GIT_")}
    env.update({
        "GIT_NO_REPLACE_OBJECTS": "1",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_OPTIONAL_LOCKS": "0",
    })
    return env


def _run_git(root, argv, *, text=False, timeout=30):
    """Run Git with one centrally enforced, non-interactive environment."""
    return subprocess.run(
        ["git"] + list(argv), cwd=root, capture_output=True, text=text,
        encoding="utf-8" if text else None,
        errors="strict" if text else None, timeout=timeout,
        env=_safe_git_env())


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def denied(name):
    return (name in EXCLUDE_FILES
            or name.startswith(".coverage.")
            or os.path.splitext(name)[1] in EXCLUDE_EXT
            or ".tmp." in name)


def generated_untracked(rel):
    """Whether an untracked path is excluded from every release input.

    The workflow intentionally builds after tests so exclusion assertions are
    non-vacuous.  Generated *untracked* pycache/coverage/dist/runtime output
    therefore does not make the staged source dirty.  Tracked changes are
    never filtered, and an untracked path not named by this packaging policy
    remains a hard refusal.
    """
    rel = rel.replace("\\", "/").strip("/")
    parts = [part for part in rel.split("/") if part]
    if not parts:
        return False
    if any(part in EXCLUDE_DIRS for part in parts[:-1]):
        return True
    name = parts[-1]
    return denied(name)


def _git(root, argv, *, text=False):
    """Run non-shell Git plumbing and return stdout or raise safely."""
    result = _run_git(root, argv, text=text, timeout=30)
    if result.returncode != 0:
        stderr = (result.stderr.strip() if text
                  else os.fsdecode(result.stderr).strip())
        raise ReleaseBuildError(
            "git %s failed: %s" % (" ".join(argv), stderr or "exit %d" %
                                    result.returncode))
    return result.stdout


def resolve_git_source(root, revision="HEAD"):
    """Return exact commit/tree/object-format for ``revision``.

    ``root`` must be the repository top level. Requiring that identity avoids
    accidentally packaging a parent repository when a non-repository folder
    is supplied as ``--root``.
    """
    if not revision or revision.startswith("-"):
        raise ReleaseBuildError("the selected Git revision is invalid")
    top = _git(root, ["rev-parse", "--show-toplevel"], text=True).strip()
    if os.path.normcase(os.path.realpath(top)) != os.path.normcase(
            os.path.realpath(root)):
        raise ReleaseBuildError(
            "--root must be the Git repository top level (got %r, expected "
            "%r)" % (root, top))
    commit = _git(
        root, ["rev-parse", "--verify", "%s^{commit}" % revision],
        text=True).strip()
    if not re.fullmatch(r"[0-9a-fA-F]{40}|[0-9a-fA-F]{64}", commit):
        raise ReleaseBuildError("Git returned an invalid commit object ID")
    commit = commit.lower()
    tree = _git(root, ["rev-parse", "%s^{tree}" % commit],
                text=True).strip().lower()
    if not re.fullmatch(r"[0-9a-f]{%d}" % len(commit), tree):
        raise ReleaseBuildError("Git returned an invalid tree object ID")
    try:
        object_format = _git(
            root, ["rev-parse", "--show-object-format"], text=True).strip()
    except ReleaseBuildError:
        object_format = "sha256" if len(commit) == 64 else "sha1"
    return commit, tree, object_format


def git_tree_entries(root, commit):
    """Return validated ``(path, mode, blob_oid)`` entries for ``commit``.

    Git symlinks (120000), gitlinks/submodules (160000), and every other
    non-regular entry are rejected before allowlist filtering. A future
    tracked link can therefore never dereference content outside the source
    tree or silently disappear from provenance.
    """
    if not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", commit):
        raise ReleaseBuildError("an exact commit object ID is required")
    raw = _git(root, ["ls-tree", "-r", "-z", "--full-tree", commit])
    entries = []
    folded = {}
    for record in raw.split(b"\0"):
        if not record:
            continue
        try:
            header, raw_path = record.split(b"\t", 1)
            mode_b, kind_b, oid_b = header.split(b" ", 2)
            path = raw_path.decode("utf-8", "strict")
            mode = mode_b.decode("ascii", "strict")
            kind = kind_b.decode("ascii", "strict")
            oid = oid_b.decode("ascii", "strict").lower()
        except (ValueError, UnicodeDecodeError) as exc:
            raise ReleaseBuildError(
                "the selected Git tree contains an unrepresentable entry") \
                from exc
        parts = path.split("/")
        if (not path or path.startswith("/") or "\\" in path
                or any(part in ("", ".", "..") for part in parts)):
            raise ReleaseBuildError(
                "the selected Git tree contains an unsafe path: %r" % path)
        collision_key = path.casefold()
        if collision_key in folded:
            raise ReleaseBuildError(
                "the selected Git tree has case-colliding paths %r and %r"
                % (folded[collision_key], path))
        folded[collision_key] = path
        if kind != "blob" or mode not in REGULAR_GIT_MODES:
            label = "symlink" if mode == "120000" else "non-regular entry"
            raise ReleaseBuildError(
                "tracked %s is forbidden in a release source tree: %s "
                "(mode %s, type %s)" % (label, path, mode, kind))
        if not re.fullmatch(r"[0-9a-f]{%d}" % len(commit), oid):
            raise ReleaseBuildError(
                "the selected Git tree contains an invalid object ID")
        entries.append((path, mode, oid))
    return sorted(entries)


def packaged_path(path):
    """Whether a validated committed path belongs in the release."""
    parts = path.split("/")
    if path in ALLOW_FILES:
        return True
    if parts[0] not in ALLOW_DIRS or len(parts) < 2:
        return False
    if any(part in EXCLUDE_DIRS for part in parts[:-1]):
        return False
    return not denied(parts[-1])


def read_git_blob(root, oid):
    """Read one immutable blob by object ID, never by a worktree path."""
    return _git(root, ["cat-file", "blob", oid])


def stage(root, staging, commit=None, entries=None, blob_oids=None):
    """Materialize allowlisted committed blobs; return staged rel paths.

    The optional ``blob_oids`` mapping is populated for provenance. The
    historical two-argument API remains available to callers and selects
    ``HEAD``.
    """
    if commit is None:
        commit, _tree, _fmt = resolve_git_source(root)
    if entries is None:
        entries = git_tree_entries(root, commit)
    staged = []
    for rel, _mode, oid in entries:
        if not packaged_path(rel):
            continue
        data = read_git_blob(root, oid)
        dst = os.path.join(staging, *rel.split("/"))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with open(dst, "wb") as stream:
            stream.write(data)
        staged.append(rel)
        if blob_oids is not None:
            blob_oids[rel] = oid
    return sorted(staged)


def commit_file(root, entries, path):
    """Return a required committed regular file's bytes."""
    match = next((oid for rel, _mode, oid in entries if rel == path), None)
    if match is None:
        raise ReleaseBuildError(
            "required release source file is absent from the selected "
            "commit: %s" % path)
    return read_git_blob(root, match)


def _npm_purl(name, version):
    return "pkg:npm/%s@%s" % (
        urllib.parse.quote(name, safe="/"),
        urllib.parse.quote(version, safe=".-+"))


def locked_claude_toolchain(lock_bytes):
    """Derive the release CLI toolchain and SBOM graph from package-lock.

    No CLI version, Node engine requirement, download URL, or integrity value
    is supplied by an environment variable or duplicated release constant.
    The committed npm v3 lock is the sole source and is itself bound into
    provenance by SHA-256.
    """
    try:
        lock = json.loads(lock_bytes.decode("utf-8", "strict"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReleaseBuildError(
            "committed %s is invalid: %s" % (CLAUDE_CLI_LOCK_PATH, exc)) \
            from exc
    packages = lock.get("packages")
    if lock.get("lockfileVersion") != 3 or not isinstance(packages, dict):
        raise ReleaseBuildError(
            "%s must be an npm lockfileVersion 3 lock" %
            CLAUDE_CLI_LOCK_PATH)
    root_package = packages.get("")
    if not isinstance(root_package, dict):
        raise ReleaseBuildError(
            "%s has no root package record" % CLAUDE_CLI_LOCK_PATH)
    root_dependencies = root_package.get("dependencies")
    requested_version = (root_dependencies.get(CLAUDE_CLI_PACKAGE)
                         if isinstance(root_dependencies, dict) else None)
    if (not isinstance(requested_version, str)
            or not RELEASE_VERSION_RE.fullmatch(requested_version)):
        raise ReleaseBuildError(
            "%s must lock %s to one exact numeric x.y.z version" %
            (CLAUDE_CLI_LOCK_PATH, CLAUDE_CLI_PACKAGE))

    parsed = []
    by_name = {}
    version_re = re.compile(
        r"^[0-9]+\.[0-9]+\.[0-9]+(?:-[0-9A-Za-z.-]+)?"
        r"(?:\+[0-9A-Za-z.-]+)?$")
    for package_path, package in sorted(packages.items()):
        if package_path == "":
            continue
        marker = "node_modules/"
        if marker not in package_path or not isinstance(package, dict):
            raise ReleaseBuildError(
                "%s contains an unsupported package record %r" %
                (CLAUDE_CLI_LOCK_PATH, package_path))
        name = package_path.rsplit(marker, 1)[1]
        version = package.get("version")
        resolved = package.get("resolved")
        integrity = package.get("integrity")
        license_name = package.get("license")
        if (not name or not isinstance(version, str)
                or not version_re.fullmatch(version)):
            raise ReleaseBuildError(
                "%s package %r has no exact version" %
                (CLAUDE_CLI_LOCK_PATH, package_path))
        if name in by_name:
            raise ReleaseBuildError(
                "%s contains duplicate package name %r; nested duplicate "
                "versions are not supported by this release toolchain" %
                (CLAUDE_CLI_LOCK_PATH, name))
        try:
            resolved_parts = urllib.parse.urlsplit(resolved)
        except (TypeError, ValueError) as exc:
            raise ReleaseBuildError(
                "%s package %r has an invalid resolved URL" %
                (CLAUDE_CLI_LOCK_PATH, name)) from exc
        if (resolved_parts.scheme != "https" or not resolved_parts.hostname
                or resolved_parts.username is not None
                or resolved_parts.password is not None
                or resolved_parts.fragment):
            raise ReleaseBuildError(
                "%s package %r must have a credential-free HTTPS resolved "
                "URL" % (CLAUDE_CLI_LOCK_PATH, name))
        if not isinstance(integrity, str) or not integrity.startswith(
                "sha512-"):
            raise ReleaseBuildError(
                "%s package %r must have sha512 integrity" %
                (CLAUDE_CLI_LOCK_PATH, name))
        try:
            digest_bytes = base64.b64decode(
                integrity.split("-", 1)[1], validate=True)
        except (ValueError, binascii.Error) as exc:
            raise ReleaseBuildError(
                "%s package %r has malformed sha512 integrity" %
                (CLAUDE_CLI_LOCK_PATH, name)) from exc
        if len(digest_bytes) != 64:
            raise ReleaseBuildError(
                "%s package %r has a non-SHA-512 integrity length" %
                (CLAUDE_CLI_LOCK_PATH, name))
        if not isinstance(license_name, str) or not license_name.strip():
            raise ReleaseBuildError(
                "%s package %r has no lock-derived license metadata" %
                (CLAUDE_CLI_LOCK_PATH, name))
        item = {
            "path": package_path,
            "name": name,
            "version": version,
            "resolved": resolved,
            "integrity": integrity,
            "sha512_hex": digest_bytes.hex(),
            "license": license_name.strip(),
            "optional": bool(package.get("optional", False)),
            "dependencies": package.get("dependencies", {}),
            "optional_dependencies": package.get(
                "optionalDependencies", {}),
            "engines": package.get("engines", {}),
            "os": package.get("os", []),
            "cpu": package.get("cpu", []),
            "libc": package.get("libc", []),
        }
        for field in ("dependencies", "optional_dependencies", "engines"):
            if not isinstance(item[field], dict):
                raise ReleaseBuildError(
                    "%s package %r has invalid %s metadata" %
                    (CLAUDE_CLI_LOCK_PATH, name, field))
        for field in ("os", "cpu", "libc"):
            if not isinstance(item[field], list) or not all(
                    isinstance(value, str) for value in item[field]):
                raise ReleaseBuildError(
                    "%s package %r has invalid %s metadata" %
                    (CLAUDE_CLI_LOCK_PATH, name, field))
        parsed.append(item)
        by_name[name] = item

    cli = by_name.get(CLAUDE_CLI_PACKAGE)
    if cli is None or cli["version"] != requested_version:
        raise ReleaseBuildError(
            "%s root dependency and resolved %s version do not match" %
            (CLAUDE_CLI_LOCK_PATH, CLAUDE_CLI_PACKAGE))
    node_engine = cli["engines"].get("node")
    if (not isinstance(node_engine, str) or not node_engine.strip()
            or len(node_engine) > 128 or "\n" in node_engine):
        raise ReleaseBuildError(
            "%s resolved %s record has no valid Node engine requirement" %
            (CLAUDE_CLI_LOCK_PATH, CLAUDE_CLI_PACKAGE))

    for item in parsed:
        for dependency in sorted(set(item["dependencies"]) |
                                 set(item["optional_dependencies"])):
            if dependency not in by_name:
                raise ReleaseBuildError(
                    "%s package %r references unresolved dependency %r" %
                    (CLAUDE_CLI_LOCK_PATH, item["name"], dependency))
    return {
        "lockfile_version": lock["lockfileVersion"],
        "root_name": root_package.get("name"),
        "root_version": root_package.get("version"),
        "node_engine": node_engine.strip(),
        "claude_cli": cli,
        "packages": parsed,
    }


def commit_epoch(root, commit="HEAD"):
    """Committer timestamp of the selected commit — the archive clock.
    SOURCE_DATE_EPOCH overrides it (reproducible-builds.org convention)."""
    env = os.environ.get("SOURCE_DATE_EPOCH")
    if env and env.isdigit():
        return int(env)
    try:
        r = _run_git(root, ["show", "-s", "--format=%ct", commit],
                     text=True, timeout=10)
        if r.returncode == 0 and r.stdout.strip().isdigit():
            return int(r.stdout.strip())
    except Exception:
        pass
    return 315532800  # 1980-01-01, the ZIP epoch floor


def zip_date_time(epoch):
    t = datetime.datetime.fromtimestamp(max(epoch, 315532800),
                                        datetime.timezone.utc)
    return (t.year, t.month, t.day, t.hour, t.minute, t.second)


def git_state(root):
    """Return ``(commit, material_dirty_paths)``.

    Tracked modifications/deletions always count.  Untracked files count
    unless the same explicit packaging policy excludes them as generated
    output.  This lets CI prove those outputs stay out of the ZIP without
    weakening the guard for material source files.
    """
    try:
        r = _run_git(root, ["rev-parse", "HEAD"], text=True, timeout=10)
        if r.returncode != 0:
            return None, []
        commit = r.stdout.strip()
        # Ask separately for tracked and untracked state.  Parsing porcelain
        # lines cannot safely recover quoted/non-ASCII filenames, while
        # ``git ls-files -z`` gives exact NUL-delimited untracked paths.
        s = _run_git(
            root, ["status", "--porcelain", "--untracked-files=no"],
            text=True, timeout=10)
        if s.returncode != 0:
            return commit, ["!! git status failed"]
        dirty = [ln for ln in s.stdout.splitlines() if ln.strip()]
        u = _run_git(
            root, ["ls-files", "--others", "--exclude-standard", "-z"],
            timeout=10)
        if u.returncode != 0:
            return commit, dirty + ["!! git ls-files failed"]
        untracked = [os.fsdecode(raw) for raw in u.stdout.split(b"\0")
                     if raw]
        dirty.extend("?? " + rel for rel in untracked
                     if not generated_untracked(rel))
        return commit, dirty
    except Exception:
        return None, []


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="dist")
    ap.add_argument("--root", default=os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))))
    ap.add_argument("--commit", default="HEAD",
                    help="commit/ref to package (resolved once to an exact "
                         "commit object; default: HEAD)")
    ap.add_argument("--allow-no-git", action="store_true",
                    help="deprecated compatibility flag; non-Git release "
                         "sources are no longer permitted")
    ap.add_argument("--allow-dirty", action="store_true",
                    help="permit uncommitted changes (provenance records "
                         "dirty=true, but package bytes still come only from "
                         "the selected commit)")
    args = ap.parse_args(argv)
    root = os.path.abspath(args.root)
    try:
        commit, source_tree_oid, object_format = resolve_git_source(
            root, args.commit)
        entries = git_tree_entries(root, commit)
        if any(rel == UNRELEASED_REMEDIATION_PATH
               for rel, _mode, _oid in entries):
            raise ReleaseBuildError(
                "%s is present; apply the planned suite/component version "
                "bumps and remove the plan in the release-cut commit before "
                "packaging" % UNRELEASED_REMEDIATION_PATH)
        mk = json.loads(commit_file(
            root, entries, ".claude-plugin/marketplace.json").decode(
                "utf-8", "strict"))
        version = strict_release_version(mk["metadata"]["version"])
        claude_lock_bytes = commit_file(
            root, entries, CLAUDE_CLI_LOCK_PATH)
        claude_toolchain = locked_claude_toolchain(claude_lock_bytes)
    except (ReleaseBuildError, UnicodeDecodeError, json.JSONDecodeError,
            KeyError) as exc:
        if args.allow_no_git:
            print("REFUSED: --allow-no-git is deprecated; release inputs "
                  "must be an exact committed Git object tree")
        else:
            print("REFUSED: %s" % exc)
        return 2

    head_commit, dirty = git_state(root)
    if head_commit is None:
        print("REFUSED: unable to inspect the Git worktree state")
        return 2
    if dirty and not args.allow_dirty:
        print("REFUSED: working tree has %d uncommitted change(s) — commit "
              "first (or --allow-dirty):" % len(dirty))
        for ln in dirty[:15]:
            print("  " + ln)
        return 2

    top = "solo-suite-plugin-v%s" % version
    os.makedirs(args.out, exist_ok=True)
    zip_path = os.path.join(args.out, top + ".zip")

    tmp = tempfile.mkdtemp(prefix="solo-suite-stage-")
    try:
        staging = os.path.join(tmp, top)
        os.makedirs(staging)
        blob_oids = {}
        staged = stage(root, staging, commit=commit, entries=entries,
                       blob_oids=blob_oids)

        # ---- REPRODUCIBLE archive: fixed timestamps (commit time /
        # SOURCE_DATE_EPOCH), normalized permissions (0644 files, 0755
        # scripts), sorted member order, fixed compression level ----------
        epoch = commit_epoch(root, commit)
        dt = zip_date_time(epoch)
        file_hashes = {}
        tree = hashlib.sha256()
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
            for rel in staged:
                full = os.path.join(staging, rel)
                with open(full, "rb") as fsrc:
                    data = fsrc.read()
                info = zipfile.ZipInfo("%s/%s" % (top, rel), date_time=dt)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.create_system = 3  # unix, stable across build hosts
                mode = 0o755 if (rel.endswith(".py")
                                 or data[:2] == b"#!") else 0o644
                info.external_attr = (stat.S_IFREG | mode) << 16
                z.writestr(info, data, compresslevel=9)
                digest = hashlib.sha256(data).hexdigest()
                file_hashes[rel] = digest
                tree.update(rel.encode("utf-8"))
                tree.update(b"\0")
                tree.update(digest.encode("ascii"))
                tree.update(b"\n")
        staged_tree_digest = tree.hexdigest()

        # ---- assert the forbidden names really are absent ------------------
        with zipfile.ZipFile(zip_path) as z:
            names = z.namelist()
        offenders = [n for n in names
                     if any(bad in n for bad in FORBIDDEN_IN_ZIP)]
        if offenders:
            print("FATAL: forbidden artifacts packaged: %s" % offenders[:10])
            os.unlink(zip_path)
            return 1
        tops = {n.split("/")[0] for n in names}
        if tops != {top}:
            print("FATAL: ZIP must have exactly one enclosing folder %r "
                  "(got %s)" % (top, sorted(tops)))
            os.unlink(zip_path)
            return 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    zip_digest = sha256(zip_path)
    # Metadata uses the same source epoch as the archive.  Rebuilding the
    # same commit now reproduces the ZIP, SBOM, and provenance timestamps;
    # wall-clock build time is validation-log data, not artifact identity.
    now = datetime.datetime.fromtimestamp(
        epoch, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    with open(os.path.join(args.out, "SHA256SUMS"), "w", encoding="utf-8",
              newline="\n") as f:
        f.write("%s  %s\n" % (zip_digest, os.path.basename(zip_path)))
        for rel in sorted(file_hashes):
            f.write("%s  %s/%s\n" % (file_hashes[rel], top, rel))

    def _lock_pins(lock_text):
        """(name, version, n_hashes) per pin from requirements-dev.lock —
        the SBOM's dependency inventory is DERIVED from the shipped lock,
        never hand-maintained."""
        import re as _re
        pins = []
        if lock_text is None:
            return pins
        for block in _re.split(r"(?m)^(?=[A-Za-z0-9._-]+==)", lock_text):
            m = _re.match(r"^([A-Za-z0-9._-]+)==([0-9a-zA-Z.]+)", block)
            if not m:
                continue
            pins.append((m.group(1), m.group(2),
                         len(_re.findall(r"--hash=sha256:", block))))
        return pins

    def _tool_version(argv):
        try:
            kwargs = {}
            if os.path.basename(argv[0]).lower() in ("git", "git.exe"):
                kwargs["env"] = _safe_git_env()
                kwargs["cwd"] = root
            r = subprocess.run(argv, capture_output=True, text=True,
                               timeout=15, **kwargs)
            if r.returncode == 0:
                return r.stdout.strip().splitlines()[0]
        except Exception:
            pass
        return "unavailable at build time"
    claude_lock_digest = hashlib.sha256(claude_lock_bytes).hexdigest()
    locked_cli = claude_toolchain["claude_cli"]
    build_tools = [
        {"vendor": "python.org", "name": "python",
         "version": sys.version.split()[0]},
        {"vendor": "git-scm.com", "name": "git",
         "version": _tool_version(["git", "--version"])},
        {"vendor": "Anthropic", "name": "Claude Code CLI",
         "version": locked_cli["version"],
         "hashes": [{"alg": "SHA-512",
                     "content": locked_cli["sha512_hex"]}]},
    ]
    actual_node_version = os.environ.get("SOLO_NODE_VERSION")
    if actual_node_version:
        build_tools.append({
            "vendor": "OpenJS Foundation", "name": "node",
            "version": actual_node_version,
        })
    sbom = {
        "bomFormat": "CycloneDX", "specVersion": "1.5", "version": 1,
        "metadata": {"timestamp": now,
                     "properties": [
                         {"name": "timestamp-basis",
                          "value": "source commit epoch or "
                                   "SOURCE_DATE_EPOCH; normalized for "
                                   "reproducibility, not wall-clock build "
                                   "execution time"},
                     ],
                     "tools": build_tools,
                     "component": {
            "type": "application", "name": "solo-suite",
            "bom-ref": "pkg:generic/solo-suite@%s" % version,
            "version": version, "licenses": [{"license": {"id": "MIT"}}]}},
        "components": [],
        "dependencies": [],
        "properties": [
            {"name": "runtime-dependencies",
             "value": "none — every helper script runs on the Python "
                      "standard library alone; listed components are "
                      "optional CI/release tooling. Python packages are "
                      "hash-locked in requirements-dev.lock and installed "
                      "with pip --require-hashes; Claude CLI packages are "
                      "integrity-locked in release/claude-cli/"
                      "package-lock.json and installed with npm ci"},
            {"name": "python-supported", "value": ">=3.9"},
            {"name": "locked-node-engine",
             "value": claude_toolchain["node_engine"]},
            {"name": "locked-claude-cli",
             "value": "%s@%s" % (CLAUDE_CLI_PACKAGE,
                                    locked_cli["version"])},
            {"name": "file-count", "value": str(len(file_hashes))},
            {"name": "packaging",
             "value": "allowlisted blobs read from one exact Git commit; "
                      "reproducible archive (commit-"
                      "time timestamps via SOURCE_DATE_EPOCH convention, "
                      "normalized 0644/0755 permissions, sorted members, "
                      "fixed compression); runner artifacts excluded by "
                      "construction and asserted absent"},
        ]}
    lock_bytes = commit_file(root, entries, "requirements-dev.lock")
    try:
        lock_text = lock_bytes.decode("utf-8", "strict")
    except UnicodeDecodeError as exc:
        print("FATAL: committed requirements-dev.lock is not UTF-8: %s" % exc)
        return 1
    pins = _lock_pins(lock_text)
    pin_versions = {n: v for n, v, _ in pins}
    metadata_bytes = commit_file(
        root, entries, "release/dependency-metadata.json")
    try:
        dependency_metadata = json.loads(metadata_bytes.decode(
            "utf-8", "strict"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        print("FATAL: committed dependency metadata is invalid: %s" % exc)
        return 1
    package_metadata = dependency_metadata.get("packages")
    if (dependency_metadata.get("schema") !=
            "solo-suite/dependency-metadata-v1" or
            not isinstance(package_metadata, dict)):
        print("FATAL: dependency metadata schema is invalid")
        return 1
    if set(package_metadata) != set(pin_versions):
        print("FATAL: dependency metadata keys do not exactly cover the "
              "requirements lock")
        return 1
    for name, data in package_metadata.items():
        if (not isinstance(data, dict)
                or not isinstance(data.get("direct"), bool)
                or not re.fullmatch(r"[A-Za-z0-9.-]+",
                                    str(data.get("license", "")))
                or not isinstance(data.get("depends_on"), list)
                or any(dep not in pin_versions
                       for dep in data.get("depends_on", []))):
            print("FATAL: dependency metadata entry is invalid: %s" % name)
            return 1
    direct_deps = sorted(name for name, data in package_metadata.items()
                         if data["direct"])
    lock_digest = hashlib.sha256(lock_bytes).hexdigest()
    dependency_metadata_digest = hashlib.sha256(metadata_bytes).hexdigest()
    sbom["metadata"]["properties"].extend([
        {"name": "requirements-lock-sha256", "value": lock_digest},
        {"name": "dependency-metadata-sha256",
         "value": dependency_metadata_digest},
        {"name": "claude-cli-package-lock-sha256",
         "value": claude_lock_digest},
    ])
    purl = lambda n: "pkg:pypi/%s@%s" % (n, pin_versions.get(n, "unknown"))
    for name, ver, n_hashes in pins:
        role = ("direct optional CI test/build dependency (top-level in "
                "ci-requirements.txt)" if name in direct_deps
                else "transitive dependency of the locked CI test/build "
                     "environment")
        sbom["components"].append(
            {"type": "library", "name": name, "version": ver,
              "scope": "optional", "bom-ref": purl(name),
              "purl": purl(name),
              "licenses": [{"license": {
                  "id": package_metadata[name]["license"]}}],
              "description": "%s; hash-locked in requirements-dev.lock "
                            "(%d sha256 artifact hashes); installed only "
                            "via pip --require-hashes"
                            % (role, n_hashes)})
    npm_purls = {item["name"]: _npm_purl(item["name"], item["version"])
                  for item in claude_toolchain["packages"]}
    for item in claude_toolchain["packages"]:
        properties = [
            {"name": "solo-suite:package-lock-path", "value": item["path"]},
            {"name": "solo-suite:optional", "value": str(
                item["optional"]).lower()},
        ]
        for field in ("os", "cpu", "libc"):
            if item[field]:
                properties.append({
                    "name": "solo-suite:npm-%s" % field,
                    "value": ",".join(item[field]),
                })
        sbom["components"].append({
            "type": "application" if item["name"] == CLAUDE_CLI_PACKAGE
                    else "library",
            "name": item["name"],
            "version": item["version"],
            "scope": "optional",
            "bom-ref": npm_purls[item["name"]],
            "purl": npm_purls[item["name"]],
            "hashes": [{"alg": "SHA-512", "content": item["sha512_hex"]}],
            "licenses": [{"license": {"name": item["license"]}}],
            "externalReferences": [{"type": "distribution",
                                    "url": item["resolved"]}],
            "properties": properties,
            "description": ("lock-derived optional release validation "
                            "toolchain package from %s" %
                            CLAUDE_CLI_LOCK_PATH),
        })
    sbom["dependencies"].append(
        {"ref": "pkg:generic/solo-suite@%s" % version,
         "dependsOn": sorted(
             [purl(n) for n in direct_deps if n in pin_versions] +
             [npm_purls[CLAUDE_CLI_PACKAGE]])})
    for name, ver, _n in pins:
        sbom["dependencies"].append(
            {"ref": purl(name),
             "dependsOn": sorted(purl(d) for d in
                                  package_metadata[name]["depends_on"]
                                  if d in pin_versions)})
    for item in claude_toolchain["packages"]:
        dependency_names = (set(item["dependencies"]) |
                            set(item["optional_dependencies"]))
        sbom["dependencies"].append({
            "ref": npm_purls[item["name"]],
            "dependsOn": sorted(npm_purls[name]
                                for name in dependency_names),
        })
    expected_component_count = len(pins) + len(
        claude_toolchain["packages"])
    if len(sbom["components"]) != expected_component_count:
        print("FATAL: SBOM component count %d != lock-derived count %d"
              % (len(sbom["components"]), expected_component_count))
        return 1
    with open(os.path.join(args.out, "sbom.json"), "w", encoding="utf-8",
              newline="\n") as f:
        json.dump(sbom, f, indent=2)

    blob_manifest = hashlib.sha256()
    for rel in sorted(blob_oids):
        blob_manifest.update(rel.encode("utf-8"))
        blob_manifest.update(b"\0")
        blob_manifest.update(blob_oids[rel].encode("ascii"))
        blob_manifest.update(b"\n")
    builder_blob_oid = blob_oids.get("release/build_release.py")
    workflow_blob_oid = blob_oids.get(".github/workflows/ci.yml")
    prov = {
        "artifact": os.path.basename(zip_path),
        "artifact_sha256": zip_digest,
        "version": version,
        "built_at": now,
        "timestamp_basis": ("source commit epoch or SOURCE_DATE_EPOCH; "
                            "normalized for reproducibility, not wall-clock "
                            "build execution time"),
        "builder": {"tool": "release/build_release.py",
                    "python": sys.version.split()[0],
                    "ci": os.environ.get("GITHUB_WORKFLOW", "local"),
                    "selected_commit_blob_oid": builder_blob_oid,
                    "selected_workflow_blob_oid": workflow_blob_oid},
        "locked_release_toolchain": {
            "source": CLAUDE_CLI_LOCK_PATH,
            "lockfile_version": claude_toolchain["lockfile_version"],
            "lock_sha256": claude_lock_digest,
            "node_engine_requirement": claude_toolchain["node_engine"],
            "claude_cli": {
                "package": CLAUDE_CLI_PACKAGE,
                "version": locked_cli["version"],
                "resolved": locked_cli["resolved"],
                "integrity": locked_cli["integrity"],
                "sha512": locked_cli["sha512_hex"],
            },
            "resolved_package_count": len(claude_toolchain["packages"]),
        },
        "ci_context": {
            "repository": os.environ.get("GITHUB_REPOSITORY"),
            "workflow_ref": os.environ.get("GITHUB_WORKFLOW_REF"),
            "run_id": os.environ.get("GITHUB_RUN_ID"),
            "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
            "runner_os": os.environ.get("RUNNER_OS"),
            "runner_arch": os.environ.get("RUNNER_ARCH"),
            "node": os.environ.get("SOLO_NODE_VERSION"),
            "claude_cli": os.environ.get("SOLO_CLAUDE_CLI_VERSION"),
            "cosign": os.environ.get("SOLO_COSIGN_VERSION"),
            "github_cli": os.environ.get("SOLO_GH_VERSION"),
        },
        "materials": [
            {"uri": "git:commit", "digest": {object_format: commit}},
            {"uri": "git:tree", "digest": {object_format: source_tree_oid}},
            {"uri": "requirements-dev.lock",
             "digest": {"sha256": lock_digest}},
            {"uri": "release/dependency-metadata.json",
             "digest": {"sha256": dependency_metadata_digest}},
            {"uri": CLAUDE_CLI_LOCK_PATH,
             "digest": {"sha256": claude_lock_digest}},
        ],
        "source_material": "immutable Git object tree",
        "source_revision_requested": args.commit,
        "source_commit": commit,
        "source_tree_oid": source_tree_oid,
        "source_object_format": object_format,
        "worktree_head_commit": head_commit,
        "source_dirty": bool(dirty),
        "source_dirty_scope": ("diagnostic only: tracked changes plus "
                               "non-generated, non-ignored untracked paths; "
                               "worktree bytes are never release inputs"),
        "packaged_blob_manifest_sha256": blob_manifest.hexdigest(),
        "requirements_lock_sha256": lock_digest,
        "dependency_metadata_sha256": dependency_metadata_digest,
        "claude_cli_package_lock_sha256": claude_lock_digest,
        "packaged_blob_count": len(blob_oids),
        "staged_tree_sha256": staged_tree_digest,
        "file_count": len(file_hashes),
    }
    with open(os.path.join(args.out, "provenance.json"), "w",
              encoding="utf-8", newline="\n") as f:
        json.dump(prov, f, indent=2)
    print("built %s (%d files, sha256 %s..., commit %s)"
          % (zip_path, len(file_hashes), zip_digest[:16],
             (commit or "UNVERIFIED")[:12]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
