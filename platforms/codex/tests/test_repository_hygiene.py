"""Repository hygiene checks needed for reproducible GitHub releases."""

from __future__ import annotations

import re
import hashlib
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
BINARY_SUFFIXES = {
    ".coverage",
    ".docx",
    ".gif",
    ".ico",
    ".jpeg",
    ".jpg",
    ".pdf",
    ".png",
    ".pyc",
    ".ttf",
    ".woff",
    ".woff2",
    ".zip",
}
PIN = re.compile(r"^([A-Za-z0-9_.-]+)==([^\s]+)$")


def repository_text_files() -> list[Path]:
    from tools import package_release

    files = []
    for path in package_release.included_files(ROOT):
        if path.name in {".coverage", "coverage.xml"}:
            continue
        if path.suffix.lower() in BINARY_SUFFIXES:
            continue
        files.append(path)
    return files


class RepositoryHygiene(unittest.TestCase):
    def test_secret_environment_files_are_ignored(self):
        for name in (".env", ".env.local", ".env.production"):
            with self.subTest(name=name):
                result = subprocess.run(
                    ["git", "check-ignore", "--no-index", "--", name],
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr)

        example = subprocess.run(
            ["git", "check-ignore", "--no-index", "--", ".env.example"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(example.returncode, 0, example.stdout)

    def test_generated_runtime_state_is_not_release_input(self):
        from tools import package_release

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            included = root / "plugins" / "demo" / "SKILL.md"
            included.parent.mkdir(parents=True)
            included.write_bytes(b"release input\n")
            runtime_paths = (
                root / ".solo" / "project.md",
                root / ".solo" / "gate-evidence" / "product.json",
                root / ".solo" / "run-state" / "run.json",
                root / "artifacts" / "runs" / "run-1" / "state.json",
                root / "worktrees" / "runs" / "run-1" / "worker" / "log.txt",
            )
            for path in runtime_paths:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"generated\r\n")

            # ``Path`` equality is case-sensitive on some Windows Python
            # builds, while temporary paths can mix long and 8.3 spellings.
            # Compare canonical resolved paths so this test checks packaging
            # policy rather than the runner's temp-path spelling.
            packaged = {path.resolve() for path in package_release.included_files(root)}
            self.assertIn(included.resolve(), packaged)
            self.assertFalse(packaged.intersection(path.resolve() for path in runtime_paths))

    def test_repository_text_is_lf_normalized(self):
        offenders = []
        for path in repository_text_files():
            data = path.read_bytes()
            if b"\r" in data:
                offenders.append(path.relative_to(ROOT).as_posix())
        self.assertEqual(offenders, [], "non-LF text files: " + ", ".join(offenders))

        from tools import package_release
        declared = {}
        for line in (ROOT / "RELEASE-CHECKSUMS.txt").read_text(
                encoding="utf-8").splitlines():
            digest, relative = line.split("  ", 1)
            declared[relative] = digest
        actual = {
            path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in package_release.included_files(ROOT)
            if path.name != "RELEASE-CHECKSUMS.txt"
        }
        self.assertEqual(declared, actual, "source checksum inventory is stale")

    def test_gitattributes_enforces_portable_text_and_binary_assets(self):
        attributes = (ROOT / ".gitattributes").read_text(encoding="utf-8")
        self.assertIn("* text=auto eol=lf", attributes)
        for suffix in ("docx", "zip", "pdf", "png", "woff2"):
            self.assertIn(f"*.{suffix} binary", attributes)

    def test_validation_dependencies_are_hash_locked_and_used_by_ci(self):
        requested = set()
        for raw in (ROOT / "requirements-dev.txt").read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            match = PIN.fullmatch(line)
            self.assertIsNotNone(match, line)
            requested.add(match.group(1).lower().replace("_", "-"))

        lock = (ROOT / "requirements-dev.lock").read_text(encoding="utf-8")
        locked = {
            match.group(1).lower().replace("_", "-")
            for match in re.finditer(r"(?m)^([A-Za-z0-9_.-]+)==", lock)
        }
        self.assertTrue(requested.issubset(locked), sorted(requested - locked))
        blocks = re.split(r"(?m)(?=^[A-Za-z0-9_.-]+==)", lock)
        requirement_blocks = [block for block in blocks if PIN.match(block.split(" \\", 1)[0])]
        self.assertTrue(requirement_blocks)
        for block in requirement_blocks:
            self.assertIn("--hash=sha256:", block, block.splitlines()[0])

        ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        self.assertIn("--require-hashes", ci)
        self.assertIn("requirements-dev.lock", ci)

        audit_input = [
            line.strip()
            for line in (ROOT / "requirements-audit.txt").read_text(
                encoding="utf-8"
            ).splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
        self.assertEqual(audit_input[0], "-c requirements-dev.txt")
        self.assertEqual(
            set(audit_input[1:]),
            {"pip==26.1.2", "pip-audit==2.10.1"},
        )
        audit_lock = (ROOT / "requirements-audit.lock").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("WARNING", audit_lock.upper())
        self.assertNotIn("not pinned", audit_lock.lower())
        audit_blocks = re.split(r"(?m)(?=^[A-Za-z0-9_.-]+==)", audit_lock)
        audit_requirement_blocks = [
            block for block in audit_blocks if PIN.match(block.split(" \\", 1)[0])
        ]
        self.assertTrue(audit_requirement_blocks)
        for block in audit_requirement_blocks:
            self.assertIn("--hash=sha256:", block, block.splitlines()[0])
        self.assertIn("pip==26.1.2", audit_lock)
        self.assertIn("pip-audit==2.10.1", audit_lock)

        ci_payload = yaml.safe_load(ci)
        ci_steps = ci_payload["jobs"]["test"]["steps"]
        ci_audit_steps = [
            step for step in ci_steps
            if "audit" in step.get("name", "").lower()
        ]
        self.assertEqual(len(ci_audit_steps), 2)
        self.assertTrue(all(
            step.get("if") == "matrix.python-version == '3.12'"
            for step in ci_audit_steps
        ))

        publish_text = (ROOT / ".github/workflows/publish-release.yml").read_text(
            encoding="utf-8"
        )
        publish_payload = yaml.safe_load(publish_text)
        publish_steps = publish_payload["jobs"]["build"]["steps"]
        publish_audit_steps = [
            step for step in publish_steps
            if "audit" in step.get("name", "").lower()
        ]
        self.assertEqual(len(publish_audit_steps), 2)
        self.assertTrue(all("if" not in step for step in publish_audit_steps))
        for workflow in (ci, publish_text):
            self.assertIn("requirements-audit.lock", workflow)
            self.assertIn("python -m pip_audit --strict", workflow)
            self.assertIn("--disable-pip --no-deps --require-hashes", workflow)
            package_step = (
                "Build deterministic release package"
                if "Build deterministic release package" in workflow
                else "Build and smoke-test deterministic release package"
            )
            self.assertLess(
                workflow.index("Audit hash-locked Python dependencies"),
                workflow.index(package_step),
            )

    def test_release_workflow_writers_support_python39(self):
        workflow = (ROOT / ".github/workflows/publish-release.yml").read_text(
            encoding="utf-8"
        )
        # Path.write_text(..., newline=...) is unavailable on Python 3.9;
        # keep the embedded release-sidecar writer on the portable byte path.
        self.assertNotIn("sidecar.write_text", workflow)
        self.assertIn("sidecar.write_bytes", workflow)


if __name__ == "__main__":
    unittest.main()
