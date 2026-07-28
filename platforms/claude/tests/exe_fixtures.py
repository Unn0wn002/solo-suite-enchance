"""INERT fake-executable fixtures for PATH-resolution tests.

These executables do nothing (exit 0; optionally print a file named by an
environment variable) — they exist ONLY so gate_policy.resolve_executable
has something to resolve, and so tests can prove that project-local
resolution is REJECTED while external resolution is accepted and recorded.
Windows gets .bat shims (shutil.which finds them via PATHEXT); POSIX gets
shell scripts.
"""
import os
import shutil
import stat

WINDOWS = os.name == "nt"

# executable families accepted somewhere in the gate command policy
FAMILY_NAMES = ("python", "python3", "pytest", "gh", "npm", "npx", "curl",
                "cargo", "make", "go", "alembic", "pip-audit",
                "govulncheck")


def make_exe(dirpath, name, stdout_file_env=None):
    """Create an inert executable `name` in dirpath; returns its path."""
    os.makedirs(dirpath, exist_ok=True)
    if WINDOWS:
        path = os.path.join(dirpath, name + ".bat")
        lines = ["@echo off"]
        if stdout_file_env:
            lines.append('if defined %s type "%%%s%%"'
                         % (stdout_file_env, stdout_file_env))
        lines.append("exit /b 0")
        with open(path, "w", encoding="ascii") as f:
            f.write("\r\n".join(lines) + "\r\n")
    else:
        path = os.path.join(dirpath, name)
        lines = ["#!/bin/sh"]
        if stdout_file_env:
            lines.append('if [ -n "${%s:-}" ]; then cat "${%s}"; fi'
                         % (stdout_file_env, stdout_file_env))
        lines.append("exit 0")
        with open(path, "w", encoding="ascii") as f:
            f.write("\n".join(lines) + "\n")
        os.chmod(path, 0o755)
    return path


def make_bin_dir(base, names=FAMILY_NAMES, stdout_file_env=None):
    """Create base/fixture-bin populated with inert executables."""
    d = os.path.join(base, "fixture-bin")
    for n in names:
        make_exe(d, n, stdout_file_env=stdout_file_env)
    return d


def force_rmtree(path):
    """shutil.rmtree that clears read-only bits first (Windows .git)."""
    def _onerror(func, p, _exc):
        try:
            os.chmod(p, stat.S_IWRITE | stat.S_IREAD)
            func(p)
        except OSError:
            pass
    shutil.rmtree(path, onerror=_onerror)


def disable_git_dir(root):
    """Cross-platform way to break a repo for fail-closed tests: RENAME
    .git to .git-disabled (never rmtree — Windows read-only object files
    make direct rmtree raise). Returns the new path."""
    src = os.path.join(root, ".git")
    dst = os.path.join(root, ".git-disabled")
    os.rename(src, dst)
    return dst
