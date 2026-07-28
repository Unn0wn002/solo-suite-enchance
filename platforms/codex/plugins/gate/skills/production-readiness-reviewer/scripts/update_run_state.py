#!/usr/bin/env python3
r"""update_run_state.py — the ONLY writer of .solo/run-state/<run_id>.json,
the formal run-state-v1 contract (v1.0.17). Stdlib only.

THE CONTRACT (schema/run-state-v1.schema.json):

    {
      "schema": "run-state-v1",
      "run_id": "<^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$>",
      "base_sha": "<optional 40 lowercase hex>",
      "integration_sha": "<optional 40 lowercase hex>",
      "final_sha": "<optional 40 lowercase hex>"
    }

Keys are EXACTLY those lowercase names. The file lives ONLY in the
untracked generated runtime directory .solo/run-state/ (a commit cannot
contain its own SHA, so tracked carriers are structurally impossible —
this tool refuses roots where runtime state is tracked in HEAD).

WHAT THIS TOOL GUARANTEES:
  * SHAs are DERIVED, never supplied: `advance <field>` reads
    `git rev-parse HEAD` itself. There is no flag to pass a SHA.
  * MONOTONIC transitions: fields advance in the order base_sha ->
    integration_sha -> final_sha. Setting a field is refused when any
    LATER field is already set (a run never rewinds), and a field that is
    set never changes — re-advancing at the same HEAD is an idempotent
    no-op; at a different HEAD it is a refusal.
  * A FROZEN final_sha can NEVER be rewritten to another value. A new
    freeze means a new run_id.
  * ATOMIC replacement (write-temp + os.replace), never in-place edits.
  * Every write is validated against schema/run-state-v1.schema.json
    (via gate_policy's built-in strict evaluator) BEFORE it lands; every
    read of an existing state file is validated too (fail closed on
    corrupt state).
  * `advance` requires a CLEAN repository outside the generated runtime
    dirs (.solo/gate-evidence/, .solo/run-state/) — recording a SHA for a
    tree that does not match it would be meaningless.

Usage:
    python3 update_run_state.py --root . --run-id ftw-123 init
    python3 update_run_state.py --root . --run-id ftw-123 advance base
    python3 update_run_state.py --root . --run-id ftw-123 advance integration
    python3 update_run_state.py --root . --run-id ftw-123 advance final
    python3 update_run_state.py --root . --run-id ftw-123 verify final
    python3 update_run_state.py --root . --run-id ftw-123 show

Exit codes: 0 = ok (state written / verified / shown);
1 = verification failed (verify: field missing or != current HEAD);
2 = refused (usage, invalid run_id, no git, dirty tree, tracked runtime
    state, non-monotonic transition, frozen final_sha rewrite, corrupt
    or foreign state file).
"""
import argparse
import contextlib
import hashlib
import json
import os
import re
import secrets
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(_HERE, "..", "..", "..", "lib")))
try:
    import gate_policy as gp
except ImportError:
    sys.exit("gate_policy.py not found — run from an intact gate plugin "
             "(plugins/gate/lib/gate_policy.py ships beside this skill)")

RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
FIELDS = ("base_sha", "integration_sha", "final_sha")
STAGE_TO_FIELD = {"base": "base_sha", "integration": "integration_sha",
                  "final": "final_sha"}


def schema_path():
    return os.path.normpath(os.path.join(
        _HERE, "..", "schema", "run-state-v1.schema.json"))


def load_run_state_schema():
    with open(schema_path(), encoding="utf-8") as f:
        return json.load(f)


def atomic_write_bytes(path, data):
    parent = os.path.dirname(path) or "."
    os.makedirs(parent, mode=0o700, exist_ok=True)
    try:
        os.chmod(parent, 0o700)
    except OSError:
        pass
    tmp = "%s.tmp.%d.%s" % (path, os.getpid(), secrets.token_hex(6))
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(tmp, flags, 0o600)
    try:
        with os.fdopen(fd, "wb") as f:
            fd = None
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
    finally:
        if fd is not None:
            os.close(fd)
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass


def state_path(root, run_id):
    return os.path.join(root, *gp.RUN_STATE_DIR.split("/"),
                        "%s.json" % run_id)


def _linklike(path):
    return os.path.islink(path) or bool(
        getattr(os.path, "isjunction", lambda _p: False)(path))


def _file_revision(path):
    """Digest exact state bytes, or None when absent; never follow links."""
    if not os.path.lexists(path):
        return None
    if _linklike(path):
        raise OSError("run-state path is a symlink/junction")
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(path, flags)
    try:
        h = hashlib.sha256()
        with os.fdopen(fd, "rb") as f:
            fd = None
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    finally:
        if fd is not None:
            os.close(fd)


@contextlib.contextmanager
def state_lock(lock_path, timeout=15):
    """Cross-platform advisory interprocess lock for one run_id."""
    parent = os.path.dirname(lock_path) or "."
    deadline = time.monotonic() + timeout
    while True:
        try:
            os.makedirs(parent, mode=0o700, exist_ok=True)
            break
        except PermissionError:
            # Concurrent first creation of nested directories can briefly
            # surface as a sharing violation on Windows.
            if time.monotonic() >= deadline:
                raise TimeoutError("timed out creating run-state lock directory")
            time.sleep(0.05)
    flags = os.O_RDWR | os.O_CREAT
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    while True:
        if _linklike(lock_path):
            raise OSError("lock path is a symlink/junction")
        try:
            fd = os.open(lock_path, flags, 0o600)
            break
        except PermissionError:
            # Windows can briefly deny a concurrent open while another
            # process is creating the lock file. Treat only that specific
            # sharing/permission failure as contention, and remain bounded by
            # the same fail-closed timeout used for byte-range acquisition.
            if time.monotonic() >= deadline:
                raise TimeoutError("timed out opening run-state lock")
            time.sleep(0.05)
    try:
        handle = os.fdopen(fd, "r+b", buffering=0)
    except Exception:
        os.close(fd)
        raise
    try:
        # Inspect the already-open object. A pathname stat can itself hit a
        # Windows sharing violation during concurrent first creation.
        while True:
            try:
                if os.fstat(handle.fileno()).st_size == 0:
                    handle.write(b"0")
                    handle.flush()
                break
            except PermissionError:
                if time.monotonic() >= deadline:
                    raise TimeoutError("timed out initializing run-state lock")
                time.sleep(0.05)
        while True:
            try:
                handle.seek(0)
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX |
                                fcntl.LOCK_NB)
                break
            except (OSError, IOError):
                if time.monotonic() >= deadline:
                    raise TimeoutError("timed out waiting for run-state lock")
                time.sleep(0.05)
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    finally:
        handle.close()


def read_state(path, run_id, schema):
    """Load and strictly validate an existing state file.

    Return ``(state_dict, revision, None)`` when valid,
    ``(None, None, reason)`` for corrupt/foreign state (fail closed), or
    ``({}, None, None)`` when the file is absent.
    """
    if not os.path.lexists(path):
        return {}, None, None
    try:
        if _linklike(path):
            return None, None, "existing run-state is a symlink/junction"
        flags = os.O_RDONLY
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        fd = os.open(path, flags)
        with os.fdopen(fd, "rb") as f:
            raw = f.read()
        revision = hashlib.sha256(raw).hexdigest()
        state = json.loads(raw.decode("utf-8"))
    except Exception as e:
        return None, None, "existing run-state file is not valid/safe: %s" % e
    errs = gp.schema_validate(state, schema)
    if errs:
        return None, None, ("existing run-state file fails run-state-v1 "
                            "(fix or remove it; this tool never repairs "
                            "foreign state): " + "; ".join(errs[:5]))
    if state.get("run_id") != run_id:
        return None, None, ("existing run-state file carries run_id %r, not "
                            "%r; one file per run, named <run_id>.json"
                            % (state.get("run_id"), run_id))
    return state, revision, None


def check_root(root, require_clean):
    """Common git-state validation. Returns (head, None) or
    (None, reason)."""
    head = gp.git_head(root)
    if head is None:
        return None, "%r is not a git checkout — run-state binds to " \
                     "commits" % root
    tracked = gp.evidence_tracked_in_head(root)
    if tracked is None:
        return None, ("git tracking check FAILED — fail closed, never "
                      "assume the supported layout")
    if tracked:
        return None, ("runtime-state files (.solo/gate-evidence/ or "
                      ".solo/run-state/) are TRACKED in HEAD — unsupported "
                      "state; gitignore both generated runtime dirs")
    if require_clean:
        state = gp.repo_state(root)
        if state is None:
            return None, ("git repository-state check FAILED — a check "
                          "that cannot run never means clean (fail closed)")
        if state["dirty"]:
            lines = "\n".join("  %s" % p for p in state["dirty"][:20])
            return None, ("repository is not clean — %d path(s) outside "
                          "the generated runtime dirs (%s); a SHA recorded "
                          "for a tree that does not match it is "
                          "meaningless:\n%s"
                          % (len(state["dirty"]),
                             ", ".join(gp.UNTRACKED_RUNTIME_DIRS), lines))
    return head, None


def write_state(path, state, schema, expected_revision):
    errs = gp.schema_validate(state, schema)
    if errs:
        print("INTERNAL: produced run-state fails run-state-v1 — not "
              "writing it:")
        for e in errs[:10]:
            print("  %s" % e)
        return 2
    try:
        current_revision = _file_revision(path)
    except OSError as e:
        print("REFUSED: cannot safely re-read run-state before write: %s" % e)
        return 2
    if current_revision != expected_revision:
        print("REFUSED: run-state changed after it was read (revision %r -> "
              "%r); retry instead of overwriting a concurrent update"
              % (expected_revision, current_revision))
        return 2
    atomic_write_bytes(path, (json.dumps(state, indent=2, sort_keys=True)
                              + "\n").encode("utf-8"))
    return 0


def _operate_locked(args, root, schema):
    raw_path = state_path(root, args.run_id)
    path, err = gp.safe_run_state_path(root, raw_path, "run-state file")
    if err:
        print("REFUSED: %s" % err)
        return 2
    raw_lock = raw_path + ".lock"
    lock_path, err = gp.safe_run_state_path(root, raw_lock,
                                            "run-state lock")
    if err:
        print("REFUSED: %s" % err)
        return 2
    try:
        with state_lock(lock_path):
            # Re-resolve after lock acquisition: a competing process must not
            # swap a parent directory between validation and use.
            path2, err = gp.safe_run_state_path(root, raw_path,
                                                "run-state file (locked)")
            lock2, lock_err = gp.safe_run_state_path(
                root, raw_lock, "run-state lock (locked)")
            if err or lock_err or path2 != path or lock2 != lock_path:
                print("REFUSED: run-state path changed during lock acquisition")
                return 2
            state, revision, err = read_state(path, args.run_id, schema)
            if err:
                print("REFUSED: %s" % err)
                return 2

            if args.mode == "show":
                if not state:
                    print("REFUSED: no run-state file at %s" % path)
                    return 2
                print(json.dumps(state, indent=2, sort_keys=True))
                return 0

            if args.mode == "verify":
                head, err = check_root(root, require_clean=False)
                if err:
                    print("REFUSED: %s" % err)
                    return 2
                field = STAGE_TO_FIELD[args.stage]
                want = state.get(field) if state else None
                if not want:
                    print("VERIFY FAILED: %s is not recorded in %s; the %s "
                          "stage has not happened"
                          % (field, path, args.stage))
                    return 1
                if want != head:
                    print("VERIFY FAILED: HEAD %s != recorded %s %s; work at "
                          "another commit is invalid"
                          % (head[:12], field, want[:12]))
                    return 1
                print("VERIFY OK: HEAD == %s (%s)" % (field, head))
                return 0

            head, err = check_root(root, require_clean=True)
            if err:
                print("REFUSED: %s" % err)
                return 2

            if args.mode == "init":
                if state:
                    print("run-state already initialized: %s" % path)
                    return 0
                rc = write_state(path, {"schema": "run-state-v1",
                                        "run_id": args.run_id}, schema,
                                 revision)
                if rc == 0:
                    print("initialized run-state %s" % path)
                return rc

            field = STAGE_TO_FIELD[args.stage]
            if not state:
                state = {"schema": "run-state-v1", "run_id": args.run_id}
            idx = FIELDS.index(field)
            later = [f for f in FIELDS[idx + 1:] if state.get(f)]
            if later:
                print("REFUSED: cannot advance %s; later field(s) %s already "
                      "set; transitions are MONOTONIC and never rewind"
                      % (field, ", ".join(later)))
                return 2
            current = state.get(field)
            if current:
                if current == head:
                    print("no-op: %s already records HEAD %s"
                          % (field, head[:12]))
                    return 0
                if field == "final_sha":
                    print("REFUSED: final_sha is FROZEN at %s; it cannot be "
                          "rewritten to %s. Use a new run_id."
                          % (current[:12], head[:12]))
                    return 2
                print("REFUSED: %s is already %s and HEAD is %s; a set field "
                      "never changes" % (field, current[:12], head[:12]))
                return 2
            state[field] = head
            rc = write_state(path, state, schema, revision)
            if rc == 0:
                print("advanced %s: %s = %s (derived from git rev-parse HEAD)"
                      % (args.run_id, field, head))
            return rc
    except (OSError, TimeoutError) as e:
        print("REFUSED: cannot acquire/use run-state lock safely: %s" % e)
        return 2


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="update_run_state.py",
        usage="update_run_state.py --root DIR --run-id ID "
              "(init | advance {base,integration,final} | "
              "verify {base,integration,final} | show)")
    ap.add_argument("--root", required=True)
    ap.add_argument("--run-id", required=True)
    sub = ap.add_subparsers(dest="mode", required=True)
    sub.add_parser("init", help="create the state file (schema + run_id "
                                "only; idempotent)")
    adv = sub.add_parser("advance",
                         help="record `git rev-parse HEAD` (derived, never "
                              "supplied) into the named field — monotonic, "
                              "set-once")
    adv.add_argument("stage", choices=sorted(STAGE_TO_FIELD))
    ver = sub.add_parser("verify",
                         help="exit 0 iff the named field exists and "
                              "equals the CURRENT derived HEAD")
    ver.add_argument("stage", choices=sorted(STAGE_TO_FIELD))
    sub.add_parser("show", help="print the validated state JSON")
    args = ap.parse_args(argv)

    if not RUN_ID_RE.match(args.run_id):
        print("REFUSED: --run-id %r does not match %s"
              % (args.run_id, RUN_ID_RE.pattern))
        return 2
    root = os.path.abspath(args.root)
    if not os.path.isdir(root):
        print("REFUSED: --root %r is not a directory" % args.root)
        return 2
    try:
        schema = load_run_state_schema()
    except Exception as e:
        print("REFUSED: cannot load bundled run-state-v1 schema: %s" % e)
        return 2
    return _operate_locked(args, root, schema)


if __name__ == "__main__":
    sys.exit(main())
