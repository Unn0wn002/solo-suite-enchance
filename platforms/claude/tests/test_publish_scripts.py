"""Fail-closed tests for the v1.0.27 publication helpers.

The integration cases push only to disposable local bare repositories. They
never contact a network remote and never mutate the developer's checkout.
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
import zipfile


REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RELEASE = os.path.join(REPO, "release")
PREPARE = os.path.join(RELEASE, "prepare-release-branch-v1.0.27.ps1")
TAG = os.path.join(RELEASE, "publish-approved-tag-v1.0.27.ps1")
COMMON = os.path.join(RELEASE, "publish-common.ps1")
WORKFLOW = os.path.join(REPO, ".github", "workflows", "ci.yml")


def run(argv, cwd=None, check=True, env=None):
    result = subprocess.run(
        argv, cwd=cwd, capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=120, env=env)
    if check and result.returncode:
        raise AssertionError(
            "command failed (%s):\nstdout:\n%s\nstderr:\n%s"
            % (result.returncode, result.stdout, result.stderr))
    return result


def git(cwd, *args, check=True):
    return run(["git", "-C", cwd] + list(args), check=check)


def tree_digest(root, relative_paths):
    digest = hashlib.sha256()
    for rel in sorted(relative_paths):
        with open(os.path.join(root, *rel.split("/")), "rb") as fh:
            file_digest = hashlib.sha256(fh.read()).hexdigest()
        digest.update(rel.encode("utf-8"))
        digest.update(b"\0")
        digest.update(file_digest.encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


class PublishFixture:
    def __init__(self, base):
        self.base = base
        self.remote = os.path.join(base, "remote.git")
        self.seed = os.path.join(base, "seed")
        self.candidate = os.path.join(base, "candidate")
        self.artifacts = os.path.join(base, "artifacts")
        os.makedirs(self.seed)
        os.makedirs(self.candidate)
        os.makedirs(self.artifacts)
        self._write_tree(self.seed, "1.0.25", "old release\n")
        self._write_tree(self.candidate, "1.0.27", "reviewed release\n")

        run(["git", "init", "--bare", "--initial-branch=main", self.remote])
        run(["git", "init", "--initial-branch=main", self.seed])
        git(self.seed, "config", "user.name", "Fixture")
        git(self.seed, "config", "user.email", "fixture@example.invalid")
        git(self.seed, "add", "--all")
        git(self.seed, "commit", "-m", "seed")
        git(self.seed, "remote", "add", "origin", self.remote)
        git(self.seed, "push", "origin", "main")
        self.base_oid = git(self.seed, "rev-parse", "HEAD").stdout.strip()
        self._build_candidate_artifacts()

    @staticmethod
    def _write_tree(root, version, readme):
        manifest_dir = os.path.join(root, ".claude-plugin")
        os.makedirs(manifest_dir)
        with open(os.path.join(manifest_dir, "marketplace.json"), "w",
                  encoding="utf-8", newline="\n") as fh:
            json.dump({"metadata": {"version": version}, "plugins": []}, fh)
            fh.write("\n")
        with open(os.path.join(root, "README.md"), "w", encoding="utf-8",
                  newline="\n") as fh:
            fh.write(readme)
        if version == "1.0.27":
            with open(os.path.join(root, "windows-crlf.txt"), "wb") as fh:
                fh.write(b"line one\r\nline two\r\n")

    def _build_candidate_artifacts(self):
        version = "1.0.27"
        top = "solo-suite-plugin-v" + version
        zip_name = top + ".zip"
        self.zip_path = os.path.join(self.artifacts, zip_name)
        paths = []
        for dirpath, _dirnames, filenames in os.walk(self.candidate):
            for name in filenames:
                full = os.path.join(dirpath, name)
                rel = os.path.relpath(full, self.candidate).replace(os.sep, "/")
                paths.append(rel)
        with zipfile.ZipFile(self.zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for rel in sorted(paths):
                zf.write(os.path.join(self.candidate, *rel.split("/")),
                         top + "/" + rel)
        with open(self.zip_path, "rb") as fh:
            zip_hash = hashlib.sha256(fh.read()).hexdigest()
        self.sums_path = os.path.join(self.artifacts, "SHA256SUMS")
        with open(self.sums_path, "w", encoding="ascii", newline="\n") as fh:
            fh.write("%s  %s\n" % (zip_hash, zip_name))
            for rel in sorted(paths):
                full = os.path.join(self.candidate, *rel.split("/"))
                with open(full, "rb") as source:
                    digest = hashlib.sha256(source.read()).hexdigest()
                fh.write("%s  %s/%s\n" % (digest, top, rel))
        self.provenance_path = os.path.join(self.artifacts, "provenance.json")
        with open(self.provenance_path, "w", encoding="utf-8",
                  newline="\n") as fh:
            json.dump({
                "artifact": zip_name,
                "artifact_sha256": zip_hash,
                "version": version,
                "file_count": len(paths),
                "staged_tree_sha256": tree_digest(self.candidate, paths),
                "source_dirty": False,
                "source_commit": self.base_oid,
            }, fh)
            fh.write("\n")


class ReleaseWorkflowPolicy(unittest.TestCase):
    @staticmethod
    def workflow_text():
        with open(WORKFLOW, encoding="utf-8") as fh:
            return fh.read()

    @staticmethod
    def job_block(workflow, job_name):
        import re
        match = re.search(
            r"(?ms)^  %s:\n.*?(?=^  [A-Za-z0-9_-]+:\n|\Z)"
            % re.escape(job_name), workflow)
        if not match:
            raise AssertionError("workflow job is missing: %s" % job_name)
        return match.group(0)

    def test_windows_default_leg_is_separate_from_utf8_matrix(self):
        workflow = self.workflow_text()
        self.assertIn("encoding_mode: windows-default", workflow)
        self.assertIn('python_utf8: "0"', workflow)
        self.assertIn('PYTHONIOENCODING: "cp1252"', workflow)
        self.assertEqual(
            workflow.count(
                "PYTHONPYCACHEPREFIX: "
                "${{ github.workspace }}/../solo-suite-pycache"),
            2)
        self.assertNotIn("\nenv:\n  PYTHONUTF8:", workflow)

    def test_job_level_env_does_not_use_runner_context(self):
        workflow = self.workflow_text()
        for job_name in ("test", "release-build"):
            block = self.job_block(workflow, job_name)
            job_header = block.split("\n    steps:", 1)[0]
            self.assertNotIn("${{ runner.", job_header, job_name)

    def test_command_substitution_failures_are_not_masked_by_export(self):
        workflow = self.workflow_text()
        self.assertNotRegex(
            workflow,
            r'(?m)^\s*export\s+[A-Za-z_][A-Za-z0-9_]*="\$\(')

    def test_previous_release_baseline_is_inventory_pinned(self):
        workflow = self.workflow_text()
        build = self.job_block(workflow, "release-build")
        self.assertNotIn("git describe", build)
        self.assertNotIn('["git", "tag", "--list"]', build)
        self.assertIn("previous = parse(previous_name", build)
        self.assertIn("if previous >= current:", build)
        self.assertIn("print(previous_name)", build)
        self.assertIn(
            'git cat-file -t "refs/tags/$PREVIOUS_TAG"', build)
        self.assertIn(
            'release/previous-release-inventory.json', build)
        self.assertIn(
            '"refs/tags/${PREVIOUS_TAG}:refs/tags/${PREVIOUS_TAG}"',
            build)

        marker = "PREVIOUS_VERSION=\"$(python - <<'PY'\n"
        self.assertIn(marker, build)
        selector = build.split(marker, 1)[1].split(
            "\n          PY\n", 1)[0]
        selector = textwrap.dedent(selector)

        with tempfile.TemporaryDirectory() as repo:
            git(repo, "init")
            git(repo, "config", "user.name", "Release test")
            git(repo, "config", "user.email", "release@example.invalid")
            tracked = os.path.join(repo, "state.txt")
            with open(tracked, "w", encoding="utf-8", newline="\n") as fh:
                fh.write("baseline\n")
            git(repo, "add", "state.txt")
            git(repo, "commit", "-m", "baseline")
            git(repo, "tag", "-a", "v1.0.20", "-m", "v1.0.20")
            with open(tracked, "w", encoding="utf-8", newline="\n") as fh:
                fh.write("failed later tag\n")
            git(repo, "commit", "-am", "v1.0.22 failed tag")
            git(repo, "tag", "-a", "v1.0.22", "-m", "v1.0.22")
            os.makedirs(os.path.join(repo, "release"))
            with open(os.path.join(repo, "release",
                                   "previous-release-inventory.json"),
                      "w", encoding="utf-8", newline="\n") as fh:
                json.dump({"release": "1.0.25"}, fh)
            env = os.environ.copy()
            env["GITHUB_REF_NAME"] = "v1.0.27"
            selected = run(
                [sys.executable, "-c", selector], cwd=repo, env=env)
            self.assertEqual(selected.stdout.strip(), "1.0.25")

    def test_annotated_tag_object_is_restored_after_checkout_clobber(self):
        workflow = self.workflow_text()
        build = self.job_block(workflow, "release-build")
        guard = 'if [[ ! "$GITHUB_REF_NAME" =~ ^v[0-9]+'
        refspec = (
            '"refs/tags/${GITHUB_REF_NAME}:'
            'refs/tags/${GITHUB_REF_NAME}"')
        annotation_check = (
            'test "$(git cat-file -t '
            '"refs/tags/$GITHUB_REF_NAME")" = "tag"')
        self.assertIn(guard, build)
        self.assertIn("git fetch --no-tags --force origin", build)
        self.assertIn(refspec, build)
        self.assertIn(annotation_check, build)
        self.assertLess(build.index(guard), build.index(refspec))
        self.assertLess(build.index(refspec), build.index(annotation_check))

        with tempfile.TemporaryDirectory() as root:
            origin = os.path.join(root, "origin.git")
            seed = os.path.join(root, "seed")
            checkout = os.path.join(root, "checkout")
            os.makedirs(origin)
            os.makedirs(seed)
            os.makedirs(checkout)
            git(origin, "init", "--bare")
            git(seed, "init")
            git(seed, "config", "user.name", "Release test")
            git(seed, "config", "user.email", "release@example.invalid")
            with open(os.path.join(seed, "state.txt"), "w",
                      encoding="utf-8", newline="\n") as fh:
                fh.write("tagged\n")
            git(seed, "add", "state.txt")
            git(seed, "commit", "-m", "tagged commit")
            git(seed, "tag", "-a", "v1.0.25", "-m", "v1.0.25")
            git(seed, "remote", "add", "origin", origin)
            git(seed, "push", "origin", "HEAD:refs/heads/main")
            git(seed, "push", "origin", "refs/tags/v1.0.25")
            commit = git(seed, "rev-parse", "HEAD").stdout.strip()

            git(checkout, "init")
            git(checkout, "remote", "add", "origin", origin)
            git(checkout, "fetch", "--no-tags", "origin",
                "refs/tags/v1.0.25:refs/tags/v1.0.25")
            self.assertEqual(
                git(checkout, "cat-file", "-t",
                    "refs/tags/v1.0.25").stdout.strip(), "tag")

            # Reproduce actions/checkout's tag-event follow-up fetch: it maps
            # the peeled event commit directly onto the local tag ref.
            git(checkout, "fetch", "--no-tags", "--force", "origin",
                "+%s:refs/tags/v1.0.25" % commit)
            self.assertEqual(
                git(checkout, "cat-file", "-t",
                    "refs/tags/v1.0.25").stdout.strip(), "commit")

            git(checkout, "fetch", "--no-tags", "--force", "origin",
                "refs/tags/v1.0.25:refs/tags/v1.0.25")
            self.assertEqual(
                git(checkout, "cat-file", "-t",
                    "refs/tags/v1.0.25").stdout.strip(), "tag")
            self.assertEqual(
                git(checkout, "rev-parse",
                    "refs/tags/v1.0.25^{}").stdout.strip(), commit)

    def test_every_checkout_drops_persisted_credentials(self):
        workflow = self.workflow_text()
        marker = "\n      - uses: actions/checkout@"
        checkout_steps = workflow.split(marker)[1:]
        self.assertGreater(len(checkout_steps), 0)
        for remainder in checkout_steps:
            step = remainder.split("\n      - ", 1)[0]
            self.assertRegex(step.splitlines()[0], r"^[0-9a-f]{40}(?:\s+#.*)?$")
            self.assertIn("persist-credentials: false", step)

    def test_claude_cli_is_exact_and_integrity_locked(self):
        workflow = self.workflow_text()
        lock_path = os.path.join(RELEASE, "claude-cli", "package-lock.json")
        package_path = os.path.join(RELEASE, "claude-cli", "package.json")
        with open(lock_path, encoding="utf-8") as fh:
            lock = json.load(fh)
        with open(package_path, encoding="utf-8") as fh:
            package = json.load(fh)
        expected = {"@anthropic-ai/claude-code": "2.1.205"}
        self.assertEqual(package["dependencies"], expected)
        self.assertTrue(package["private"])
        self.assertEqual(lock["lockfileVersion"], 3)
        self.assertEqual(lock["packages"][""]["dependencies"], expected)
        cli = lock["packages"]["node_modules/@anthropic-ai/claude-code"]
        self.assertEqual(cli["version"], "2.1.205")
        self.assertTrue(cli["resolved"].startswith("https://registry.npmjs.org/"))
        self.assertTrue(cli["integrity"].startswith("sha512-"))
        for name, metadata in lock["packages"].items():
            if name.startswith("node_modules/"):
                self.assertIn("resolved", metadata, name)
                self.assertIn("integrity", metadata, name)
        self.assertNotIn("npm install -g", workflow)
        self.assertGreaterEqual(
            workflow.count("npm ci --prefix release/claude-cli --ignore-scripts"), 2)
        self.assertGreaterEqual(
            workflow.count("@anthropic-ai/claude-code-${CLI_PLATFORM}-${CLI_ARCH}"), 2)
        self.assertNotIn("release/claude-cli/node_modules/.bin", workflow)

    def test_release_privileges_are_split_and_fail_closed(self):
        workflow = self.workflow_text()
        build = self.job_block(workflow, "release-build")
        signer = self.job_block(workflow, "release-sign")
        publisher = self.job_block(workflow, "release-publish")

        self.assertEqual(workflow.count("contents: write"), 1)
        self.assertEqual(workflow.count("id-token: write"), 1)
        self.assertIn("permissions:\n      contents: read", build)
        self.assertNotIn("id-token: write", build)
        self.assertNotIn("contents: write", build)
        self.assertIn("permissions:\n      contents: read\n      id-token: write", signer)
        self.assertNotIn("contents: write", signer)
        self.assertIn("permissions:\n      contents: write", publisher)
        self.assertNotIn("id-token: write", publisher)

        self.assertIn("name: release-signing", signer)
        self.assertIn("name: release-publishing", publisher)
        for privileged in (signer, publisher):
            self.assertNotIn("actions/checkout@", privileged)
            self.assertNotIn("npm ci", privileged)
            self.assertNotIn("npm install", privileged)
            self.assertNotIn("pip install", privileged)
            self.assertNotIn("python release/", privileged)

    def test_artifacts_are_pinned_checksummed_and_reverified_remotely(self):
        import re
        workflow = self.workflow_text()
        signer = self.job_block(workflow, "release-sign")
        publisher = self.job_block(workflow, "release-publish")

        all_uses = re.findall(r"(?m)^\s+- uses: ([^\s#]+)", workflow)
        self.assertTrue(all_uses)
        for use in all_uses:
            self.assertRegex(use, r"^[^@]+@[0-9a-f]{40}$")
        download_pin = (
            "actions/download-artifact@"
            "3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c")
        self.assertEqual(workflow.count(download_pin), 2)
        self.assertIn("unsigned-release", signer)
        self.assertIn("signed-release", publisher)
        self.assertIn("sha256sum --check --strict RELEASE-SHA256SUMS", signer)
        self.assertIn("SIGNED-BUNDLE-SHA256SUMS", signer)
        self.assertIn("sha256sum --check --strict SIGNED-BUNDLE-SHA256SUMS", publisher)
        self.assertIn("gh release download", publisher)
        self.assertIn("cmp --silent", publisher)
        self.assertIn("asset set differs from the fixed allowlist", publisher)
        self.assertIn("expected-final-release-assets.txt", publisher)
        self.assertIn('test "${#assets[@]}" = "18"', publisher)
        self.assertGreaterEqual(publisher.count("cosign verify-blob"), 2)

    def test_no_checkout_publisher_has_explicit_repository_context(self):
        workflow = self.workflow_text()
        publisher = self.job_block(workflow, "release-publish")
        self.assertNotIn("actions/checkout@", publisher)
        self.assertIn("GH_REPO: ${{ github.repository }}", publisher)
        self.assertIn('test "$GH_REPO" = "$GITHUB_REPOSITORY"', publisher)
        logical_script = re.sub(r"[ \t]+", " ",
                                publisher.replace("\\\n", " "))
        release_commands = [
            line.strip() for line in logical_script.splitlines()
            if "gh release " in line
        ]
        self.assertGreaterEqual(len(release_commands), 6)
        for command in release_commands:
            self.assertIn('--repo "$GH_REPO"', command, command)

    def test_tag_release_is_signed_complete_draft_then_promoted(self):
        workflow = self.workflow_text()
        publisher = self.job_block(workflow, "release-publish")
        logical_script = re.sub(r"[ \t]+", " ",
                                publisher.replace("\\\n", " "))
        promote = (
            'gh release edit "$GITHUB_REF_NAME" --repo "$GH_REPO" '
            '--draft=false')
        self.assertIn("validation-logs-v%s.zip", workflow)
        self.assertIn("gh release create", publisher)
        self.assertIn("--draft", publisher)
        self.assertIn("asset set is incomplete or unexpected", publisher)
        self.assertIn(
            "verify_release_metadata \"$RUNNER_TEMP/draft-release.json\" "
            "true false remote-draft", logical_script)
        self.assertIn(
            "verify_release_metadata \"$RUNNER_TEMP/public-release.json\" "
            "false true public-release", logical_script)
        self.assertIn(promote, publisher)
        self.assertLess(publisher.index("cosign verify-blob"),
                        publisher.index("gh release create"))
        downloads = [match.start() for match in
                     re.finditer("gh release download", publisher)]
        self.assertEqual(len(downloads), 2)
        self.assertLess(publisher.index("gh release create"), downloads[0])
        self.assertLess(downloads[0], publisher.index(promote))
        self.assertLess(publisher.index(promote), downloads[1])

    def test_reproducibility_covers_the_complete_core_set_portably(self):
        workflow = self.workflow_text()
        self.assertIn("tempfile.TemporaryDirectory", workflow)
        for name in ("SHA256SUMS", "sbom.json", "provenance.json"):
            self.assertIn(name, workflow)
        self.assertNotIn('os.path.join("/tmp', workflow)


@unittest.skipUnless(shutil.which("git"), "git is required")
class PublishScripts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.powershell = shutil.which("pwsh") or shutil.which("powershell.exe")

    def setUp(self):
        self.temp = tempfile.mkdtemp(prefix="solo-suite-publish-test-")
        self.addCleanup(shutil.rmtree, self.temp, True)
        self.fixture = PublishFixture(self.temp)
        self.git_config = os.path.join(self.temp, "forced-global-gitconfig")
        with open(self.git_config, "w", encoding="ascii", newline="\n") as fh:
            fh.write("[core]\n\tautocrlf = true\n")

    def invoke(self, script, parameters, check=False):
        if not self.powershell:
            self.skipTest("PowerShell is required")
        argv = [self.powershell, "-NoProfile"]
        if os.name == "nt":
            argv += ["-ExecutionPolicy", "Bypass"]
        argv += ["-File", script]
        for name, value in parameters:
            argv += ["-" + name]
            if value is not None:
                argv += [value]
        env = dict(os.environ, GIT_CONFIG_GLOBAL=self.git_config)
        return run(argv, check=check, env=env)

    def prepare_parameters(self, expected=None):
        return [
            ("RemoteUrl", self.fixture.remote),
            ("ExpectedRemoteHead", expected or self.fixture.base_oid),
            ("ReleaseZip", self.fixture.zip_path),
            ("Sha256Sums", self.fixture.sums_path),
            ("Provenance", self.fixture.provenance_path),
            ("AllowLocalTestRemote", None),
        ]

    def prepare_successfully(self):
        result = self.invoke(PREPARE, self.prepare_parameters())
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        line = next(line for line in result.stdout.splitlines()
                    if line.startswith("APPROVED_COMMIT_OID="))
        oid = line.split("=", 1)[1]
        self.assertRegex(oid, r"^[0-9a-f]{40}$")
        remote_oid = run([
            "git", "ls-remote", self.fixture.remote,
            "refs/heads/release/v1.0.27"]).stdout.split()[0]
        self.assertEqual(remote_oid, oid)
        blob = subprocess.run(
            ["git", "--git-dir", self.fixture.remote, "show",
             "refs/heads/release/v1.0.27:windows-crlf.txt"],
            capture_output=True, timeout=30, check=True).stdout
        self.assertEqual(blob, b"line one\r\nline two\r\n")
        return oid

    def test_prepare_pushes_only_new_review_branch_and_refuses_overwrite(self):
        oid = self.prepare_successfully()
        self.assertEqual(
            run(["git", "ls-remote", self.fixture.remote, "HEAD"])
            .stdout.split()[0], self.fixture.base_oid)

        again = self.invoke(PREPARE, self.prepare_parameters())
        self.assertNotEqual(again.returncode, 0)
        self.assertIn("already exists", again.stdout + again.stderr)
        self.assertEqual(
            run(["git", "ls-remote", self.fixture.remote,
                 "refs/heads/release/v1.0.27"]).stdout.split()[0], oid)

    def test_prepare_wrong_expected_head_aborts_without_branch(self):
        wrong = "0" * 40
        result = self.invoke(PREPARE, self.prepare_parameters(wrong))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Remote HEAD mismatch", result.stdout + result.stderr)
        refs = run(["git", "ls-remote", self.fixture.remote,
                    "refs/heads/release/v1.0.27"]).stdout
        self.assertEqual(refs.strip(), "")

    def test_prepare_rejects_dirty_or_unverified_provenance(self):
        with open(self.fixture.provenance_path, encoding="utf-8") as fh:
            original = json.load(fh)
        for field, value, expected in (
                ("source_dirty", True, "source_dirty"),
                ("source_commit", "UNVERIFIED", "source_commit")):
            changed = dict(original)
            changed[field] = value
            with open(self.fixture.provenance_path, "w", encoding="utf-8",
                      newline="\n") as fh:
                json.dump(changed, fh)
                fh.write("\n")
            result = self.invoke(PREPARE, self.prepare_parameters())
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(expected, result.stdout + result.stderr)
            refs = run(["git", "ls-remote", self.fixture.remote,
                        "refs/heads/release/v1.0.27"]).stdout
            self.assertEqual(refs.strip(), "")

    def test_tag_requires_exact_approved_oid_and_refuses_existing_tag(self):
        wrong = self.invoke(TAG, [
            ("RemoteUrl", self.fixture.remote),
            ("ApprovedCommitOid", self.fixture.base_oid),
            ("AllowLocalTestRemote", None),
        ])
        self.assertNotEqual(wrong.returncode, 0)
        self.assertIn("review branch", wrong.stdout + wrong.stderr)
        self.assertEqual(run(["git", "ls-remote", self.fixture.remote,
                              "refs/tags/v1.0.27"]).stdout.strip(), "")

        approved = self.prepare_successfully()
        result = self.invoke(TAG, [
            ("RemoteUrl", self.fixture.remote),
            ("ApprovedCommitOid", approved),
            ("AllowLocalTestRemote", None),
        ])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        peeled = run(["git", "ls-remote", self.fixture.remote,
                      "refs/tags/v1.0.27^{}"]).stdout.split()[0]
        self.assertEqual(peeled, approved)

        again = self.invoke(TAG, [
            ("RemoteUrl", self.fixture.remote),
            ("ApprovedCommitOid", approved),
            ("AllowLocalTestRemote", None),
        ])
        self.assertNotEqual(again.returncode, 0)
        self.assertIn("already exists", again.stdout + again.stderr)

    def test_scripts_have_checked_git_boundary_and_no_direct_main_push(self):
        with open(COMMON, encoding="utf-8") as fh:
            common = fh.read()
        with open(PREPARE, encoding="utf-8") as fh:
            prepare = fh.read()
        with open(TAG, encoding="utf-8") as fh:
            tag = fh.read()
        self.assertIn("function Invoke-CheckedGit", common)
        self.assertIn("function Invoke-CheckedGitGlobal", common)
        self.assertNotIn("refs/heads/main", prepare)
        self.assertNotIn("refs/heads/main", tag)
        self.assertIn('"HEAD:refs/heads/$ReleaseBranch"', prepare)
        self.assertIn('"--force-with-lease=refs/heads/${ReleaseBranch}:"',
                      prepare)
        self.assertIn('"$TagName^{}"', tag)

    def test_common_rejects_windows_invalid_archive_characters(self):
        if not self.powershell:
            self.skipTest("PowerShell is required")
        common = COMMON.replace("'", "''")
        for bad in ('.', 'bad?.txt', 'bad*.txt', 'bad<.txt', 'bad>.txt',
                    'bad".txt', 'bad|.txt', 'bad' + chr(0x7f) + '.txt'):
            value = ("top/" + bad).replace("'", "''")
            command = ". '%s'; Assert-PortableArchivePath -Path '%s' -Kind test" % (
                common, value)
            argv = [self.powershell, "-NoProfile"]
            if os.name == "nt":
                argv += ["-ExecutionPolicy", "Bypass"]
            result = run(argv + ["-Command", command], check=False)
            self.assertNotEqual(result.returncode, 0, bad)
            self.assertIn("non-portable", result.stdout + result.stderr)

    def test_common_rejects_remote_helpers_and_requires_explicit_local_mode(self):
        if not self.powershell:
            self.skipTest("PowerShell is required")
        common = COMMON.replace("'", "''")
        local = self.fixture.remote.replace("'", "''")
        commands = (
            ". '%s'; Assert-SafeRemoteUrl -RemoteUrl 'ext::sh -c evil'" % common,
            ". '%s'; Assert-SafeRemoteUrl -RemoteUrl '%s'" % (common, local),
        )
        for command in commands:
            argv = [self.powershell, "-NoProfile"]
            if os.name == "nt":
                argv += ["-ExecutionPolicy", "Bypass"]
            result = run(argv + ["-Command", command], check=False)
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        allowed = ". '%s'; Assert-SafeRemoteUrl -RemoteUrl '%s' -AllowLocalPath" % (
            common, local)
        result = run(argv + ["-Command", allowed], check=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_common_rejects_archive_expansion_over_budget(self):
        if not self.powershell:
            self.skipTest("PowerShell is required")
        quote = lambda value: value.replace("'", "''")
        destination = os.path.join(self.temp, "budget-extract")
        command = (
            ". '%s'; Expand-AndVerifyReleasePackage -ReleaseZip '%s' "
            "-Sha256Sums '%s' -ProvenanceFile '%s' -Destination '%s' "
            "-Version '1.0.27' -MaxExpandedBytes 1"
            % tuple(map(quote, (COMMON, self.fixture.zip_path,
                                self.fixture.sums_path,
                                self.fixture.provenance_path, destination))))
        argv = [self.powershell, "-NoProfile"]
        if os.name == "nt":
            argv += ["-ExecutionPolicy", "Bypass"]
        result = run(argv + ["-Command", command], check=False)
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("expanded-byte budget", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
