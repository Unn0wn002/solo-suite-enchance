#!/usr/bin/env python3
r"""scan_secrets.py — scan a codebase for likely hardcoded secrets:
API keys, private keys, tokens, passwords, and cloud credentials.

Stdlib only. Usage:
    python3 scan_secrets.py /path/to/repo-or-single-file
        [--max-bytes 2000000] [--json] [--git-history]

SAFE OUTPUT CONTRACT: this scanner never prints or retains the matched
line or the complete secret value — not in stdout, stderr, JSON, or
exceptions. Each finding contains ONLY:
  - relative file path
  - line number
  - rule name
  - a safely redacted preview (short prefix + masked middle + short suffix)
  - a KEYED fingerprint of the matched value: HMAC-SHA256 under a key that
    is either supplied via the SECRETSCAN_HMAC_KEY environment variable
    (stable fingerprints for rotation tracking across runs) or generated
    fresh per run (fingerprints then only deduplicate WITHIN the run).
    An unkeyed hash of a low-entropy value like a password is a
    dictionary-attackable oracle — this scanner never emits one.

COVERAGE CONTRACT: every candidate file gets an explicit outcome —
  inspected | skipped_too_large | unreadable | suppressed | binary |
  unsupported_encoding
Files skipped by extension policy (SKIP_EXT — known-binary formats) and
the scanner's own file are excluded before counting. The scan is COMPLETE
only when nothing was skipped_too_large, unreadable, binary, or
unsupported_encoding AND at least one file was inspected. `--max-bytes 1`
therefore reports every file as skipped and exits 3 — it can never
masquerade as a clean scan — and an extensionless binary or undecodable
file makes coverage INCOMPLETE rather than silently clean.

LONG LINES ARE SCANNED, NEVER SKIPPED: lines over 2,000 characters are
scanned in bounded overlapping chunks (4096-char windows, 512-char overlap)
so a secret buried in minified output is still found — with the same
redaction guarantees. The count appears as coverage.long_lines_chunked.

ENCODINGS: UTF-8 is decoded strictly (no errors='ignore' masking);
UTF-16 files with a BOM are decoded and scanned; anything else that
cannot be decoded is outcome unsupported_encoding (coverage incomplete).

Findings are HEURISTIC. Every hit must be verified by a human — test
fixtures, examples, and placeholders will match.

Exit codes:
  0 = complete scan, no findings
  1 = complete scan with findings (verify each)
  2 = usage error (bad --max-bytes, missing root, root neither a
      directory nor a regular file)
  3 = INCOMPLETE scan, with or without findings (files skipped as too large
      or unreadable, a bounded Git subprocess failed, or zero files inspected)

INCOMPLETE PRECEDENCE: exit 3 takes precedence over exit 1 when findings and
incomplete coverage occur together. This preserves the findings in output
without allowing partial coverage to masquerade as a complete findings-only
scan. CI must reject both 1 and 3, but should report them differently.

Repository-controlled suppression pragmas are deliberately NOT honored: a
committed comment must not be able to hide a committed credential from CI.
The scanner skips only its own file automatically so its rule definitions do
not self-report. Generated gate evidence and textual lock/source-map/minified
files remain in scope; they can contain credentials too.

LOCAL GIT HISTORY (optional): ``--git-history`` reads local committed Git
objects only (no fetch/network and no checkout), under explicit commit, file,
per-blob, total-byte and finding caps. Historical findings intentionally emit
ONLY commit/path/line/rule/keyed-fingerprint: no preview, source line or secret
value. Hitting a scope cap or unreadable/binary/unsupported blob makes history
coverage incomplete and exit 3, so a partial history scan never looks clean.
Every Git subprocess streams through hard stdout/stderr byte caps; timeout or
overflow terminates its whole process tree and discards partial/raw output.
"""
import argparse
import hashlib
import hmac
import json
import os
import re
import secrets as _secrets
import signal
import subprocess
import sys
import threading
import time

# Directories and files never worth scanning
SKIP_DIRS = {".git", "node_modules", "vendor", "dist", "build", ".next",
             "__pycache__", ".venv", "venv", "coverage", ".cache"}
SKIP_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico",
            ".pdf", ".zip", ".gz", ".tar", ".mp4", ".woff", ".woff2",
            ".ttf", ".eot",
            ".docx", ".xlsx", ".pptx", ".jar", ".exe", ".dll", ".so",
            ".dylib", ".pyc", ".class", ".wasm"}

# (label, compiled regex). Ordered specific -> generic. Where a named group
# "secret" exists, only that group is fingerprinted/redacted; otherwise the
# whole match is. These literals are rule definitions, not secrets.
PATTERNS = [
    ("AWS Access Key ID", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("AWS Secret Access Key", re.compile(r"(?i)aws.{0,20}?['\"](?P<secret>[0-9a-zA-Z/+]{40})['\"]")),
    ("Private key block", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----")),
    ("GitHub token", re.compile(r"gh[pousr]_[0-9A-Za-z]{36,}")),
    ("Slack token", re.compile(r"xox[baprs]-[0-9A-Za-z-]{10,}")),
    ("Google API key", re.compile(r"AIza[0-9A-Za-z_\-]{35}")),
    ("Stripe live key", re.compile(r"sk_live_[0-9a-zA-Z]{20,}")),
    ("Xendit secret key", re.compile(r"xnd_(?:development|production)_[0-9A-Za-z]{20,}")),
    ("Midtrans server key", re.compile(r"(?:SB-)?Mid-server-[0-9A-Za-z_\-]{16,}")),
    ("SendGrid key", re.compile(r"SG\.[0-9A-Za-z_\-]{20,}\.[0-9A-Za-z_\-]{20,}")),
    ("Resend key", re.compile(r"\bre_[0-9A-Za-z]{16,}")),
    ("Supabase access token", re.compile(r"sbp_[0-9a-f]{40}")),
    ("Supabase secret key", re.compile(r"sb_secret_[0-9A-Za-z_\-]{20,}")),
    ("Vercel token assignment", re.compile(r"(?i)vercel.{0,15}['\"](?P<secret>[0-9A-Za-z]{24})['\"]")),
    ("Cloudflare API token assignment", re.compile(r"(?i)cloudflare.{0,20}['\"](?P<secret>[0-9A-Za-z_\-]{40})['\"]")),
    ("OpenAI key", re.compile(r"sk-[A-Za-z0-9]{20,}")),
    ("JWT", re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}")),
    ("Generic API key assignment", re.compile(
        r"(?i)(?:api[_-]?key|apikey|access[_-]?token|auth[_-]?token|client[_-]?secret)"
        r"\s*[:=]\s*['\"](?P<secret>[0-9a-zA-Z_\-]{16,})['\"]")),
    ("Hardcoded password assignment", re.compile(
        r"(?i)(?:password|passwd|pwd)\s*[:=]\s*['\"](?P<secret>[^'\"]{6,})['\"]")),
    ("Connection string with creds", re.compile(
        r"(?i)(?:postgres|postgresql|mysql|mongodb(?:\+srv)?|redis|amqp)://"
        r"[^:@\s'\"]+:(?P<secret>[^@\s'\"]+)@")),
]

# Values that look like placeholders — noted, not suppressed
PLACEHOLDER = re.compile(
    r"(?i)(your[_-]?(?:key|token|secret|password)|placeholder|<[^>]+>|"
    r"change[_-]?me|explicitly[_-]?redacted|x{8,}|0{12,})")

IGNORE_LINE = re.compile(r"secretscan:ignore(?!-file)")
IGNORE_FILE = "secretscan:ignore-file"

MAX_LINE_LEN = 2000
CHUNK = 4096       # window for long-line scanning
OVERLAP = 512      # longer than any secret token the rules can match

OUTCOMES = ("inspected", "skipped_too_large", "unreadable", "suppressed",
            "binary", "unsupported_encoding", "unsafe_symlink")

# Git is never allowed to produce unbounded output.  stdout is retained only
# up to the caller's explicit cap; stderr is never retained because it could
# contain repository-controlled paths or secret material.  The command tuple
# is not repository-configurable; tests patch it in-process with a defensive
# fake to exercise hostile subprocess behavior.
GIT_COMMAND = ("git",)
GIT_STDERR_CAP = 64 * 1024
GIT_PIPE_CHUNK = 64 * 1024
GIT_TREE_MIN_CAP = 64 * 1024
GIT_TREE_ENTRY_BUDGET = 1024


def redact(value):
    """Short prefix + masked middle + short suffix; not reconstructable."""
    v = str(value)
    if len(v) <= 8:
        return "%s (len %d)" % ("*" * len(v), len(v))
    return "%s%s%s (len %d)" % (v[:4], "*" * 6, v[-2:], len(v))


def make_fingerprinter():
    """Return (fingerprint_fn, key_source). HMAC-SHA256 keyed either by
    SECRETSCAN_HMAC_KEY (stable across runs) or a fresh per-run key —
    NEVER an unkeyed hash, which would let anyone dictionary-attack
    low-entropy values like passwords offline."""
    env = os.environ.get("SECRETSCAN_HMAC_KEY")
    if env:
        key, source = env.encode("utf-8"), "env:SECRETSCAN_HMAC_KEY"
    else:
        key, source = _secrets.token_bytes(32), "ephemeral (per-run)"

    def fingerprint(value):
        mac = hmac.new(key, str(value).encode("utf-8", "replace"),
                       hashlib.sha256)
        return "hmac-sha256:" + mac.hexdigest()
    return fingerprint, source


def _finding(rel, lineno, label, secret, fingerprint=None):
    # ``fingerprint`` is always supplied by the current scanner.  The optional
    # legacy form is retained for integrations that imported this helper before
    # keyed fingerprints became part of the public output contract.
    if fingerprint is None:
        legacy_digest = make_fingerprinter()[0](secret).split(":", 1)[-1]
        legacy_redacted = "<redacted>" if len(str(secret)) <= 8 else (
            f"{str(secret)[:4]}...{str(secret)[-4:]}"
        )
        return {
            "path": rel,
            "line": lineno,
            "rule": label,
            "redacted": legacy_redacted,
            "fingerprint": legacy_digest,
        }
    return {
        "path": rel,
        "line": lineno,
        "rule": label,
        "preview": redact(secret),
        "fingerprint": fingerprint(secret),
        "placeholder_hint": bool(PLACEHOLDER.search(secret)),
    }


def _scan_short_line(rel, lineno, line, fingerprint, findings):
    for label, rx in PATTERNS:
        m = rx.search(line)
        if m:
            secret = m.groupdict().get("secret") or m.group(0)
            findings.append(_finding(rel, lineno, label, secret, fingerprint))
            return  # one label per line is enough


def _scan_long_line(rel, lineno, line, fingerprint, findings):
    """Scan an over-long line in bounded overlapping windows. At most one
    finding per rule per line; a secret straddling a window boundary is
    covered by the OVERLAP. Nothing unredacted ever leaves this function."""
    seen_rules = set()
    step = CHUNK - OVERLAP
    start = 0
    while start < len(line):
        seg = line[start:start + CHUNK]
        for label, rx in PATTERNS:
            if label in seen_rules:
                continue
            m = rx.search(seg)
            if m:
                secret = m.groupdict().get("secret") or m.group(0)
                findings.append(_finding(rel, lineno, label, secret,
                                         fingerprint))
                seen_rules.add(label)
        if start + CHUNK >= len(line):
            break
        start += step


def _decode_lines(path, max_bytes):
    """Yield decoded text for scanning. Returns (kind, text|None):
    kind is 'utf-8', 'utf-16', 'binary', or 'unsupported_encoding'."""
    with open(path, "rb") as bf:
        data = bf.read(max_bytes + 1)
    if data[:2] in (b"\xff\xfe", b"\xfe\xff"):
        try:
            return "utf-16", data.decode("utf-16")
        except UnicodeDecodeError:
            return "unsupported_encoding", None
    if b"\0" in data[:8192]:
        return "binary", None
    try:
        return "utf-8", data.decode("utf-8")   # STRICT — no errors='ignore'
    except UnicodeDecodeError:
        return "unsupported_encoding", None


def _scan_file_with_outcome(path, root, max_bytes, fingerprint):
    """Scan ONE file. Returns (outcome, findings, long_lines_chunked).
    outcome is always one of OUTCOMES — a file can never silently produce
    no outcome. Over-long lines are SCANNED in overlapping chunks, never
    skipped; undecodable content is an explicit incomplete-coverage
    outcome, never treated as clean."""
    rel = os.path.relpath(path, root).replace(os.sep, "/") \
        if os.path.isdir(root) else os.path.basename(path)
    findings = []
    long_lines = 0
    try:
        is_junction = getattr(os.path, "isjunction", lambda _p: False)
        if os.path.islink(path) or is_junction(path):
            return "unsafe_symlink", [], 0
        base = os.path.realpath(root if os.path.isdir(root)
                                else os.path.dirname(root))
        actual = os.path.realpath(path)
        if not (actual == base or actual.startswith(base + os.sep)):
            return "unsafe_symlink", [], 0
        if os.path.getsize(path) > max_bytes:
            return "skipped_too_large", [], 0
        kind, text = _decode_lines(path, max_bytes)
        if kind in ("binary", "unsupported_encoding"):
            return kind, [], 0
        for lineno, line in enumerate(text.splitlines(), 1):
            if len(line) > MAX_LINE_LEN:
                long_lines += 1
                _scan_long_line(rel, lineno, line, fingerprint, findings)
            else:
                _scan_short_line(rel, lineno, line, fingerprint, findings)
    except OSError:
        return "unreadable", [], long_lines
    return "inspected", findings, long_lines


def positive_int(value):
    """Parse a positive integer for legacy callers and argparse adapters."""
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise argparse.ArgumentTypeError("must be a positive integer") from exc
    if number < 1:
        raise argparse.ArgumentTypeError("must be positive")
    return number


def scan_file(path, root, max_bytes, fingerprint=None):
    """Compatibility wrapper around the coverage-aware scanner.

    New callers receive the full ``(outcome, findings, long_lines)`` tuple by
    supplying a fingerprinter.  Older callers that omit it receive only the
    findings list, matching the v1.0.12 helper seam.
    """
    if fingerprint is None:
        legacy_fp = make_fingerprinter()[0]
        _outcome, findings, _long_lines = _scan_file_with_outcome(
            path, root, max_bytes, legacy_fp)
        return findings
    return _scan_file_with_outcome(path, root, max_bytes, fingerprint)


def scan_tree(root, max_bytes):
    """Legacy tree API returning ``(scanned_count, findings)``."""
    fingerprint = make_fingerprinter()[0]
    self_path = os.path.abspath(__file__)
    scanned = 0
    findings = []
    for path in iter_candidates(root, self_path):
        outcome, hits, _long_lines = _scan_file_with_outcome(
            path, root, max_bytes, fingerprint)
        if outcome == "inspected":
            scanned += 1
        findings.extend(hits)
    return scanned, findings


def iter_candidates(root, self_path):
    """Yield candidate files under root (or root itself when it is a
    file), after extension policy and self-exclusion."""
    is_junction = getattr(os.path, "isjunction", lambda _p: False)
    if os.path.isfile(root) or os.path.islink(root) or is_junction(root):
        name = os.path.basename(root)
        if not any(name.endswith(e) for e in SKIP_EXT) \
                and os.path.abspath(root) != self_path:
            yield root
        return
    for dirpath, dirnames, filenames in os.walk(root):
        kept = []
        for dirname in sorted(dirnames):
            if dirname in SKIP_DIRS:
                continue
            candidate = os.path.join(dirpath, dirname)
            if os.path.islink(candidate) or is_junction(candidate):
                # Yield it so coverage records the refused traversal instead
                # of silently dropping a directory link from os.walk.
                yield candidate
                continue
            kept.append(dirname)
        dirnames[:] = kept
        for name in sorted(filenames):
            full = os.path.join(dirpath, name)
            if any(name.endswith(e) for e in SKIP_EXT):
                continue
            if os.path.abspath(full) == self_path:
                continue  # never self-report our own rule definitions
            yield full


def _windows_job_for(proc):
    """Put *proc* in a kill-on-close Windows Job Object when possible.

    A Job Object is the only reliable stdlib-level way to terminate children
    after their immediate parent exits.  Failure is safe: the caller falls
    back to ``taskkill /T`` and then ``Popen.kill``.  No Windows error text is
    returned or printed because it may include repository-controlled data.
    """
    if os.name != "nt":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        class IoCounters(ctypes.Structure):
            _fields_ = [
                ("ReadOperationCount", ctypes.c_ulonglong),
                ("WriteOperationCount", ctypes.c_ulonglong),
                ("OtherOperationCount", ctypes.c_ulonglong),
                ("ReadTransferCount", ctypes.c_ulonglong),
                ("WriteTransferCount", ctypes.c_ulonglong),
                ("OtherTransferCount", ctypes.c_ulonglong),
            ]

        class BasicLimitInformation(ctypes.Structure):
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

        class ExtendedLimitInformation(ctypes.Structure):
            _fields_ = [
                ("BasicLimitInformation", BasicLimitInformation),
                ("IoInfo", IoCounters),
                ("ProcessMemoryLimit", ctypes.c_size_t),
                ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t),
                ("PeakJobMemoryUsed", ctypes.c_size_t),
            ]

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateJobObjectW.argtypes = (
            ctypes.c_void_p, wintypes.LPCWSTR)
        kernel32.CreateJobObjectW.restype = wintypes.HANDLE
        kernel32.SetInformationJobObject.argtypes = (
            wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD)
        kernel32.SetInformationJobObject.restype = wintypes.BOOL
        kernel32.AssignProcessToJobObject.argtypes = (
            wintypes.HANDLE, wintypes.HANDLE)
        kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
        kernel32.TerminateJobObject.argtypes = (
            wintypes.HANDLE, wintypes.UINT)
        kernel32.TerminateJobObject.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
        kernel32.CloseHandle.restype = wintypes.BOOL
        job = kernel32.CreateJobObjectW(None, None)
        if not job:
            return None
        info = ExtendedLimitInformation()
        info.BasicLimitInformation.LimitFlags = 0x00002000  # KILL_ON_CLOSE
        if not kernel32.SetInformationJobObject(
                job, 9, ctypes.byref(info), ctypes.sizeof(info)):
            kernel32.CloseHandle(job)
            return None
        process_handle = wintypes.HANDLE(int(proc._handle))
        if not kernel32.AssignProcessToJobObject(job, process_handle):
            kernel32.CloseHandle(job)
            return None
        return kernel32, job
    except (AttributeError, OSError, TypeError, ValueError):
        return None


def _close_windows_job(job):
    if job is not None:
        kernel32, handle = job
        try:
            kernel32.CloseHandle(handle)
        except (AttributeError, OSError, TypeError, ValueError):
            pass


def _terminate_process_tree(proc, windows_job):
    """Force-stop the process and all descendants without capturing output."""
    if os.name == "nt":
        if windows_job is not None:
            kernel32, handle = windows_job
            try:
                if kernel32.TerminateJobObject(handle, 1):
                    return
            except (AttributeError, OSError, TypeError, ValueError):
                pass
        # Fallback for hosts that disallow nested Job Objects.
        try:
            subprocess.run(
                ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL, timeout=2, check=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except (OSError, subprocess.TimeoutExpired):
            pass
        try:
            proc.kill()
        except OSError:
            pass
        return
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except (OSError, ProcessLookupError):
        try:
            proc.kill()
        except OSError:
            pass


def _read_bounded_pipe(pipe, cap, retained, limit_hit, read_failed, done):
    """Drain one pipe while retaining at most *cap* bytes.

    ``retained`` is ``None`` for stderr, so stderr bytes are counted and
    discarded immediately.  One extra byte is read only to detect overflow;
    it is never retained or returned.
    """
    remaining = cap
    try:
        while True:
            request = min(GIT_PIPE_CHUNK, remaining + 1)
            chunk = pipe.read(request)
            if not chunk:
                break
            keep = min(len(chunk), remaining)
            if retained is not None and keep:
                retained.extend(chunk[:keep])
            remaining -= keep
            if len(chunk) > keep:
                limit_hit.set()
                break
    except (OSError, ValueError):
        read_failed.set()
    finally:
        done.set()


def _git_bounded(repo, args, output_cap, timeout=30,
                 stderr_cap=GIT_STDERR_CAP):
    """Run local Git with streaming hard caps on stdout and stderr.

    Return ``(return_code, stdout, truncated_or_failed)``.  stdout is returned
    only after a fully bounded, successful read; timeout, stream failure, or
    either cap being exceeded returns an empty byte string.  stderr is always
    discarded and never appears in exceptions or reports.  The process is
    started in an isolated POSIX session or Windows process group and the
    entire tree is force-terminated on a cap or timeout.
    """
    if output_cap < 1 or stderr_cap < 1 or timeout <= 0:
        return 125, b"", True
    popen_kwargs = {
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "bufsize": 0,
    }
    if os.name == "nt":
        popen_kwargs["creationflags"] = (
            getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) |
            getattr(subprocess, "CREATE_NO_WINDOW", 0))
    else:
        popen_kwargs["start_new_session"] = True
    try:
        proc = subprocess.Popen(
            list(GIT_COMMAND) + ["-C", repo] + list(args), **popen_kwargs)
    except OSError:
        return 127, b"", False

    windows_job = _windows_job_for(proc)
    stdout_data = bytearray()
    limit_hit = threading.Event()
    read_failed = threading.Event()
    stdout_done = threading.Event()
    stderr_done = threading.Event()
    readers = [
        threading.Thread(target=_read_bounded_pipe,
                         args=(proc.stdout, output_cap, stdout_data,
                               limit_hit, read_failed, stdout_done),
                         name="secretscan-git-stdout", daemon=True),
        threading.Thread(target=_read_bounded_pipe,
                         args=(proc.stderr, stderr_cap, None,
                               limit_hit, read_failed, stderr_done),
                         name="secretscan-git-stderr", daemon=True),
    ]
    for reader in readers:
        reader.start()

    deadline = time.monotonic() + timeout
    timed_out = False
    while True:
        if limit_hit.is_set() or read_failed.is_set():
            break
        if (proc.poll() is not None and stdout_done.is_set() and
                stderr_done.is_set()):
            break
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            timed_out = True
            break
        limit_hit.wait(min(0.02, remaining))

    abnormal = timed_out or limit_hit.is_set() or read_failed.is_set()
    if abnormal:
        _terminate_process_tree(proc, windows_job)
    try:
        rc = proc.wait(timeout=2)
    except subprocess.TimeoutExpired:
        _terminate_process_tree(proc, windows_job)
        try:
            rc = proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            rc = 124

    for reader in readers:
        reader.join(timeout=1)
    readers_alive = any(reader.is_alive() for reader in readers)
    if readers_alive:
        # The writer tree should already be dead.  Closing our pipe handles is
        # a final bounded unblock; no partial data is returned after this path.
        for pipe in (proc.stdout, proc.stderr):
            try:
                pipe.close()
            except (OSError, ValueError):
                pass
        for reader in readers:
            reader.join(timeout=0.5)
    # Popen does not close PIPE handles after wait(); close both on every path
    # so repeated per-blob history reads cannot leak descriptors/handles.
    for pipe in (proc.stdout, proc.stderr):
        try:
            pipe.close()
        except (OSError, ValueError):
            pass
    _close_windows_job(windows_job)

    failed = abnormal or readers_alive or limit_hit.is_set() or \
        read_failed.is_set()
    if timed_out:
        return 124, b"", True
    if failed:
        return rc, b"", True
    return rc, bytes(stdout_data), False


def _history_line_hits(text, fingerprint):
    """Return only (line, rule, keyed fingerprint), never source/preview."""
    found = []
    for lineno, line in enumerate(text.splitlines(), 1):
        seen = set()
        windows = [line]
        if len(line) > MAX_LINE_LEN:
            windows = []
            start, step = 0, CHUNK - OVERLAP
            while start < len(line):
                windows.append(line[start:start + CHUNK])
                if start + CHUNK >= len(line):
                    break
                start += step
        for window in windows:
            for label, rx in PATTERNS:
                if label in seen:
                    continue
                match = rx.search(window)
                if match:
                    secret = (match.groupdict().get("secret") or
                              match.group(0))
                    found.append((lineno, label, fingerprint(secret)))
                    seen.add(label)
            if len(line) <= MAX_LINE_LEN and seen:
                break  # preserve one-label-per-short-line behavior
    return found


def _decode_blob(data):
    if data[:2] in (b"\xff\xfe", b"\xfe\xff"):
        try:
            return "utf-16", data.decode("utf-16")
        except UnicodeDecodeError:
            return "unsupported_encoding", None
    if b"\0" in data[:8192]:
        return "binary", None
    try:
        return "utf-8", data.decode("utf-8")
    except UnicodeDecodeError:
        return "unsupported_encoding", None


def scan_git_history(root, fingerprint, max_commits, max_files,
                     max_blob_bytes, max_total_bytes, max_findings):
    """Bounded local-object history scan; never checks out or contacts Git."""
    result = {
        "enabled": True,
        "complete": True,
        "commits_scanned": 0,
        "files_considered": 0,
        "blobs_scanned": 0,
        "bytes_scanned": 0,
        "cache_hits": 0,
        "binary": 0,
        "unsupported_encoding": 0,
        "skipped_too_large": 0,
        "incomplete_reasons": [],
        "limits": {"commits": max_commits, "files": max_files,
                   "blob_bytes": max_blob_bytes,
                   "total_bytes": max_total_bytes,
                   "findings": max_findings},
        "findings": [],
    }

    start = root if os.path.isdir(root) else os.path.dirname(root)
    rc, repo_raw, truncated = _git_bounded(
        start, ["rev-parse", "--show-toplevel"], 32768)
    if rc != 0 or truncated:
        result["complete"] = False
        result["incomplete_reasons"].append(
            "target is not inside a readable local Git worktree")
        return result
    repo = os.path.realpath(repo_raw.decode("utf-8", "replace").strip())
    target = os.path.realpath(root)
    if not (target == repo or target.startswith(repo + os.sep)):
        result["complete"] = False
        result["incomplete_reasons"].append("target resolves outside Git root")
        return result
    rel_target = os.path.relpath(target, repo).replace(os.sep, "/")
    if rel_target == ".":
        rel_target = None

    rev_cap = (max_commits + 1) * 64
    rc, rev_raw, truncated = _git_bounded(
        repo, ["rev-list", "--max-count=%d" % (max_commits + 1), "HEAD"],
        rev_cap)
    if rc != 0 or truncated:
        result["complete"] = False
        result["incomplete_reasons"].append("could not enumerate commits")
        return result
    commits = [x for x in rev_raw.decode("ascii", "replace").splitlines()
               if re.match(r"^[0-9a-f]{40}$", x)]
    if len(commits) > max_commits:
        commits = commits[:max_commits]
        result["complete"] = False
        result["incomplete_reasons"].append(
            "commit cap reached; older commits were not scanned")

    cache = {}  # blob oid -> safe tuples only; never raw blob/secret values
    stop = False
    self_suffix = ("plugins/site-doctor/skills/security-review/scripts/"
                   "scan_secrets.py")
    for commit in commits:
        if stop:
            break
        result["commits_scanned"] += 1
        ls_args = ["ls-tree", "-r", "-z", "--long", commit]
        if rel_target:
            ls_args += ["--", rel_target]
        tree_cap = min(64 * 1024 * 1024,
                       max(GIT_TREE_MIN_CAP,
                           (max_files + 1) * GIT_TREE_ENTRY_BUDGET))
        rc, tree_raw, truncated = _git_bounded(repo, ls_args, tree_cap)
        if rc != 0 or truncated:
            result["complete"] = False
            result["incomplete_reasons"].append(
                "tree listing failed or exceeded its bounded output cap")
            break
        for entry in tree_raw.split(b"\0"):
            if not entry:
                continue
            try:
                meta, path_raw = entry.split(b"\t", 1)
                parts = meta.split()
                if len(parts) != 4 or parts[1] != b"blob":
                    continue
                oid = parts[2].decode("ascii")
                size = int(parts[3])
                path = path_raw.decode("utf-8", "surrogateescape")
            except (ValueError, UnicodeError):
                result["complete"] = False
                result["incomplete_reasons"].append(
                    "unparseable bounded git tree entry")
                stop = True
                break
            if path.replace("\\", "/").endswith(self_suffix):
                continue
            name = os.path.basename(path)
            if any(name.endswith(ext) for ext in SKIP_EXT):
                continue
            if result["files_considered"] >= max_files:
                result["complete"] = False
                result["incomplete_reasons"].append(
                    "file cap reached; remaining historical paths skipped")
                stop = True
                break
            result["files_considered"] += 1
            if size > max_blob_bytes:
                result["skipped_too_large"] += 1
                result["complete"] = False
                continue
            if oid in cache:
                safe_hits, kind = cache[oid]
                result["cache_hits"] += 1
            else:
                if result["bytes_scanned"] + size > max_total_bytes:
                    result["complete"] = False
                    result["incomplete_reasons"].append(
                        "total byte cap reached; remaining blobs skipped")
                    stop = True
                    break
                rc, blob, truncated = _git_bounded(
                    repo, ["cat-file", "blob", oid], max_blob_bytes)
                if rc != 0 or truncated or len(blob) != size:
                    result["complete"] = False
                    result["incomplete_reasons"].append(
                        "blob read failed or exceeded declared/capped size")
                    stop = True
                    break
                result["bytes_scanned"] += len(blob)
                result["blobs_scanned"] += 1
                kind, text_value = _decode_blob(blob)
                safe_hits = [] if text_value is None else \
                    _history_line_hits(text_value, fingerprint)
                cache[oid] = (safe_hits, kind)
                del blob, text_value
            if kind == "binary":
                result["binary"] += 1
                result["complete"] = False
                continue
            if kind == "unsupported_encoding":
                result["unsupported_encoding"] += 1
                result["complete"] = False
                continue
            for lineno, rule, keyed_fingerprint in safe_hits:
                if len(result["findings"]) >= max_findings:
                    result["complete"] = False
                    result["incomplete_reasons"].append(
                        "finding cap reached; remaining history skipped")
                    stop = True
                    break
                result["findings"].append({
                    "commit": commit,
                    "path": path,
                    "line": lineno,
                    "rule": rule,
                    "fingerprint": keyed_fingerprint,
                })
            if stop:
                break
    # Stable order and de-duplicated generic reason messages.
    result["findings"].sort(key=lambda x: (x["commit"], x["path"],
                                            x["line"], x["rule"]))
    if result["skipped_too_large"]:
        result["incomplete_reasons"].append(
            "%d historical blob occurrence(s) exceeded the per-blob byte cap"
            % result["skipped_too_large"])
    if result["binary"]:
        result["incomplete_reasons"].append(
            "%d historical binary blob occurrence(s) were not scanned"
            % result["binary"])
    if result["unsupported_encoding"]:
        result["incomplete_reasons"].append(
            "%d historical blob occurrence(s) used an unsupported encoding"
            % result["unsupported_encoding"])
    result["incomplete_reasons"] = list(dict.fromkeys(
        result["incomplete_reasons"]))
    return result


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("root", help="repository directory OR a single file")
    ap.add_argument("--max-bytes", type=int, default=2_000_000)
    ap.add_argument("--json", action="store_true",
                    help="emit findings as JSON (same redacted fields only)")
    ap.add_argument("--git-history", action="store_true",
                    help="also scan bounded LOCAL committed Git objects; "
                         "never fetches or checks out")
    ap.add_argument("--history-max-commits", type=int, default=100)
    ap.add_argument("--history-max-files", type=int, default=10_000)
    ap.add_argument("--history-max-bytes", type=int, default=100_000_000,
                    help="total unique historical blob bytes")
    ap.add_argument("--history-max-findings", type=int, default=10_000)
    args = ap.parse_args(argv)
    if not 1 <= args.max_bytes <= 100_000_000:
        print("--max-bytes must be positive and no greater than 100000000 (got %d)" % args.max_bytes)
        return 2
    limits = (("--history-max-commits", args.history_max_commits, 5000),
              ("--history-max-files", args.history_max_files, 100_000),
              ("--history-max-bytes", args.history_max_bytes, 1_000_000_000),
              ("--history-max-findings", args.history_max_findings, 100_000))
    for label, value, maximum in limits:
        if not 1 <= value <= maximum:
            print("%s must be 1..%d (got %d)" % (label, maximum, value))
            return 2

    if not os.path.exists(args.root):
        print("Path not found: %s" % args.root)
        return 2
    root = os.path.abspath(args.root)
    if not (os.path.isdir(root) or os.path.isfile(root)):
        print("Root must be a directory or a regular file: %s" % args.root)
        return 2

    fingerprint, key_source = make_fingerprinter()
    self_path = os.path.abspath(__file__)
    hits = []
    counts = {k: 0 for k in OUTCOMES}
    long_lines_total = 0
    for path in iter_candidates(root, self_path):
        outcome, findings, long_lines = scan_file(
            path, root, args.max_bytes, fingerprint)
        counts[outcome] += 1
        long_lines_total += long_lines
        hits.extend(findings)

    candidates = sum(counts.values())
    incomplete_reasons = []
    if counts["skipped_too_large"]:
        incomplete_reasons.append("%d file(s) skipped as larger than "
                                  "--max-bytes %d"
                                  % (counts["skipped_too_large"],
                                     args.max_bytes))
    if counts["unreadable"]:
        incomplete_reasons.append("%d file(s) unreadable"
                                  % counts["unreadable"])
    if counts["binary"]:
        incomplete_reasons.append("%d extensionless binary file(s) NOT "
                                  "scanned — rename/exclude them "
                                  "deliberately or scan them with a "
                                  "binary-aware tool" % counts["binary"])
    if counts["unsupported_encoding"]:
        incomplete_reasons.append("%d file(s) in an unsupported encoding "
                                  "(not UTF-8/UTF-16) — convert or exclude "
                                  "them deliberately"
                                  % counts["unsupported_encoding"])
    if counts["unsafe_symlink"]:
        incomplete_reasons.append(
            "%d symlink/junction path(s) refused (scanner never follows "
            "filesystem links)" % counts["unsafe_symlink"])
    if counts["inspected"] == 0:
        incomplete_reasons.append("ZERO files inspected")
    complete = not incomplete_reasons

    coverage = {
        "candidates": candidates,
        "inspected": counts["inspected"],
        "suppressed": counts["suppressed"],
        "binary": counts["binary"],
        "unsupported_encoding": counts["unsupported_encoding"],
        "skipped_too_large": counts["skipped_too_large"],
        "unreadable": counts["unreadable"],
        "unsafe_symlink": counts["unsafe_symlink"],
        "long_lines_chunked": long_lines_total,
        "complete": complete,
    }

    history = None
    if args.git_history:
        history = scan_git_history(
            root, fingerprint, args.history_max_commits,
            args.history_max_files, args.max_bytes, args.history_max_bytes,
            args.history_max_findings)
    history_hits = [] if history is None else history["findings"]
    all_complete = complete and (history is None or history["complete"])

    if not all_complete:
        exit_code = 3
    elif hits or history_hits:
        exit_code = 1
    else:
        exit_code = 0

    if args.json:
        document = {"scanned_files": counts["inspected"],
                    "root": os.path.basename(root),
                    "coverage": coverage,
                    "fingerprint_key": key_source,
                    "findings": hits}
        if history is not None:
            document["history"] = history
        print(json.dumps(document, indent=2))
        return exit_code

    print("Coverage: %d candidate file(s) — %d inspected, %d suppressed, "
          "%d binary, %d unsupported-encoding, %d too large, %d unreadable, "
          "%d unsafe symlink/junction; "
          "%d over-long line(s) scanned in chunks"
          % (candidates, counts["inspected"], counts["suppressed"],
             counts["binary"], counts["unsupported_encoding"],
              counts["skipped_too_large"], counts["unreadable"],
              counts["unsafe_symlink"],
             long_lines_total))
    if not complete:
        print("INCOMPLETE COVERAGE: " + "; ".join(incomplete_reasons))
        print("An incomplete scan is NOT a clean scan.")
    print("")
    if history is not None:
        print("Git history: %d commit(s), %d path(s), %d unique blob(s), "
              "%d byte(s), %d finding(s); complete=%s"
              % (history["commits_scanned"], history["files_considered"],
                 history["blobs_scanned"], history["bytes_scanned"],
                 len(history_hits), history["complete"]))
        if not history["complete"]:
            print("INCOMPLETE HISTORY: " + "; ".join(
                history["incomplete_reasons"]))
        print("")
    if not hits and not history_hits:
        if all_complete:
            print("No obvious hardcoded secrets found.")
            print("(Absence of matches is not proof of safety — review auth "
                  "and config handling manually too.)")
        else:
            print("No findings, but the scan was INCOMPLETE (see above) — "
                  "do not treat this as clean.")
        return exit_code

    print("POTENTIAL SECRETS (%d) — verify each before acting.\n"
          "Values are REDACTED by design; use path:line to inspect locally.\n"
          "Fingerprints are HMAC-keyed (%s) — no offline dictionary "
          "attacks.\n" % (len(hits) + len(history_hits), key_source))
    for h in hits:
        note = "  (looks like a placeholder — verify)" if h["placeholder_hint"] else ""
        print("  [%s]%s" % (h["rule"], note))
        print("    %s:%d" % (h["path"], h["line"]))
        print("    preview: %s" % h["preview"])
        print("    %s\n" % h["fingerprint"])
    if history_hits:
        print("POTENTIAL HISTORICAL SECRETS (%d) - no source preview/value "
              "is emitted.\n" % len(history_hits))
        for h in history_hits:
            print("  [%s] commit=%s path=%s line=%d"
                  % (h["rule"], h["commit"], json.dumps(h["path"]),
                     h["line"]))
            print("    %s\n" % h["fingerprint"])
    print("If any real secret was ever committed, ROTATE it — git history "
          "keeps it even after deletion.")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
