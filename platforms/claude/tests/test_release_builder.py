"""Release-builder clean-tree and reproducibility guard regressions."""
import base64
import importlib.util
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import unittest
import zipfile
from unittest import mock


REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILDER = os.path.join(REPO, "release", "build_release.py")
SPEC = importlib.util.spec_from_file_location("build_release", BUILDER)
build_release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(build_release)


def git(root, *args):
    return subprocess.run(
        ["git", "-C", root] + list(args), capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=30)


@unittest.skipUnless(shutil.which("git"), "git is required")
class BuilderCleanTree(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="release-builder-state-")
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        with open(os.path.join(self.root, "tracked.txt"), "w",
                  encoding="utf-8", newline="\n") as stream:
            stream.write("committed source\n")
        self.write(".gitignore",
                   b"plugins/demo/from-gitignore.txt\n")
        self.write(".gitattributes",
                   b"* text=auto eol=lf\n*.docx binary\n")
        self.write(".claude-plugin/marketplace.json", json.dumps({
            "metadata": {"version": "9.9.9"}, "plugins": []
        }).encode("utf-8"))
        self.write("plugins/demo/committed.txt", b"committed blob\n")
        self.write("requirements-dev.lock", b"")
        self.write("release/dependency-metadata.json", json.dumps({
            "schema": "solo-suite/dependency-metadata-v1",
            "packages": {}
        }).encode("utf-8"))
        self.write("release/claude-cli/package-lock.json", json.dumps({
            "name": "solo-suite-release-toolchain",
            "version": "1.0.0",
            "lockfileVersion": 3,
            "requires": True,
            "packages": {
                "": {
                    "name": "solo-suite-release-toolchain",
                    "version": "1.0.0",
                    "license": "MIT",
                    "dependencies": {
                        "@anthropic-ai/claude-code": "2.1.205"
                    }
                },
                "node_modules/@anthropic-ai/claude-code": {
                    "version": "2.1.205",
                    "resolved": ("https://registry.npmjs.org/"
                                 "@anthropic-ai/claude-code/-/"
                                 "claude-code-2.1.205.tgz"),
                    "integrity": "sha512-" + base64.b64encode(
                        b"\0" * 64).decode("ascii"),
                    "license": "SEE LICENSE IN README.md",
                    "engines": {"node": ">=22.0.0"}
                }
            }
        }).encode("utf-8"))
        self.assertEqual(git(self.root, "init", "-q").returncode, 0)
        self.assertEqual(
            git(self.root, "config", "user.name", "Builder test").returncode,
            0)
        self.assertEqual(
            git(self.root, "config", "user.email",
                "builder@example.invalid").returncode, 0)
        self.assertEqual(git(self.root, "add", "--all").returncode, 0)
        committed = git(self.root, "commit", "-qm", "fixture")
        self.assertEqual(committed.returncode, 0, committed.stderr)

    def write(self, relative, value=b"generated"):
        path = os.path.join(self.root, *relative.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as stream:
            stream.write(value)

    def commit_market_version(self, version, message="market version"):
        self.write(".claude-plugin/marketplace.json", json.dumps({
            "metadata": {"version": version}, "plugins": []
        }).encode("utf-8"))
        self.assertEqual(git(self.root, "add", "--all").returncode, 0)
        committed = git(self.root, "commit", "-qm", message)
        self.assertEqual(committed.returncode, 0, committed.stderr)

    def test_only_policy_excluded_untracked_outputs_are_ignored(self):
        for relative in (
                "dist/logs/validation.log",
                "tests/__pycache__/test_x.cpython-312.pyc",
                ".pytest_cache/state",
                ".solo/gate-evidence/product.json",
                ".coverage",
                ".coverage.worker.1",
                "scan.json"):
            self.write(relative)
        commit, dirty = build_release.git_state(self.root)
        self.assertRegex(commit, r"^[0-9a-f]{40}$")
        self.assertEqual(dirty, [])

    def test_material_untracked_file_is_still_dirty(self):
        self.write("release-notes-untracked.md")
        _commit, dirty = build_release.git_state(self.root)
        self.assertIn("?? release-notes-untracked.md", dirty)

    def test_tracked_change_is_never_filtered(self):
        with open(os.path.join(self.root, "tracked.txt"), "w",
                  encoding="utf-8", newline="\n") as stream:
            stream.write("changed source\n")
        _commit, dirty = build_release.git_state(self.root)
        self.assertTrue(any("tracked.txt" in line for line in dirty), dirty)

    def test_text_outputs_are_configured_for_lf_stability(self):
        with open(BUILDER, encoding="utf-8") as stream:
            source = stream.read()
        self.assertGreaterEqual(source.count('newline="\\n"'), 3)
        self.assertIn('"timestamp_basis"', source)
        self.assertIn('"timestamp-basis"', source)

    def test_checkout_policy_is_shipped_in_release_zip(self):
        """The Windows byte-stability fix must survive the allowlist."""
        self.assertTrue(build_release.packaged_path(".gitattributes"))
        out = tempfile.mkdtemp(prefix="release-attributes-output-")
        self.addCleanup(shutil.rmtree, out, ignore_errors=True)
        self.assertEqual(build_release.main([
            "--root", self.root, "--out", out]), 0)
        archive = os.path.join(out, "solo-suite-plugin-v9.9.9.zip")
        with zipfile.ZipFile(archive) as zf:
            policy = zf.read(
                "solo-suite-plugin-v9.9.9/.gitattributes")
        self.assertEqual(
            policy, b"* text=auto eol=lf\n*.docx binary\n")

    def test_distributed_coverage_files_cannot_enter_staging(self):
        self.write("plugins/demo/.coverage.worker.1")
        staging = tempfile.mkdtemp(prefix="release-builder-stage-")
        self.addCleanup(shutil.rmtree, staging, ignore_errors=True)
        staged = build_release.stage(self.root, staging)
        self.assertNotIn("plugins/demo/.coverage.worker.1", staged)
        self.assertFalse(os.path.exists(os.path.join(
            staging, "plugins", "demo", ".coverage.worker.1")))

    def test_ignored_files_from_every_git_exclude_source_cannot_ship(self):
        """Regression for SEC-001: ignored content is never a package input."""
        info_exclude = os.path.join(self.root, ".git", "info", "exclude")
        with open(info_exclude, "a", encoding="utf-8", newline="\n") as f:
            f.write("plugins/demo/from-info-exclude.txt\n")
        global_dir = tempfile.mkdtemp(prefix="release-global-excludes-")
        self.addCleanup(shutil.rmtree, global_dir, ignore_errors=True)
        global_excludes = os.path.join(global_dir, "global-ignore")
        with open(global_excludes, "w", encoding="utf-8", newline="\n") as f:
            f.write("plugins/demo/from-global-exclude.txt\n")
        configured = git(self.root, "config", "core.excludesFile",
                         global_excludes)
        self.assertEqual(configured.returncode, 0, configured.stderr)

        ignored = (
            "plugins/demo/from-gitignore.txt",
            "plugins/demo/from-info-exclude.txt",
            "plugins/demo/from-global-exclude.txt",
        )
        for rel in ignored:
            self.write(rel, ("must-not-ship:%s\n" % rel).encode("utf-8"))
            checked = git(self.root, "check-ignore", rel)
            self.assertEqual(checked.returncode, 0, (rel, checked.stderr))

        out = tempfile.mkdtemp(prefix="release-ignored-output-")
        self.addCleanup(shutil.rmtree, out, ignore_errors=True)
        self.assertEqual(build_release.main([
            "--root", self.root, "--out", out]), 0)
        archive = os.path.join(out, "solo-suite-plugin-v9.9.9.zip")
        with zipfile.ZipFile(archive) as zf:
            names = set(zf.namelist())
            for rel in ignored:
                self.assertNotIn("solo-suite-plugin-v9.9.9/" + rel, names)
            committed = zf.read(
                "solo-suite-plugin-v9.9.9/plugins/demo/committed.txt")
        self.assertEqual(committed, b"committed blob\n")
        with open(os.path.join(out, "provenance.json"), encoding="utf-8") as f:
            provenance = json.load(f)
        self.assertFalse(provenance["source_dirty"])
        self.assertEqual(provenance["source_material"],
                         "immutable Git object tree")
        self.assertRegex(provenance["source_tree_oid"],
                         r"^[0-9a-f]{40}(?:[0-9a-f]{24})?$")
        expected_tree = git(self.root, "rev-parse", "HEAD^{tree}").stdout.strip()
        self.assertEqual(provenance["source_tree_oid"], expected_tree)
        self.assertEqual(provenance["packaged_blob_count"], len(names))
        self.assertEqual(provenance["requirements_lock_sha256"],
                         hashlib.sha256(b"").hexdigest())

    def test_staging_reads_committed_blob_not_modified_worktree_file(self):
        path = os.path.join(self.root, "plugins", "demo", "committed.txt")
        with open(path, "wb") as stream:
            stream.write(b"uncommitted replacement\n")
        staging = tempfile.mkdtemp(prefix="release-object-stage-")
        self.addCleanup(shutil.rmtree, staging, ignore_errors=True)
        staged = build_release.stage(self.root, staging)
        self.assertIn("plugins/demo/committed.txt", staged)
        with open(os.path.join(staging, "plugins", "demo",
                               "committed.txt"), "rb") as stream:
            self.assertEqual(stream.read(), b"committed blob\n")

    def test_same_commit_is_byte_deterministic_despite_worktree_content(self):
        target = os.path.join(self.root, "plugins", "demo", "committed.txt")
        outputs = []
        for marker in (b"first live value\n", b"second live value\n"):
            with open(target, "wb") as stream:
                stream.write(marker)
            out = tempfile.mkdtemp(prefix="release-determinism-")
            self.addCleanup(shutil.rmtree, out, ignore_errors=True)
            self.assertEqual(build_release.main([
                "--root", self.root, "--out", out, "--allow-dirty"]), 0)
            outputs.append(out)
        for name in ("solo-suite-plugin-v9.9.9.zip", "SHA256SUMS",
                     "sbom.json", "provenance.json"):
            with open(os.path.join(outputs[0], name), "rb") as first:
                left = first.read()
            with open(os.path.join(outputs[1], name), "rb") as second:
                right = second.read()
            self.assertEqual(left, right, name)

    def test_explicit_historical_commit_selects_its_tree_not_head(self):
        selected = git(self.root, "rev-parse", "HEAD").stdout.strip()
        path = os.path.join(self.root, "plugins", "demo", "committed.txt")
        with open(path, "wb") as stream:
            stream.write(b"newer committed value\n")
        self.assertEqual(git(self.root, "add", "--all").returncode, 0)
        committed = git(self.root, "commit", "-qm", "new head")
        self.assertEqual(committed.returncode, 0, committed.stderr)
        current = git(self.root, "rev-parse", "HEAD").stdout.strip()
        self.assertNotEqual(selected, current)

        out = tempfile.mkdtemp(prefix="release-selected-commit-")
        self.addCleanup(shutil.rmtree, out, ignore_errors=True)
        self.assertEqual(build_release.main([
            "--root", self.root, "--out", out, "--commit", selected]), 0)
        archive = os.path.join(out, "solo-suite-plugin-v9.9.9.zip")
        with zipfile.ZipFile(archive) as zf:
            data = zf.read(
                "solo-suite-plugin-v9.9.9/plugins/demo/committed.txt")
        self.assertEqual(data, b"committed blob\n")
        with open(os.path.join(out, "provenance.json"), encoding="utf-8") as f:
            provenance = json.load(f)
        self.assertEqual(provenance["source_commit"], selected)
        self.assertEqual(provenance["worktree_head_commit"], current)

    def test_marketplace_version_is_validated_before_any_output_path(self):
        malicious = ("../../escaped", "1.2.3/../../escaped", "v1.2.3",
                     "1.2.3-rc.1", "1.2.3\n../../escaped", 123)
        for index, version in enumerate(malicious):
            with self.subTest(version=version):
                self.commit_market_version(version, "invalid version %d" % index)
                parent = tempfile.mkdtemp(prefix="release-version-output-")
                self.addCleanup(shutil.rmtree, parent, ignore_errors=True)
                out = os.path.join(parent, "not-created")
                self.assertEqual(build_release.main([
                    "--root", self.root, "--out", out]), 2)
                self.assertFalse(os.path.exists(out))
                self.assertEqual(os.listdir(parent), [])

    def test_unreleased_remediation_plan_blocks_packaging(self):
        self.write(build_release.UNRELEASED_REMEDIATION_PATH,
                   json.dumps({
                       "schema": "solo-suite/unreleased-remediation-v1",
                       "base_release": "9.9.9",
                       "target_release": "9.9.10",
                   }).encode("utf-8"))
        self.assertEqual(git(self.root, "add", "--all").returncode, 0)
        committed = git(self.root, "commit", "-qm", "unreleased plan")
        self.assertEqual(committed.returncode, 0, committed.stderr)
        parent = tempfile.mkdtemp(prefix="release-unreleased-output-")
        self.addCleanup(shutil.rmtree, parent, ignore_errors=True)
        out = os.path.join(parent, "not-created")
        self.assertEqual(build_release.main([
            "--root", self.root, "--out", out]), 2)
        self.assertFalse(os.path.exists(out))
        self.assertEqual(os.listdir(parent), [])

    def test_ci_release_tag_shape_is_strict_before_git_tag_lookup(self):
        workflow = os.path.join(REPO, ".github", "workflows", "ci.yml")
        with open(workflow, encoding="utf-8") as stream:
            source = stream.read()
        shape = ('[[ ! "$GITHUB_REF_NAME" =~ '
                 '^v[0-9]+\\.[0-9]+\\.[0-9]+$ ]]')
        self.assertIn(shape, source)
        self.assertLess(source.index(shape), source.index(
            'git cat-file -t "refs/tags/$GITHUB_REF_NAME"'))

    def test_git_replacement_ref_cannot_replace_selected_commit(self):
        original = git(self.root, "rev-parse", "HEAD").stdout.strip()
        self.commit_market_version("7.7.7", "malicious replacement tree")
        replacement = git(self.root, "rev-parse", "HEAD").stdout.strip()
        self.assertNotEqual(original, replacement)
        replaced = git(self.root, "replace", original, replacement)
        self.assertEqual(replaced.returncode, 0, replaced.stderr)

        safe_env = os.environ.copy()
        safe_env["GIT_NO_REPLACE_OBJECTS"] = "1"
        reset = subprocess.run(
            ["git", "-C", self.root, "reset", "--hard", original],
            capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=30, env=safe_env)
        self.assertEqual(reset.returncode, 0, reset.stderr)
        unsafe_view = git(
            self.root, "show", "%s:.claude-plugin/marketplace.json" %
            original)
        self.assertIn("7.7.7", unsafe_view.stdout,
                      "fixture must prove the replacement ref is active")

        out = tempfile.mkdtemp(prefix="release-replace-output-")
        self.addCleanup(shutil.rmtree, out, ignore_errors=True)
        with mock.patch.dict(os.environ, {"GIT_NO_REPLACE_OBJECTS": "0"}):
            self.assertEqual(build_release.main([
                "--root", self.root, "--out", out]), 0)
        self.assertTrue(os.path.isfile(os.path.join(
            out, "solo-suite-plugin-v9.9.9.zip")))
        self.assertFalse(os.path.exists(os.path.join(
            out, "solo-suite-plugin-v7.7.7.zip")))
        with open(os.path.join(out, "provenance.json"), encoding="utf-8") as f:
            provenance = json.load(f)
        self.assertEqual(provenance["source_commit"], original)

    def test_git_repository_and_config_environment_overrides_are_ignored(self):
        out = tempfile.mkdtemp(prefix="release-git-env-output-")
        self.addCleanup(shutil.rmtree, out, ignore_errors=True)
        hostile = {
            "GIT_DIR": os.path.join(self.root, "does-not-exist.git"),
            "GIT_WORK_TREE": os.path.dirname(self.root),
            "GIT_OBJECT_DIRECTORY": os.path.join(self.root, "fake-objects"),
            "GIT_CONFIG_COUNT": "1",
            "GIT_CONFIG_KEY_0": "core.repositoryformatversion",
            "GIT_CONFIG_VALUE_0": "999",
        }
        with mock.patch.dict(os.environ, hostile):
            self.assertEqual(build_release.main([
                "--root", self.root, "--out", out]), 0)
        self.assertTrue(os.path.isfile(os.path.join(
            out, "solo-suite-plugin-v9.9.9.zip")))

    def test_locked_claude_toolchain_is_derived_and_bound(self):
        out = tempfile.mkdtemp(prefix="release-toolchain-output-")
        self.addCleanup(shutil.rmtree, out, ignore_errors=True)
        with mock.patch.dict(os.environ,
                             {"SOLO_NODE_VERSION": "v22.99.0"}):
            self.assertEqual(build_release.main([
                "--root", self.root, "--out", out]), 0)
        lock_path = os.path.join(
            self.root, "release", "claude-cli", "package-lock.json")
        with open(lock_path, "rb") as stream:
            expected_digest = hashlib.sha256(stream.read()).hexdigest()
        with open(os.path.join(out, "provenance.json"), encoding="utf-8") as f:
            provenance = json.load(f)
        self.assertEqual(provenance["claude_cli_package_lock_sha256"],
                         expected_digest)
        self.assertEqual(
            provenance["locked_release_toolchain"]["claude_cli"]["version"],
            "2.1.205")
        self.assertEqual(
            provenance["locked_release_toolchain"][
                "node_engine_requirement"], ">=22.0.0")
        material = next(item for item in provenance["materials"]
                        if item["uri"] ==
                        "release/claude-cli/package-lock.json")
        self.assertEqual(material["digest"]["sha256"], expected_digest)
        with open(os.path.join(out, "sbom.json"), encoding="utf-8") as f:
            sbom = json.load(f)
        cli = next(component for component in sbom["components"]
                   if component["name"] == "@anthropic-ai/claude-code")
        self.assertEqual(cli["version"], "2.1.205")
        self.assertEqual(cli["hashes"][0]["alg"], "SHA-512")
        node = next(tool for tool in sbom["metadata"]["tools"]
                    if tool["name"] == "node")
        self.assertEqual(node["version"], "v22.99.0")

    def test_mismatched_claude_lock_is_rejected_before_output(self):
        lock_path = os.path.join(
            self.root, "release", "claude-cli", "package-lock.json")
        with open(lock_path, encoding="utf-8") as stream:
            lock = json.load(stream)
        lock["packages"][""]["dependencies"][
            "@anthropic-ai/claude-code"] = "2.1.204"
        self.write("release/claude-cli/package-lock.json",
                   json.dumps(lock).encode("utf-8"))
        self.assertEqual(git(self.root, "add", "--all").returncode, 0)
        committed = git(self.root, "commit", "-qm", "bad cli lock")
        self.assertEqual(committed.returncode, 0, committed.stderr)
        parent = tempfile.mkdtemp(prefix="release-bad-lock-")
        self.addCleanup(shutil.rmtree, parent, ignore_errors=True)
        out = os.path.join(parent, "not-created")
        self.assertEqual(build_release.main([
            "--root", self.root, "--out", out]), 2)
        self.assertFalse(os.path.exists(out))

    def test_sbom_components_have_validated_license_metadata(self):
        requirement = (
            "demo-package==1.2.3 \\\n"
            "    --hash=sha256:" + "a" * 64 + "\n")
        self.write("requirements-dev.lock", requirement.encode("utf-8"))
        self.write("release/dependency-metadata.json", json.dumps({
            "schema": "solo-suite/dependency-metadata-v1",
            "packages": {
                "demo-package": {
                    "license": "MIT",
                    "direct": True,
                    "depends_on": []
                }
            }
        }).encode("utf-8"))
        self.assertEqual(git(self.root, "add", "--all").returncode, 0)
        committed = git(self.root, "commit", "-qm", "dependency metadata")
        self.assertEqual(committed.returncode, 0, committed.stderr)
        out = tempfile.mkdtemp(prefix="release-sbom-metadata-")
        self.addCleanup(shutil.rmtree, out, ignore_errors=True)
        self.assertEqual(build_release.main([
            "--root", self.root, "--out", out]), 0)
        with open(os.path.join(out, "sbom.json"), encoding="utf-8") as fh:
            sbom = json.load(fh)
        python_components = [component for component in sbom["components"]
                             if component["purl"].startswith("pkg:pypi/")]
        self.assertEqual(len(python_components), 1)
        self.assertEqual(python_components[0]["licenses"],
                         [{"license": {"id": "MIT"}}])
        properties = {p["name"]: p["value"]
                      for p in sbom["metadata"]["properties"]}
        self.assertRegex(properties["requirements-lock-sha256"],
                         r"^[0-9a-f]{64}$")

    def _write_index_entry(self, mode, oid, relative):
        result = git(self.root, "update-index", "--add", "--cacheinfo",
                     "%s,%s,%s" % (mode, oid, relative))
        self.assertEqual(result.returncode, 0, result.stderr)
        committed = git(self.root, "commit", "-qm", "non-regular fixture")
        self.assertEqual(committed.returncode, 0, committed.stderr)

    def test_tracked_symlink_is_rejected_without_dereferencing(self):
        blob = subprocess.run(
            ["git", "-C", self.root, "hash-object", "-w", "--stdin"],
            input=b"../../outside.txt", capture_output=True, timeout=30)
        self.assertEqual(blob.returncode, 0, blob.stderr)
        oid = blob.stdout.decode("ascii").strip()
        self._write_index_entry("120000", oid, "plugins/demo/escape")
        staging = tempfile.mkdtemp(prefix="release-link-stage-")
        self.addCleanup(shutil.rmtree, staging, ignore_errors=True)
        with self.assertRaisesRegex(build_release.ReleaseBuildError,
                                    "tracked symlink"):
            build_release.stage(self.root, staging)

    def test_tracked_gitlink_is_rejected_as_non_regular(self):
        head = git(self.root, "rev-parse", "HEAD").stdout.strip()
        self._write_index_entry("160000", head, "plugins/vendor")
        staging = tempfile.mkdtemp(prefix="release-gitlink-stage-")
        self.addCleanup(shutil.rmtree, staging, ignore_errors=True)
        with self.assertRaisesRegex(build_release.ReleaseBuildError,
                                    "non-regular entry"):
            build_release.stage(self.root, staging)


if __name__ == "__main__":
    unittest.main()
