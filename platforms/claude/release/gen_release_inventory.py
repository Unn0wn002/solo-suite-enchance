#!/usr/bin/env python3
"""gen_release_inventory.py — snapshot a RELEASED solo-suite tree into
release/previous-release-inventory.json. Stdlib only.

The snapshot powers tests/test_release_versioning.py: when the NEXT
release changes any file inside plugins/<name>/ (ignoring generated
files) but keeps plugins/<name>/.claude-plugin/plugin.json at the
previous version, the test fails — the exact defect the v1.0.16 audit
found (ai/gate/solo changed since v1.0.15 without a version bump).

Run it against the PREVIOUS release's pristine tree right after cutting a
release, and commit the result:

    python3 release/gen_release_inventory.py --root <extracted-release> \
        --out release/previous-release-inventory.json

Generated files are excluded by the SHARED ignore rules below (the test
imports them from this module so the two can never drift):
__pycache__/, *.pyc/*.pyo, coverage output, dist/, test caches, VCS and
editor droppings.
"""
import argparse
import hashlib
import json
import os
import stat
import sys

INVENTORY_SCHEMA = "solo-suite/release-inventory-v1"
IGNORED_DIRS = {"__pycache__", ".git", ".pytest_cache", "dist",
                "node_modules", ".solo", ".venv", "venv", ".cache",
                ".mypy_cache", ".ruff_cache", "htmlcov", ".tox",
                ".eggs", ".idea", ".vscode"}
IGNORED_FILES = {".coverage", "coverage.xml", "coverage.json",
                 "scan.json", ".DS_Store", "Thumbs.db"}
IGNORED_EXTS = {".pyc", ".pyo", ".orig", ".rej", ".swp"}


class InventoryError(RuntimeError):
    """A release tree contains an entry that cannot be inventoried safely."""


def ignored_file(name):
    return (name in IGNORED_FILES
            or os.path.splitext(name)[1] in IGNORED_EXTS
            or ".tmp." in name
            or name.startswith(".coverage."))


def _linklike(path, st=None):
    """Detect POSIX links and Windows reparse points/junctions."""
    if os.path.islink(path):
        return True
    if st is None:
        st = os.lstat(path)
    attrs = getattr(st, "st_file_attributes", 0)
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    return bool(reparse and attrs & reparse)


def sha256(path):
    """Hash one regular file without accepting a link-like entry."""
    h = hashlib.sha256()
    with _open_regular(path) as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _open_regular(path):
    """Open and identity-check a regular file; return a binary stream."""
    before = os.lstat(path)
    if _linklike(path, before) or not stat.S_ISREG(before.st_mode):
        raise InventoryError("non-regular or link-like file: %s" % path)
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(path, flags)
    try:
        opened = os.fstat(fd)
        if not stat.S_ISREG(opened.st_mode):
            raise InventoryError("file changed to a non-regular entry: %s"
                                 % path)
        if ((before.st_dev, before.st_ino) != (opened.st_dev, opened.st_ino)
                and before.st_ino and opened.st_ino):
            raise InventoryError("file changed while inventorying: %s" % path)
        return os.fdopen(fd, "rb")
    except Exception:
        os.close(fd)
        raise


def _read_json_regular(path, expected_sha256=None):
    with _open_regular(path) as stream:
        data = stream.read()
    if (expected_sha256 is not None
            and hashlib.sha256(data).hexdigest() != expected_sha256):
        raise InventoryError("file changed while inventorying: %s" % path)
    return json.loads(data.decode("utf-8", "strict"))


def walk_files(root):
    """rel-path -> sha256 for each non-generated regular file.

    Symlinks, junctions/reparse points, device nodes, and other non-regular
    entries fail closed even when named like an ignored directory. The
    inventory can therefore never dereference content outside ``root``.
    """
    root = os.path.abspath(root)
    root_st = os.lstat(root)
    if _linklike(root, root_st) or not stat.S_ISDIR(root_st.st_mode):
        raise InventoryError("inventory root must be a real directory: %s"
                             % root)
    out = {}

    def visit(directory, prefix=""):
        with os.scandir(directory) as iterator:
            entries = sorted(iterator, key=lambda item: item.name)
        for entry in entries:
            rel = "%s/%s" % (prefix, entry.name) if prefix else entry.name
            st = entry.stat(follow_symlinks=False)
            if entry.is_symlink() or _linklike(entry.path, st):
                raise InventoryError(
                    "link-like entry is forbidden in a release tree: %s"
                    % rel)
            if stat.S_ISDIR(st.st_mode):
                if entry.name not in IGNORED_DIRS:
                    visit(entry.path, rel)
            elif stat.S_ISREG(st.st_mode):
                if not ignored_file(entry.name):
                    out[rel.replace(os.sep, "/")] = sha256(entry.path)
            else:
                raise InventoryError(
                    "non-regular entry is forbidden in a release tree: %s"
                    % rel)

    visit(root)
    return out


def build_inventory(root):
    files = walk_files(root)
    mk_path = os.path.join(root, ".claude-plugin", "marketplace.json")
    if ".claude-plugin/marketplace.json" not in files:
        raise InventoryError("release tree is missing marketplace.json")
    mk = _read_json_regular(
        mk_path, files[".claude-plugin/marketplace.json"])
    plugin_versions = {}
    for rel in sorted(files):
        parts = rel.split("/")
        if (len(parts) == 4 and parts[0] == "plugins"
                and parts[2:] == [".claude-plugin", "plugin.json"]):
            name = parts[1]
            pj = os.path.join(root, *parts)
            plugin_versions[name] = _read_json_regular(pj, files[rel])[
                "version"]
    return {
        "schema": INVENTORY_SCHEMA,
        "release": mk["metadata"]["version"],
        "plugin_versions": plugin_versions,
        "files": files,
    }


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True,
                    help="the PREVIOUS release's pristine source tree")
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    inv = build_inventory(os.path.abspath(args.root))
    # Keep the snapshot byte-stable on Windows and POSIX.  With newline=None,
    # Python translates every JSON newline to the host convention.
    with open(args.out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(inv, f, indent=2, sort_keys=True)
        f.write("\n")
    print("wrote %s: release %s, %d plugins, %d files"
          % (args.out, inv["release"], len(inv["plugin_versions"]),
             len(inv["files"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
