#!/usr/bin/env python3
r"""record_evidence.py — produce a gate-evidence-v1 record. Stdlib only.

TWO canonical operations used by the shipped workflow. Their unsigned JSON
output is self-attested, and the recorder label is copyable; it does not prove
process origin:

  1. VERIFIED evidence (default): ACTUALLY EXECUTE a policy-validated
     category command, capture the REAL exit code, derive the source
     identity from git OBJECTS, hash the captured output, write the
     record + artifact atomically.
  2. CANONICAL N/A (--not-applicable, v1.0.17): mint a matrix-permitted
     not-applicable record. The tool — never the caller — derives the
     commit from git, validates the repository state, confirms the
     category/profile cell against the applicability matrix, REJECTS the
     seven mandatory categories, generates the timestamps, validates the
     completed record against the bundled schema, and writes atomically
     under .solo/gate-evidence/. There is NO flag to supply a commit,
     tree digest, exit code, or timestamp — caller-supplied source
     identity is exactly the failure mode this tool exists to prevent.

TRUST MODEL — SELF-ATTESTED LOCAL EVIDENCE, not cryptographic attestation.
This tool makes honest workflows mechanically checkable: it runs the
command itself, captures the REAL exit code, derives the source identity
from git OBJECTS, and hashes the captured output. It does not sign
anything; a trusted CI identity/signature is the upgrade path.

WHAT IT REFUSES (exit 2, no record written):
  * any command the shared per-category policy (plugins/gate/lib/
    gate_policy.py — full-argv validators, used by the checker too) does
    not accept. `git log`/`git ls-files` are evidence of NOTHING; --help,
    --version, dry-runs, list-only modes, unrelated paths, and arbitrary
    suffixes are rejected.
  * an unclean repository — FAIL-CLOSED three-way check (index vs HEAD
    including renames/copies with BOTH sides evaluated; working tree vs
    index; non-ignored untracked files) with ONLY the two generated
    runtime dirs (.solo/gate-evidence/, .solo/run-state/) exempt, and
    only on the working-tree side. There is NO --allow-dirty, a staged
    rename INTO the evidence dir is dirt, and a git failure is a refusal,
    never "clean". IGNORED-FILE POLICY: gitignored paths are exempt BY
    DESIGN — the .gitignore is tracked, reviewed content (see
    gate_policy.repo_state).
  * a repository the evidence command itself MUTATED: HEAD, the committed
    tree digest, and cleanliness are re-checked AFTER execution; any
    change refuses the record.
  * --out/--artifact paths that do not resolve INSIDE
    <root>/.solo/gate-evidence/ (absolute outside paths, '..', symlink
    escapes, and tracked files are refused) — validated BEFORE execution
    and RE-VALIDATED after it, immediately before the atomic writes, so a
    command that swaps the evidence directory for a symlink mid-run
    refuses the record.
  * an argv[0] that does not resolve through PATH / an absolute path to a
    real executable OUTSIDE the project (gate_policy.resolve_executable).
    The RESOLVED absolute executable is what gets executed and recorded
    (resolved_executable) — never the original bare token.
  * a gh-run record whose captured JSON does not name the derived HEAD
    with conclusion "success"; a version-endpoint response that does not
    contain the derived HEAD; a health-endpoint response without an
    explicit health contract (output bindings).
  * a `gh run view` without an explicit external `--gh-config-dir`
    containing a regular `hosts.yml`. Ambient GH_TOKEN/GITHUB_TOKEN and
    the normal user HOME remain unavailable. The recorder passes only the
    validated directory reference as GH_CONFIG_DIR; it never reads,
    copies, hashes, prints, or records the config contents/token.
  * a command whose complete process container cannot be terminated or
    whose stdout/stderr readers cannot drain to EOF. POSIX commands run in
    a new session/process group; Windows commands run in a kill-on-close
    Job Object and are released only after assignment. A timeout kills
    the container, not only the direct child. Surviving descendants or
    readers mean refusal and no artifact/record.
  * a root that is not a git checkout, and the UNSUPPORTED state where
    .solo/gate-evidence or .solo/run-state files are tracked in HEAD. The
    single supported workflow keeps both generated runtime directories
    untracked/gitignored, so writing records never changes the commit
    they describe.
  * an N/A request for a MANDATORY category (product, architecture,
    security, testing, deployment, monitoring, documentation), for a
    category/profile cell the matrix does not permit, without --profile,
    when --profile differs from the single canonical `Project profile:`
    field in the COMMITTED .solo/project.md at HEAD, with an arbitrary
    --profile-source, with an empty/trivial --reason, or without at least
    one --checked item describing what was actually inspected.

SOURCE IDENTITY (never caller-asserted): commit = `git rev-parse HEAD`;
tree_digest = SHA-256 over the COMMITTED tree at HEAD (path + blob sha
from `git ls-tree -r HEAD`, excluding ONLY the generated runtime paths
.solo/gate-evidence/** and .solo/run-state/**) — mutating working-tree
bytes cannot change it.

Usage (verified evidence):
    python3 record_evidence.py --category testing --project acme \
        --environment production --root . --reviewer "qa seat" \
        [--profile saas-application] [--run-id ftw-123] \
        [--expires-days 7] [--out PATH] [--artifact REL] \
        [--timeout 1800] [--gh-config-dir EXTERNAL_DIR] -- \
        python3 -m pytest -q

Usage (canonical N/A):
    python3 record_evidence.py --not-applicable --category seo \
        --project acme --environment production --root . \
        --reviewer "evidence finalizer" --profile api-service \
        --reason "API service exposes no public HTML pages to index" \
        --checked "router exposes JSON endpoints only" \
        [--profile-source .solo/project.md] [--run-id ftw-123] \
        [--expires-days 7] [--out PATH]

Exit codes: 0 = record written (command exited 0, or N/A minted);
1 = command ran and exited nonzero, record written (with the real code);
2 = refused (usage, policy, dirty tree, no git, tracked runtime state,
    mandatory/matrix-rejected N/A).
"""
import argparse
import datetime
import hashlib
import hmac
import json
import locale
import os
import re
import secrets
import signal
import stat
import subprocess
import sys
import tempfile
import threading
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(_HERE, "..", "..", "..", "lib")))
try:
    import gate_policy as gp
except ImportError:
    sys.exit("gate_policy.py not found — run from an intact gate plugin "
             "(plugins/gate/lib/gate_policy.py ships beside this skill)")


def atomic_write_bytes(path, data):
    """Atomic private-file write (0700 directory / 0600 file where honored)."""
    parent = os.path.dirname(path) or "."
    os.makedirs(parent, mode=0o700, exist_ok=True)
    try:
        os.chmod(parent, 0o700)
    except OSError:
        pass  # Windows ACLs do not map completely to POSIX mode bits
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


def _capture_as_utf8(data):
    """Return captured child output as well-formed UTF-8 bytes.

    ``subprocess.run(..., text=False)`` correctly preserves the command's
    bytes, but Windows children commonly encode redirected output with the
    active ANSI code page. Appending those bytes to our UTF-8 evidence
    header created a mixed-encoding artifact. Decode UTF-8 first, then the
    recorder's active stream/locale encodings (the encoding inherited by a
    normal child). If no declared encoding can decode the data, preserve
    every unknown byte as an ASCII ``\\xNN`` escape. The evidence artifact
    is therefore always UTF-8 and never silently drops captured bytes.
    """
    if data is None:
        return b""
    if isinstance(data, str):
        return data.encode("utf-8")
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        candidates = [getattr(sys.stdout, "encoding", None),
                      getattr(sys.stderr, "encoding", None),
                      locale.getpreferredencoding(False)]
        seen = set()
        for encoding in candidates:
            if not encoding:
                continue
            key = encoding.lower().replace("-", "").replace("_", "")
            if key in seen or key == "utf8":
                continue
            seen.add(key)
            try:
                return data.decode(encoding).encode("utf-8")
            except (LookupError, UnicodeDecodeError):
                continue
        # Fail safe for output whose encoding cannot be established. ASCII
        # backslash escapes are reversible at byte level and valid UTF-8.
        return data.decode("ascii", "backslashreplace").encode("utf-8")
    return data


# Output is evidence, not a safe place to archive credentials emitted by a
# test runner. These rules intentionally prefer over-redaction, but local
# redaction is best-effort: generated evidence must still be treated as
# sensitive and kept private/untracked.
_OUTPUT_SECRET_PATTERNS = (
    (re.compile(r"(?i)(authorization\s*:\s*(?:bearer|basic)\s+)[^\s]+"),
     r"\1[REDACTED]"),
    (re.compile(r"(?i)((?:password|passwd|pwd|api[_-]?key|access[_-]?token|"
                r"auth[_-]?token|oauth[_-]?token|client[_-]?secret)\s*[:=]\s*)"
                r"[^\s,;]+"),
     r"\1[REDACTED]"),
    (re.compile(r"(?i)((?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis|"
                r"amqp)://[^:/@\s]+:)[^@\s]+(@)"),
     r"\1[REDACTED]\2"),
    (re.compile(r"\b(?:AKIA[0-9A-Z]{16}|gh[pousr]_[0-9A-Za-z]{36,}|"
                r"sk_live_[0-9A-Za-z]{20,}|sk-[A-Za-z0-9]{20,}|"
                r"xox[baprs]-[0-9A-Za-z-]{10,})\b"),
     "[REDACTED-TOKEN]"),
)


def _redact_capture(data, sensitive_values=()):
    text = _capture_as_utf8(data).decode("utf-8")
    # Configuration references are intentionally absent from artifacts. The
    # selected gh profile path is not a credential, but it can expose a local
    # username/layout and an invoked CLI could echo it in diagnostics.
    for value in sensitive_values:
        if value:
            variants = {value, os.path.normpath(value),
                        value.replace("\\", "/"),
                        json.dumps(value)[1:-1]}
            flags = re.IGNORECASE if os.name == "nt" else 0
            for variant in sorted(variants, key=len, reverse=True):
                if variant:
                    text = re.sub(re.escape(variant),
                                  "[REDACTED-CONFIG-DIR]", text,
                                  flags=flags)
    for pattern, replacement in _OUTPUT_SECRET_PATTERNS:
        text = pattern.sub(replacement, text)
    return text.encode("utf-8")


class _BoundedStream(object):
    """Drain a child pipe continuously while retaining a bounded prefix."""
    def __init__(self, limit):
        self.limit = limit
        self.data = bytearray()
        self.truncated = False
        self.error = None

    def drain(self, pipe):
        try:
            while True:
                chunk = pipe.read(65536)
                if not chunk:
                    break
                room = self.limit - len(self.data)
                if room > 0:
                    self.data.extend(chunk[:room])
                if len(chunk) > max(room, 0):
                    self.truncated = True
        except BaseException as exc:
            # The caller treats any reader failure as an incomplete capture
            # and refuses evidence. Do not let a daemon-thread traceback be
            # the only signal that capture integrity was lost.
            self.error = "%s: %s" % (type(exc).__name__, exc)
        finally:
            pipe.close()


class _ProcessContainmentError(RuntimeError):
    """The command could not be placed in a killable process container."""


if os.name == "nt":
    import ctypes
    from ctypes import wintypes

    class _IO_COUNTERS(ctypes.Structure):
        _fields_ = [
            ("ReadOperationCount", ctypes.c_ulonglong),
            ("WriteOperationCount", ctypes.c_ulonglong),
            ("OtherOperationCount", ctypes.c_ulonglong),
            ("ReadTransferCount", ctypes.c_ulonglong),
            ("WriteTransferCount", ctypes.c_ulonglong),
            ("OtherTransferCount", ctypes.c_ulonglong),
        ]

    class _JOB_BASIC_LIMIT(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_longlong),
            ("PerJobUserTimeLimit", ctypes.c_longlong),
            ("LimitFlags", wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        ]

    class _JOB_EXTENDED_LIMIT(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", _JOB_BASIC_LIMIT),
            ("IoInfo", _IO_COUNTERS),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    class _JOB_BASIC_ACCOUNTING(ctypes.Structure):
        _fields_ = [
            ("TotalUserTime", ctypes.c_longlong),
            ("TotalKernelTime", ctypes.c_longlong),
            ("ThisPeriodTotalUserTime", ctypes.c_longlong),
            ("ThisPeriodTotalKernelTime", ctypes.c_longlong),
            ("TotalPageFaultCount", wintypes.DWORD),
            ("TotalProcesses", wintypes.DWORD),
            ("ActiveProcesses", wintypes.DWORD),
            ("TotalTerminatedProcesses", wintypes.DWORD),
        ]

    class _WindowsJob(object):
        """Kill-on-close Windows Job Object containing the command tree.

        The command itself is released by a tiny Python bootstrap only after
        that bootstrap has been assigned to the job. This closes the normal
        Popen->AssignProcess race: every subsequently created target process
        and ordinary descendant inherits membership in the job.
        """
        _EXTENDED_LIMIT_INFO = 9
        _BASIC_ACCOUNTING_INFO = 1
        _KILL_ON_JOB_CLOSE = 0x00002000

        def __init__(self):
            self._k32 = ctypes.WinDLL("kernel32", use_last_error=True)
            self._k32.CreateJobObjectW.argtypes = [ctypes.c_void_p,
                                                   wintypes.LPCWSTR]
            self._k32.CreateJobObjectW.restype = wintypes.HANDLE
            self._k32.SetInformationJobObject.argtypes = [
                wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p,
                wintypes.DWORD]
            self._k32.SetInformationJobObject.restype = wintypes.BOOL
            self._k32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE,
                                                           wintypes.HANDLE]
            self._k32.AssignProcessToJobObject.restype = wintypes.BOOL
            self._k32.TerminateJobObject.argtypes = [wintypes.HANDLE,
                                                     wintypes.UINT]
            self._k32.TerminateJobObject.restype = wintypes.BOOL
            self._k32.QueryInformationJobObject.argtypes = [
                wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p,
                wintypes.DWORD, ctypes.c_void_p]
            self._k32.QueryInformationJobObject.restype = wintypes.BOOL
            self._k32.CloseHandle.argtypes = [wintypes.HANDLE]
            self._k32.CloseHandle.restype = wintypes.BOOL
            self.handle = self._k32.CreateJobObjectW(None, None)
            if not self.handle:
                self._fail("CreateJobObjectW")
            info = _JOB_EXTENDED_LIMIT()
            info.BasicLimitInformation.LimitFlags = self._KILL_ON_JOB_CLOSE
            if not self._k32.SetInformationJobObject(
                    self.handle, self._EXTENDED_LIMIT_INFO,
                    ctypes.byref(info), ctypes.sizeof(info)):
                err = ctypes.get_last_error()
                self.close()
                raise _ProcessContainmentError(
                    "SetInformationJobObject failed (Windows error %d)" % err)

        @staticmethod
        def _fail(operation):
            raise _ProcessContainmentError(
                "%s failed (Windows error %d)" %
                (operation, ctypes.get_last_error()))

        def assign(self, proc):
            if not self._k32.AssignProcessToJobObject(
                    self.handle, wintypes.HANDLE(int(proc._handle))):
                self._fail("AssignProcessToJobObject")

        def terminate(self, code=124):
            if self.handle and not self._k32.TerminateJobObject(
                    self.handle, int(code)):
                return False
            return True

        def active(self):
            info = _JOB_BASIC_ACCOUNTING()
            if not self._k32.QueryInformationJobObject(
                    self.handle, self._BASIC_ACCOUNTING_INFO,
                    ctypes.byref(info), ctypes.sizeof(info), None):
                self._fail("QueryInformationJobObject")
            return int(info.ActiveProcesses)

        def close(self):
            if getattr(self, "handle", None):
                self._k32.CloseHandle(self.handle)
                self.handle = None


_WIN_BOOTSTRAP = (
    "import os,subprocess,sys,time\n"
    "gate=sys.argv[1]; deadline=time.monotonic()+30\n"
    "while not os.path.exists(gate):\n"
    "  if time.monotonic()>=deadline: sys.exit(125)\n"
    "  time.sleep(0.01)\n"
    "try: os.unlink(gate)\n"
    "except OSError: pass\n"
    "try:\n"
    "  child=subprocess.Popen(sys.argv[2:],stdin=subprocess.DEVNULL)\n"
    "except BaseException as exc:\n"
    "  print('command launch failed: %s' % exc,file=sys.stderr); sys.exit(127)\n"
    "sys.exit(child.wait())\n"
)


def _join_readers(threads, timeout):
    deadline = time.monotonic() + timeout
    for thread in threads:
        remaining = max(0.0, deadline - time.monotonic())
        thread.join(remaining)
    return not any(thread.is_alive() for thread in threads)


def _posix_group_active(pgid):
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        # A group we created but can no longer signal is still active and is
        # a containment failure, never evidence of successful cleanup.
        return True
    return True


def _wait_tree_gone(proc, job, timeout):
    deadline = time.monotonic() + timeout
    while True:
        try:
            active = job.active() > 0 if job is not None \
                else _posix_group_active(proc.pid)
        except _ProcessContainmentError:
            return False
        if not active:
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(0.05)


def _terminate_tree(proc, job):
    """Terminate then force-kill the complete contained command tree."""
    if job is not None:
        job.terminate(124)
    else:
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        if not _wait_tree_gone(proc, None, 2.0):
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        try:
            proc.kill()
        except OSError:
            pass
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            return False
    return _wait_tree_gone(proc, job, 5.0)


def _run_bounded(argv, cwd, env, timeout, max_output_bytes):
    """Run without a shell in a killable tree, draining streams to EOF.

    Returns the historical six capture fields plus ``cleanup_ok`` and a safe
    diagnostic. A timeout may be recorded only after the complete process
    tree is gone and both reader threads reached EOF. A command that returns
    while descendants still run is terminated and marked unsafe so the caller
    refuses to write evidence.
    """
    job = None
    release_path = None
    popen_argv = list(argv)
    popen_kw = {}
    if os.name == "nt":
        job = _WindowsJob()
        release_path = os.path.join(
            env.get("HOME", tempfile.gettempdir()),
            ".solo-gate-release-%s" % secrets.token_hex(12))
        popen_argv = [sys.executable, "-c", _WIN_BOOTSTRAP,
                      release_path] + popen_argv
        popen_kw["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        popen_kw["start_new_session"] = True
    try:
        proc = subprocess.Popen(
            popen_argv, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, **popen_kw)
        if job is not None:
            try:
                job.assign(proc)
            except _ProcessContainmentError:
                try:
                    proc.kill()
                    proc.wait(timeout=5)
                finally:
                    job.close()
                raise
            # Release the bootstrap only after its process belongs to the
            # kill-on-close job, so the real command cannot win an assignment
            # race and spawn an uncontained descendant.
            with open(release_path, "xb"):
                pass
    except BaseException:
        if job is not None:
            job.close()
        raise
    out = _BoundedStream(max_output_bytes)
    err = _BoundedStream(max_output_bytes)
    threads = [threading.Thread(target=out.drain, args=(proc.stdout,)),
               threading.Thread(target=err.drain, args=(proc.stderr,))]
    for thread in threads:
        thread.daemon = True
        thread.start()
    timed_out = False
    cleanup_ok = True
    cleanup_reason = None
    try:
        exit_code = proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        tree_gone = _terminate_tree(proc, job)
        exit_code = 124
        readers_done = _join_readers(threads, 5.0)
        cleanup_ok = tree_gone and readers_done
        if not cleanup_ok:
            cleanup_reason = ("timed-out command tree did not terminate "
                              "completely or capture readers did not reach "
                              "EOF")
    else:
        # A completed foreground process must leave no background descendants
        # and close every inherited capture handle. Briefly allow normal pipe
        # EOF propagation, then fail closed and terminate anything remaining.
        readers_done = _join_readers(threads, 1.0)
        tree_gone = _wait_tree_gone(proc, job, 0.0)
        if not tree_gone or not readers_done:
            _terminate_tree(proc, job)
            _join_readers(threads, 5.0)
            cleanup_ok = False
            cleanup_reason = ("command returned while descendant processes "
                              "or capture-pipe readers were still active")
    if out.error or err.error:
        cleanup_ok = False
        cleanup_reason = "capture reader failed before a complete EOF drain"
    if job is not None:
        job.close()
    if release_path:
        try:
            os.unlink(release_path)
        except FileNotFoundError:
            pass
    return (exit_code, bytes(out.data), bytes(err.data), out.truncated,
            err.truncated, timed_out, cleanup_ok, cleanup_reason)


_SAFE_ENV_KEYS = {
    "SYSTEMROOT", "WINDIR", "COMSPEC", "PATHEXT", "SYSTEMDRIVE",
    "TEMP", "TMP", "TMPDIR", "LANG", "LC_ALL", "LC_CTYPE", "TZ",
    "NUMBER_OF_PROCESSORS", "PROCESSOR_ARCHITECTURE",
}


def _sanitized_path(root):
    kept = []
    seen = set()
    for entry in os.environ.get("PATH", "").split(os.pathsep):
        entry = entry.strip().strip('"')
        if not entry:
            continue
        real = os.path.realpath(entry)
        if gp._inside(real, root):
            continue
        key = os.path.normcase(real)
        if key not in seen:
            kept.append(real)
            seen.add(key)
    return os.pathsep.join(kept)


def _child_environment(root, private_home, allow_network,
                       gh_config_dir=None):
    """Construct a small allowlisted environment; never inherit tokens.

    ``gh`` authentication is the sole credential exception: the caller may
    supply an already-existing external GitHub CLI config directory. Only its
    path is handed to ``gh`` via its documented ``GH_CONFIG_DIR`` discovery
    variable; token variables and config contents are never read or copied by
    the recorder.
    """
    env = {k: v for k, v in os.environ.items() if k.upper() in _SAFE_ENV_KEYS}
    path = _sanitized_path(root)
    if path:
        env["PATH"] = path
    env.update({
        "HOME": private_home,
        "USERPROFILE": private_home,
        "XDG_CONFIG_HOME": os.path.join(private_home, "config"),
        "XDG_CACHE_HOME": os.path.join(private_home, "cache"),
        "PYTHONNOUSERSITE": "1",
        "PYTHONUTF8": "1",
        "PIP_NO_INPUT": "1",
        "NO_COLOR": "1",
    })
    if gh_config_dir:
        env["GH_CONFIG_DIR"] = gh_config_dir
    if not allow_network:
        # Defence in depth for common toolchains. This is not claimed as an
        # OS network sandbox; the CLI still requires explicit approval for
        # known-network command families and docs require external isolation
        # for untrusted repositories.
        env.update({"NPM_CONFIG_OFFLINE": "true", "PIP_NO_INDEX": "1",
                    "CARGO_NET_OFFLINE": "true", "GOTOOLCHAIN": "local"})
    return env


def _link_or_reparse(path):
    try:
        st = os.lstat(path)
    except OSError:
        return True
    if stat.S_ISLNK(st.st_mode):
        return True
    attrs = getattr(st, "st_file_attributes", 0)
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return bool(attrs & reparse)


def _gh_config_profile(candidate, root):
    """Validate an explicit external gh config and return (path, id, error).

    The opaque id binds preview/confirmation to path + non-secret filesystem
    metadata. The file is deliberately never opened, parsed, copied, hashed,
    or printed: GitHub CLI remains the only process that discovers any token.
    """
    if not candidate:
        return None, None, (
            "gh run view requires --gh-config-dir pointing to an existing "
            "external GitHub CLI profile; ambient GH_TOKEN/GITHUB_TOKEN and "
            "the normal user HOME are intentionally unavailable")
    expanded = os.path.abspath(os.path.expanduser(candidate))
    if _link_or_reparse(expanded):
        return None, None, ("the supplied --gh-config-dir must be a real "
                            "directory, not a symlink/junction/reparse point")
    real = os.path.realpath(expanded)
    if not os.path.isdir(real):
        return None, None, ("the supplied --gh-config-dir is not an existing "
                            "directory")
    if gp._inside(real, os.path.realpath(root)):
        return None, None, ("--gh-config-dir must be outside the project; "
                            "repository-controlled credential profiles are "
                            "refused")
    hosts = os.path.join(real, "hosts.yml")
    if _link_or_reparse(hosts) or not os.path.isfile(hosts):
        return None, None, ("the supplied --gh-config-dir must contain a "
                            "regular, non-linked hosts.yml")
    try:
        dst = os.stat(real)
        hst = os.stat(hosts)
    except OSError:
        return None, None, ("could not stat the supplied GitHub CLI profile "
                            "without following an unsafe link")
    if not stat.S_ISDIR(dst.st_mode) or not stat.S_ISREG(hst.st_mode):
        return None, None, ("the supplied GitHub CLI profile/hosts.yml has "
                            "an unsupported file type")
    if os.name != "nt" and hasattr(os, "getuid"):
        if dst.st_uid != os.getuid() or hst.st_uid != os.getuid():
            return None, None, ("the supplied GitHub CLI profile must be "
                                "owned by the current OS user")
        if stat.S_IMODE(dst.st_mode) & 0o022:
            return None, None, ("the supplied --gh-config-dir is writable "
                                "by another user/group; restrict it first")
        if stat.S_IMODE(hst.st_mode) & 0o077:
            return None, None, ("GitHub CLI hosts.yml must not grant group/"
                                "other permissions; use mode 0600")
    metadata = {
        "dir": os.path.normcase(real),
        "dir_dev": dst.st_dev, "dir_ino": dst.st_ino,
        "hosts_dev": hst.st_dev, "hosts_ino": hst.st_ino,
        "hosts_size": hst.st_size,
        "hosts_mtime_ns": getattr(hst, "st_mtime_ns",
                                   int(hst.st_mtime * 1_000_000_000)),
    }
    opaque_id = hashlib.sha256(json.dumps(
        metadata, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")).hexdigest()
    return real, opaque_id, None


def _needs_network(command_id, argv):
    if any(gp._URL_RE.match(t) for t in argv[1:]):
        return True
    exe = gp._norm_exe(argv[0])
    return exe in {"gh", "pip-audit", "govulncheck"} or command_id in {
        "npm audit", "cargo audit", "check_email_dns.py", "alembic current",
        "npx --no-install prisma migrate status",
        "npx --no-install supabase db lint",
    }


def _preview_token(category, command_id, exec_argv, head, digest, timeout,
                   max_output_bytes, allow_network, credential_profile_id):
    payload = json.dumps({
        "category": category, "command_id": command_id,
        "exec_argv": exec_argv, "head": head, "tree_digest": digest,
        "timeout": timeout, "max_output_bytes": max_output_bytes,
        "allow_network": bool(allow_network),
        "credential_profile_id": credential_profile_id,
    }, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _check_repo_identity(root):
    """Independently read and validate HEAD + repository state. Returns
    (head, digest, None) or (None, None, refusal_message). Shared by both
    canonical operations — the caller NEVER supplies any of it."""
    head = gp.git_head(root)
    if head is None:
        return None, None, ("%r is not a git checkout — evidence must "
                            "bind to a commit" % root)
    tracked = gp.evidence_tracked_in_head(root)
    if tracked is None:
        return None, None, ("git tracking check FAILED — a check that "
                            "cannot run never means clean (fail closed)")
    if tracked:
        return None, None, (
            "runtime-state files (.solo/gate-evidence/ or .solo/run-state/) "
            "are TRACKED in HEAD — the only supported workflow keeps BOTH "
            "generated runtime directories untracked/gitignored (add "
            "'.solo/gate-evidence/' and '.solo/run-state/' to .gitignore "
            "and remove the tracked copies)")
    state = gp.repo_state(root)
    if state is None:
        return None, None, ("git repository-state check FAILED — a check "
                            "that cannot run never means clean (fail "
                            "closed)")
    if state["dirty"]:
        lines = "\n".join("  %s" % p for p in state["dirty"][:20])
        return None, None, (
            "repository is not clean — %d staged/unstaged/untracked "
            "path(s) outside the generated runtime dirs (%s). Commit or "
            "remove them first (there is no --allow-dirty; gitignored "
            "paths are exempt by documented policy):\n%s"
            % (len(state["dirty"]), ", ".join(gp.UNTRACKED_RUNTIME_DIRS),
               lines))
    digest = gp.committed_tree_digest(root)
    if digest is None:
        return None, None, "could not read the committed tree at HEAD"
    return head, digest, None


def record_not_applicable(args):
    """CANONICAL N/A OPERATION (v1.0.17). Mints a matrix-permitted
    not-applicable record: derives the commit itself, validates the
    repository state, confirms the matrix cell, rejects mandatory
    categories, generates timestamps, validates against the bundled
    schema, and writes atomically under .solo/gate-evidence/. Never
    accepts a caller-supplied commit, tree digest, exit code, or
    timestamp — no such flags exist."""
    root = os.path.abspath(args.root)
    if not os.path.isdir(root):
        print("REFUSED: --root %r is not a directory" % args.root)
        return 2
    if args.command and [t for t in args.command if t != "--"]:
        print("REFUSED: --not-applicable takes no command — an N/A record "
              "asserts non-applicability, it never executes anything")
        return 2
    # ---- matrix cell: mandatory categories are NEVER N/A -------------------
    if args.category in gp.MANDATORY:
        print("REFUSED: category %r is MANDATORY and may never be N/A "
              "(mandatory: %s)" % (args.category, sorted(gp.MANDATORY)))
        return 2
    if args.profile is None:
        print("REFUSED: --not-applicable requires --profile (the matrix "
              "cell is <category>:<profile>)")
        return 2
    allowed = gp.NA_ALLOWED.get(args.category, set())
    if args.profile not in allowed:
        print("REFUSED: the applicability matrix does not permit N/A for "
              "category %r under profile %r (permitted profiles: %s)"
              % (args.category, args.profile, sorted(allowed) or "none"))
        return 2
    # ---- substantive reason + inspection evidence ---------------------------
    reason = (args.reason or "").strip()
    if len(reason) < 20 or len(reason.split()) < 4:
        print("REFUSED: --reason must be substantive (>= 20 characters "
              "and >= 4 words); got %r" % (args.reason,))
        return 2
    checked = [c.strip() for c in (args.checked or []) if c.strip()]
    if not checked:
        print("REFUSED: at least one --checked item is required — name "
              "what was actually inspected to conclude non-applicability")
        return 2
    if not args.reviewer.strip():
        print("REFUSED: --reviewer must be non-empty")
        return 2
    profile_source = (args.profile_source or "").strip()
    if profile_source != gp.PROJECT_PROFILE_SOURCE:
        print("REFUSED: --profile-source must be exactly %r; the N/A "
              "profile is bound to that committed file, not a caller-"
              "selected source" % gp.PROJECT_PROFILE_SOURCE)
        return 2
    # ---- source identity: derived from git objects, never asserted ---------
    head, _digest, err = _check_repo_identity(root)
    if err:
        print("REFUSED: %s" % err)
        return 2
    committed_profile, profile_err = gp.committed_project_profile(root)
    if profile_err:
        print("REFUSED: committed project profile unavailable: %s" %
              profile_err)
        return 2
    if args.profile != committed_profile:
        print("REFUSED: --profile %r does not match %r recorded in the "
              "committed %s at HEAD" %
              (args.profile, committed_profile, gp.PROJECT_PROFILE_SOURCE))
        return 2
    # ---- output path must resolve inside the evidence dir ------------------
    out_default = os.path.join(root, gp.EVIDENCE_DIR,
                               "%s.json" % args.category)
    out_path, err = gp.safe_evidence_path(root, args.out or out_default,
                                          "--out")
    if err:
        print("REFUSED: %s" % err)
        return 2
    # ---- the record: timestamps generated HERE, never supplied -------------
    now = datetime.datetime.now(datetime.timezone.utc)
    rec = {
        "schema": "solo-suite/gate-evidence-v1",
        "status": "not-applicable",
        "recorder": "record_evidence.py/v1",
        "project": args.project,
        "commit": head,
        "environment": args.environment,
        "timestamp": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "category": args.category,
        "profile": args.profile,
        "reason": reason,
        "applicability": {
            "matrix": "%s:%s" % (args.category, args.profile),
            "profile_source": gp.PROJECT_PROFILE_SOURCE,
            "checked": checked,
        },
        "reviewer": args.reviewer,
        "expires": (now + datetime.timedelta(days=args.expires_days)
                    ).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    if args.run_id:
        rec["run_id"] = args.run_id
    # the record must satisfy the bundled schema BEFORE it is written
    errs = gp.schema_validate(rec)
    if errs:
        print("INTERNAL: produced N/A record fails the bundled schema — "
              "not writing it:")
        for e in errs[:10]:
            print("  %s" % e)
        return 2
    atomic_write_bytes(out_path,
                       (json.dumps(rec, indent=2) + "\n").encode("utf-8"))
    print("recorded %s N/A evidence (matrix %s): commit=%s -> %s"
          % (args.category, rec["applicability"]["matrix"], head[:12],
             out_path))
    return 0


def bounded_expires_days(value):
    days = int(value)
    if not 1 <= days <= 7:
        raise argparse.ArgumentTypeError("must be between 1 and 7 days")
    return days


def main(argv=None):
    ap = argparse.ArgumentParser(
        usage="record_evidence.py --category CAT --project P --environment "
              "E --root DIR --reviewer NAME [options] -- COMMAND [ARGS...]\n"
              "       record_evidence.py --not-applicable --category CAT "
              "--project P --environment E --root DIR --reviewer NAME "
              "--profile PROFILE --reason TEXT --checked ITEM [options]")
    ap.add_argument("--category", required=True,
                    choices=sorted(gp.CATEGORIES))
    ap.add_argument("--project", required=True)
    ap.add_argument("--environment", required=True)
    ap.add_argument("--root", required=True)
    ap.add_argument("--reviewer", required=True)
    ap.add_argument("--profile", default=None,
                    choices=sorted(gp.RECOGNIZED_PROFILES))
    ap.add_argument("--run-id", default=None)
    ap.add_argument("--expires-days", type=bounded_expires_days, default=7,
                    help="record validity (1-7 days; cannot exceed gate policy)")
    ap.add_argument("--out", default=None,
                    help="record path (default: <root>/.solo/gate-evidence/"
                         "<category>.json)")
    ap.add_argument("--artifact", default=None,
                    help="captured-output path RELATIVE to root (default: "
                         ".solo/gate-evidence/artifacts/<category>.log)")
    ap.add_argument("--timeout", type=int, default=1800)
    ap.add_argument("--max-output-bytes", type=int, default=2_000_000,
                    help="maximum retained bytes for EACH stdout/stderr "
                         "stream (4096..10000000); excess is drained and "
                         "marked truncated, never buffered without bound")
    execution = ap.add_mutually_exclusive_group()
    execution.add_argument(
        "--preview", action="store_true",
        help="validate and print the exact execution plan plus its bound "
             "confirmation token; execute nothing")
    execution.add_argument(
        "--confirm-execution", metavar="PREVIEW_TOKEN",
        help="execute only when this SHA-256 token exactly matches the "
             "current preview (HEAD, tree, argv and limits)")
    ap.add_argument(
        "--allow-network", action="store_true",
        help="explicitly approve network use for a known-network command; "
             "must be present during preview and confirmed execution")
    ap.add_argument(
        "--gh-config-dir", default=None,
        help="for gh run view only: explicit external GitHub CLI config "
             "directory containing hosts.yml. The recorder passes only the "
             "path as GH_CONFIG_DIR; it never reads/copies/logs config "
             "contents or inherits GH_TOKEN/GITHUB_TOKEN")
    # ---- canonical N/A operation (v1.0.17) ---------------------------------
    ap.add_argument("--not-applicable", action="store_true",
                    help="mint a matrix-permitted N/A record instead of "
                         "executing a command (the tool derives the commit "
                         "and timestamps itself; mandatory categories are "
                         "refused)")
    ap.add_argument("--reason", default=None,
                    help="(--not-applicable) substantive justification, "
                         ">= 20 chars and >= 4 words")
    ap.add_argument("--checked", action="append", default=None,
                    help="(--not-applicable, repeatable) what was actually "
                         "inspected to conclude non-applicability")
    ap.add_argument("--profile-source", default=gp.PROJECT_PROFILE_SOURCE,
                    help="(--not-applicable) compatibility flag; must be "
                         "exactly .solo/project.md, whose committed "
                         "Project profile: field is authoritative")
    ap.add_argument("command", nargs=argparse.REMAINDER,
                    help="-- followed by the exact command argv")
    args = ap.parse_args(argv)

    if args.not_applicable:
        if (args.preview or args.confirm_execution or args.allow_network or
                args.gh_config_dir):
            print("REFUSED: execution preview/confirmation/network/credential "
                  "flags are not valid with --not-applicable (it executes "
                  "nothing)")
            return 2
        return record_not_applicable(args)
    for flag, val in (("--reason", args.reason),
                      ("--checked", args.checked)):
        if val:
            print("REFUSED: %s is only valid with --not-applicable" % flag)
            return 2

    cmd = list(args.command)
    if cmd and cmd[0] == "--":
        cmd = cmd[1:]
    if not cmd:
        print("REFUSED: no command given (pass it after --)")
        return 2
    if not args.reviewer.strip():
        print("REFUSED: --reviewer must be non-empty")
        return 2
    if not 1 <= args.timeout <= 3600:
        print("REFUSED: --timeout must be 1..3600 seconds")
        return 2
    if not 4096 <= args.max_output_bytes <= 10_000_000:
        print("REFUSED: --max-output-bytes must be 4096..10000000")
        return 2
    root = os.path.abspath(args.root)
    if not os.path.isdir(root):
        print("REFUSED: --root %r is not a directory" % args.root)
        return 2

    # ---- command policy: full-argv validation, shared with the checker ----
    ok, why = gp.validate_command(args.category, cmd, root)
    if not ok:
        print("REFUSED by the %r command policy: %s" % (args.category, why))
        for rule in gp.describe_policy(args.category):
            if rule:
                print("  policy: %s" % rule.strip().splitlines()[0])
        return 2
    command_id = why
    gh_config_dir = None
    credential_profile_id = None
    if command_id == gp.GH_RUN_COMMAND_ID:
        gh_config_dir, credential_profile_id, err = _gh_config_profile(
            args.gh_config_dir, root)
        if err:
            print("REFUSED: GitHub CLI credential profile: %s" % err)
            return 2
    elif args.gh_config_dir:
        print("REFUSED: --gh-config-dir is valid only for the policy-bound "
              "gh run view deployment command")
        return 2
    # ---- canonical executable identity: resolve, then EXECUTE the resolved
    # absolute path (never the original bare token) and RECORD it ----------
    resolved_exe, err = gp.resolve_executable(cmd[0], root)
    if err:
        print("REFUSED: executable identity: %s" % err)
        return 2

    # ---- source identity: derived from git objects, never asserted --------
    head, digest, err = _check_repo_identity(root)
    if err:
        print("REFUSED: %s" % err)
        return 2

    # ---- output paths must resolve inside the evidence dir ----------------
    rel_artifact = args.artifact or \
        "%s/artifacts/%s.log" % (gp.EVIDENCE_DIR, args.category)
    artifact_path, err = gp.safe_evidence_path(root, rel_artifact,
                                               "--artifact")
    if err:
        print("REFUSED: %s" % err)
        return 2
    out_default = os.path.join(root, gp.EVIDENCE_DIR,
                               "%s.json" % args.category)
    out_path, err = gp.safe_evidence_path(root, args.out or out_default,
                                          "--out")
    if err:
        print("REFUSED: %s" % err)
        return 2

    # ---- explicit preview -> manual confirmation ---------------------------
    exec_argv = [resolved_exe] + cmd[1:]
    needs_network = _needs_network(command_id, cmd)
    token = _preview_token(args.category, command_id, exec_argv, head, digest,
                           args.timeout, args.max_output_bytes,
                           args.allow_network, credential_profile_id)
    print("EXECUTION PREVIEW (nothing has run):")
    print("  category: %s" % args.category)
    print("  cwd: %s" % root)
    print("  argv: %s" % json.dumps(exec_argv))
    print("  timeout: %ds" % args.timeout)
    print("  retained output cap: %d bytes per stream" %
          args.max_output_bytes)
    print("  network required/approved: %s/%s" %
          ("yes" if needs_network else "no",
           "yes" if args.allow_network else "no"))
    print("  environment: allowlisted OS/runtime keys only; private temporary "
          "HOME; ambient tokens, credentials and proxy variables removed")
    if credential_profile_id:
        print("  gh auth: explicit external GH_CONFIG_DIR profile %s "
              "(path and contents omitted; ambient token variables refused)"
              % credential_profile_id[:12])
    print("  preview token: %s" % token)
    if needs_network and not args.allow_network:
        print("REFUSED: this command needs network access. Re-run --preview "
              "with --allow-network, review that changed plan, then use its "
              "new token only after explicit human approval.")
        return 2
    if args.preview:
        print("PREVIEW ONLY: after explicit human approval, replace --preview "
              "with --confirm-execution %s%s" %
              (token, " --allow-network" if args.allow_network else ""))
        return 0
    if not args.confirm_execution:
        print("REFUSED: commands are manual-only. Run once with --preview, "
              "obtain explicit human approval, then pass the displayed "
              "--confirm-execution token.")
        return 2
    if not hmac.compare_digest(args.confirm_execution, token):
        print("REFUSED: --confirm-execution token does not match this exact "
              "HEAD/tree/argv/timeout/output/network plan. Preview again.")
        return 2
    if needs_network:
        safe, reason = gp.check_http_targets_safe(cmd)
        if not safe:
            print("REFUSED by the outbound URL guard: %s" % reason)
            return 2

    # ---- execute resolved executable with bounded streams and scrubbed env --
    started = time.time()
    stdout_only = b""
    try:
        with tempfile.TemporaryDirectory(prefix="solo-gate-home-") as home:
            child_env = _child_environment(
                root, home, args.allow_network,
                gh_config_dir=gh_config_dir)
            (exit_code, raw_stdout, raw_stderr, stdout_truncated,
             stderr_truncated, timed_out, cleanup_ok,
             cleanup_reason) = _run_bounded(
                 exec_argv, root, child_env, args.timeout,
                 args.max_output_bytes)
        if not cleanup_ok:
            print("REFUSED: process-tree/capture cleanup failed — %s; no "
                  "artifact or evidence record written" % cleanup_reason)
            return 2
        if gh_config_dir:
            _profile2, profile_id2, profile_err2 = _gh_config_profile(
                args.gh_config_dir, root)
            if profile_err2 or profile_id2 != credential_profile_id:
                print("REFUSED: GitHub CLI credential profile changed or "
                      "became unsafe during execution; no record written")
                return 2
        stdout_only = _capture_as_utf8(raw_stdout)
        sensitive_refs = (gh_config_dir,) if gh_config_dir else ()
        stderr_bytes = _redact_capture(raw_stderr, sensitive_refs)
        out_bytes = _redact_capture(raw_stdout, sensitive_refs)
        if stderr_bytes:
            out_bytes += b"\n--- stderr ---\n" + stderr_bytes
        if stdout_truncated:
            out_bytes += (b"\n--- STDOUT TRUNCATED at %d bytes ---\n" %
                          args.max_output_bytes)
        if stderr_truncated:
            out_bytes += (b"\n--- STDERR TRUNCATED at %d bytes ---\n" %
                          args.max_output_bytes)
        if timed_out:
            out_bytes += b"\n--- TIMEOUT after %ds ---\n" % args.timeout
    except FileNotFoundError as e:
        print("REFUSED: command not found: %s" % e)
        return 2
    except _ProcessContainmentError as e:
        print("REFUSED: could not establish/verify process-tree containment: "
              "%s; no evidence command was released" % e)
        return 2
    duration = round(time.time() - started, 3)

    # ---- RE-CHECK the repository AFTER execution ---------------------------
    # The command itself could have mutated tracked files or moved HEAD;
    # a record must describe the SAME state before and after.
    head2 = gp.git_head(root)
    state2 = gp.repo_state(root)
    digest2 = gp.committed_tree_digest(root)
    if head2 is None or state2 is None or digest2 is None:
        print("REFUSED: post-execution git re-check FAILED — cannot prove "
              "the command left the repository intact (fail closed)")
        return 2
    if head2 != head or digest2 != digest:
        print("REFUSED: the evidence command MOVED HEAD or changed the "
              "committed tree (%s -> %s) — no record written"
              % (head[:12], head2[:12]))
        return 2
    if state2["dirty"]:
        print("REFUSED: the evidence command DIRTIED the repository — no "
              "record written:")
        for p in state2["dirty"][:20]:
            print("  %s" % p)
        return 2

    # ---- output binding (gh run -> HEAD + success; version-endpoint ->
    # HEAD in the response; health-endpoint -> explicit health contract) ----
    binder = gp.OUTPUT_BINDINGS.get(command_id)
    if binder is not None:
        if stdout_truncated:
            print("REFUSED: bound stdout exceeded the capture limit; an "
                  "incomplete response cannot prove the output contract")
            return 2
        bound, breason = binder(stdout_only, head, root)
        if not bound:
            print("REFUSED: output binding failed — %s" % breason)
            return 2

    # ---- REVALIDATE --out/--artifact AFTER execution, immediately before
    # the atomic writes: the command ran arbitrary code and could have
    # swapped the evidence directory (or a parent) for a symlink between
    # the initial validation and now. The paths are re-resolved from the
    # ORIGINAL candidates; any escape refuses the record. ------------------
    artifact_path, err = gp.safe_evidence_path(root, rel_artifact,
                                               "--artifact (post-exec)")
    if err:
        print("REFUSED: %s" % err)
        return 2
    out_path, err = gp.safe_evidence_path(root, args.out or out_default,
                                          "--out (post-exec)")
    if err:
        print("REFUSED: %s" % err)
        return 2

    # ---- artifact + record, atomically -------------------------------------
    rel_artifact = os.path.relpath(artifact_path, root).replace(os.sep, "/")
    header = ("# record_evidence.py capture (self-attested local evidence)\n"
              "# capture_encoding: utf-8; secret-like values redacted\n"
              "# category: %s\n# argv: %s\n# command_id: %s\n"
              "# resolved_executable: %s\n"
              "# commit: %s\n# tree_digest: %s\n# exit_code: %d\n\n"
              % (args.category, json.dumps(cmd), command_id, resolved_exe,
                 head, digest, exit_code)).encode("utf-8")
    atomic_write_bytes(artifact_path, header + out_bytes)

    now = datetime.datetime.now(datetime.timezone.utc)
    rec = {
        "schema": "solo-suite/gate-evidence-v1",
        "status": "verified",
        "recorder": "record_evidence.py/v1",
        "project": args.project,
        "commit": head,
        "tree_digest": digest,
        "environment": args.environment,
        "timestamp": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "category": args.category,
        "command": " ".join(cmd),
        "command_id": command_id,
        "command_argv": cmd,
        "resolved_executable": resolved_exe,
        "exit_code": exit_code,
        "duration_seconds": duration,
        "artifact": rel_artifact.replace(os.sep, "/"),
        "artifact_sha256": gp.sha256_file(artifact_path),
        "reviewer": args.reviewer,
        "expires": (now + datetime.timedelta(days=args.expires_days)
                    ).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    if args.run_id:
        rec["run_id"] = args.run_id
    # the record must satisfy the bundled schema BEFORE it is written
    errs = gp.schema_validate(rec)
    if errs:
        print("INTERNAL: produced record fails the bundled schema — not "
              "writing it:")
        for e in errs[:10]:
            print("  %s" % e)
        return 2
    atomic_write_bytes(out_path,
                       (json.dumps(rec, indent=2) + "\n").encode("utf-8"))

    print("recorded %s evidence (%s): exit_code=%d commit=%s tree=%s… -> %s"
          % (args.category, command_id, exit_code, head[:12], digest[:12],
             out_path))
    if exit_code != 0:
        print("NOTE: the command FAILED — the record preserves the real "
              "exit code and check_evidence.py will reject it, by design.")
    return 0 if exit_code == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
