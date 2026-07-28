"""Adversarial tests for the committed project-profile trust boundary."""
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import unittest


REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GP_PATH = os.path.join(REPO, "plugins", "gate", "lib", "gate_policy.py")
CE_PATH = os.path.join(
    REPO, "plugins", "gate", "skills", "production-readiness-reviewer",
    "scripts", "check_evidence.py")
_SPEC = importlib.util.spec_from_file_location("gp_profile_binding", GP_PATH)
gp = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(gp)


def git(root, *args, input_bytes=None):
    return subprocess.run(
        ["git"] + list(args), cwd=root, input=input_bytes,
        capture_output=True, timeout=30)


class CommittedProjectProfile(unittest.TestCase):
    def make_repo(self, content="# Project\n\nProject profile: api-service\n"):
        root = tempfile.mkdtemp(prefix="profile-binding-")
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        self.assertEqual(git(root, "init", "-q", ".").returncode, 0)
        git(root, "config", "user.email", "t@example.invalid")
        git(root, "config", "user.name", "t")
        with open(os.path.join(root, "README.md"), "w", encoding="utf-8") as f:
            f.write("fixture\n")
        if content is not None:
            os.makedirs(os.path.join(root, ".solo"), exist_ok=True)
            with open(os.path.join(root, ".solo", "project.md"), "w",
                      encoding="utf-8") as f:
                f.write(content)
        self.assertEqual(git(root, "add", "-A").returncode, 0)
        self.assertEqual(git(root, "commit", "-qm", "fixture").returncode, 0)
        return root

    def test_reads_committed_blob_not_mutable_worktree(self):
        root = self.make_repo()
        profile, reason = gp.committed_project_profile(root)
        self.assertEqual((profile, reason), ("api-service", None))
        with open(os.path.join(root, ".solo", "project.md"), "w",
                  encoding="utf-8") as f:
            f.write("Project profile: library-package\n")
        profile, reason = gp.committed_project_profile(root)
        self.assertEqual((profile, reason), ("api-service", None))

    def test_missing_malformed_ambiguous_and_unknown_fail_closed(self):
        fixtures = (
            (None, "exist exactly once"),
            ("# Project\nProfile: api-service\n", "exactly one canonical"),
            ("Project profile: api-service\n"
             "Project profile: library-package\n", "2 profile declaration"),
            ("Project profile: api-service\n"
             " Project profile: library-package extra\n",
             "2 profile declaration"),
            ("Project profile: invented-profile\n", "unrecognized"),
        )
        for content, needle in fixtures:
            with self.subTest(content=content):
                root = self.make_repo(content)
                profile, reason = gp.committed_project_profile(root)
                self.assertIsNone(profile)
                self.assertIn(needle, reason)

    def test_git_symlink_object_is_refused_without_following_it(self):
        root = self.make_repo(None)
        blob = git(root, "hash-object", "-w", "--stdin",
                   input_bytes=b"README.md\n")
        self.assertEqual(blob.returncode, 0, blob.stderr)
        sha = blob.stdout.decode("ascii").strip()
        update = git(root, "update-index", "--add", "--cacheinfo",
                     "120000,%s,.solo/project.md" % sha)
        self.assertEqual(update.returncode, 0, update.stderr)
        self.assertEqual(git(root, "commit", "-qm", "symlink profile").returncode,
                         0)
        profile, reason = gp.committed_project_profile(root)
        self.assertIsNone(profile)
        self.assertIn("regular file", reason)

    def test_checker_requires_profile_and_rejects_cli_commit_mismatch(self):
        root = self.make_repo()
        evidence = os.path.join(root, ".solo", "gate-evidence")
        os.makedirs(evidence)
        base = [sys.executable, CE_PATH, evidence, "--root", root,
                "--environment", "production", "--project", "demo"]
        missing = subprocess.run(base, capture_output=True, text=True,
                                 timeout=60)
        self.assertEqual(missing.returncode, 2)
        self.assertIn("--profile", missing.stderr)
        mismatch = subprocess.run(
            base + ["--profile", "library-package"], capture_output=True,
            text=True, timeout=60)
        self.assertEqual(mismatch.returncode, 2, mismatch.stdout)
        self.assertIn("does not match", mismatch.stdout)
        self.assertIn("committed .solo/project.md", mismatch.stdout)


if __name__ == "__main__":
    unittest.main()
