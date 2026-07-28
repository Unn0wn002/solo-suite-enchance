"""Tracked-content identity regressions for the AgentRoom runner."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "plugins/ai/skills/agent-room-templates/scripts/git_trust.py"
spec = importlib.util.spec_from_file_location("agentroom_git_trust", SCRIPT)
if spec is None or spec.loader is None:
    raise RuntimeError("cannot import AgentRoom Git trust helper")
git_trust = importlib.util.module_from_spec(spec)
spec.loader.exec_module(git_trust)


def git(root: Path, *arguments: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(root), *arguments], check=check,
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )


class GitTrackedIdentity(unittest.TestCase):
    def make_repository(self, root: Path) -> str:
        git(root, "init", "-q")
        git(root, "config", "user.email", "runner@example.test")
        git(root, "config", "user.name", "Runner Test")
        (root / "app.txt").write_text("bound\n", encoding="utf-8")
        git(root, "add", "app.txt")
        git(root, "commit", "-qm", "fixture")
        return git(root, "rev-parse", "HEAD").stdout.strip()

    def test_manifest_detects_content_even_when_status_can_be_concealed(self) -> None:
        for flag, clear in (
            ("--assume-unchanged", "--no-assume-unchanged"),
            ("--skip-worktree", "--no-skip-worktree"),
        ):
            with self.subTest(flag=flag), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                commit = self.make_repository(root)
                manifest = git_trust.build_manifest(root, commit)
                git_trust.verify_manifest(root, manifest, commit)
                git(root, "update-index", flag, "app.txt")
                (root / "app.txt").write_text("hidden\n", encoding="utf-8")
                self.assertEqual(
                    git(root, "status", "--porcelain").stdout.strip(), "",
                )
                with self.assertRaisesRegex(
                    git_trust.GitTrustError, "concealment flags",
                ):
                    git_trust.verify_manifest(root, manifest, commit)
                git(root, "update-index", clear, "app.txt")

    def test_manifest_detects_unflagged_worktree_and_index_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            commit = self.make_repository(root)
            manifest = git_trust.build_manifest(root, commit)
            (root / "app.txt").write_text("changed\n", encoding="utf-8")
            with self.assertRaisesRegex(
                git_trust.GitTrustError, "working-tree content changed",
            ):
                git_trust.verify_manifest(root, manifest, commit)
            git(root, "add", "app.txt")
            with self.assertRaisesRegex(
                git_trust.GitTrustError, "index identity changed",
            ):
                git_trust.verify_manifest(root, manifest, commit)

    def test_manifest_rejects_fsmonitor_valid_index_entries(self) -> None:
        def flagged_run(root: Path, *arguments: str, **kwargs):
            output = b"h app.txt\0" if "-f" in arguments else b"H app.txt\0"
            return subprocess.CompletedProcess(arguments, 0, output, b"")

        with mock.patch.object(git_trust, "_run", side_effect=flagged_run):
            with self.assertRaisesRegex(
                git_trust.GitTrustError, "concealment flags",
            ):
                git_trust._reject_concealment_flags(Path("."))

    def test_manifest_rejects_gitlink_even_when_dirty_submodule_is_ignored(
            self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            fixture = Path(temp)
            dependency = fixture / "dependency"
            repository = fixture / "repository"
            dependency.mkdir()
            repository.mkdir()
            self.make_repository(dependency)
            self.make_repository(repository)
            git(
                repository, "-c", "protocol.file.allow=always", "submodule",
                "add", "--name", "dep", str(dependency), "modules/dep",
            )
            git(repository, "commit", "-qam", "add submodule")
            commit = git(repository, "rev-parse", "HEAD").stdout.strip()
            git(repository, "config", "submodule.dep.ignore", "dirty")
            (repository / "modules/dep/app.txt").write_text(
                "hidden dirty content\n", encoding="utf-8",
            )

            self.assertEqual(
                git(repository, "status", "--porcelain").stdout.strip(), "",
            )
            with self.assertRaisesRegex(
                git_trust.GitTrustError, "submodules/gitlinks are not allowed",
            ):
                git_trust.build_manifest(repository, commit)
            with self.assertRaisesRegex(
                git_trust.GitTrustError, "submodules/gitlinks are not allowed",
            ):
                git_trust.verify_manifest(
                    repository,
                    {
                        "schema": git_trust.MANIFEST_SCHEMA,
                        "commit": commit,
                        "files": {},
                    },
                    commit,
                )


if __name__ == "__main__":
    unittest.main()
