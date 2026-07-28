"""Release checksum, SBOM, provenance, and reproducibility checks."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import zipfile


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_COMMIT_EPOCH = 1_700_000_000
HISTORICAL_DIGEST = (
    "b691905f8ade4c2fb7e0084a46f537c9be8d7b2bf0f4d160c38c5e930aed1d43"
)
CANONICAL_DIGEST = (
    "7dde7bbe44e7534e3f1890ddb1c5feba5554d60127c4dd7ef2095b31cafb03aa"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def package_module():
    path = ROOT / "tools/package_release.py"
    name = "package_release_v127"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


PACKAGE = package_module()


def run_git(root: Path, *arguments: str, env=None) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *arguments],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        timeout=60,
    )
    if result.returncode:
        raise AssertionError(
            f"git {' '.join(arguments)} failed:\n{result.stdout}{result.stderr}"
        )
    return result.stdout.strip()


def write_fixture(root: Path) -> None:
    manifest = root / "plugins/demo/.codex-plugin/plugin.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        json.dumps({"name": "demo", "version": "1.0.12", "license": "MIT"})
        + "\n",
        encoding="utf-8",
    )
    skill = root / "plugins/demo/skills/example/SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("---\nname: example\ndescription: Example.\n---\n", encoding="utf-8")
    (root / "command-map.json").write_text("{}\n", encoding="utf-8")
    (root / "requirements-dev.txt").write_text(
        "PyYAML==6.0.2\n"
        "coverage==7.6.12\n"
        "jsonschema==4.23.0\n"
        "attrs==25.3.0\n"
        "jsonschema-specifications==2024.10.1\n"
        "referencing==0.36.2\n"
        "rpds-py==0.27.1\n"
        "typing_extensions==4.15.0\n",
        encoding="utf-8",
    )
    (root / "requirements-audit.txt").write_text(
        "-c requirements-dev.txt\n"
        "pip==26.1.2\n"
        "pip-audit==2.10.1\n",
        encoding="utf-8",
    )
    (root / "payload.txt").write_text("portable payload\n", encoding="utf-8")


def initialize_git(root: Path) -> str:
    run_git(root, "init", "--quiet")
    run_git(root, "config", "user.name", "Release Test")
    run_git(root, "config", "user.email", "release-test@example.invalid")
    run_git(root, "config", "core.autocrlf", "false")
    run_git(root, "add", "--all")
    env = os.environ.copy()
    date = f"@{FIXTURE_COMMIT_EPOCH} +0000"
    env.update({"GIT_AUTHOR_DATE": date, "GIT_COMMITTER_DATE": date})
    run_git(root, "commit", "--quiet", "-m", "fixture", env=env)
    return run_git(root, "rev-parse", "HEAD")


def read_zip_json(path: Path, relative: str) -> dict:
    member = f"{PACKAGE.FOLDER}/{relative}"
    with zipfile.ZipFile(path) as archive:
        return json.loads(archive.read(member).decode("utf-8"))


class ReleaseArtifacts(unittest.TestCase):
    def test_canonical_and_historical_materials_are_pinned(self):
        self.assertEqual(PACKAGE.CANONICAL_SOURCE_SHA256, CANONICAL_DIGEST)
        self.assertEqual(PACKAGE.HISTORICAL_SOURCE_SHA256, HISTORICAL_DIGEST)
        provenance = json.loads(
            (ROOT / "RELEASE-PROVENANCE.json").read_text(encoding="utf-8")
        )
        self.assertEqual(provenance["record_kind"], "unbound-source-template")
        self.assertEqual(provenance["build_type"], "unbound-source-template")
        self.assertIsNone(provenance["build_timestamp"])
        self.assertIsNone(provenance["source_date_epoch"])
        self.assertIsNone(provenance["source_git_commit"])
        self.assertIsNone(provenance["source_git_dirty"])
        self.assertEqual(provenance["validation_state"], "unbound")
        source_sbom = json.loads(
            (ROOT / "SBOM.spdx.json").read_text(encoding="utf-8")
        )
        self.assertTrue(
            source_sbom["documentNamespace"].endswith("unbound-source-template")
        )
        source_packages = {item["name"] for item in source_sbom["packages"]}
        self.assertTrue({"pip", "pip-audit"}.issubset(source_packages))
        self.assertEqual(
            provenance["validation_commands"],
            provenance["installed_package_validation_commands"],
        )
        self.assertTrue(any(
            "unittest discover" in command
            for command in provenance["source_checkout_validation_commands"]
        ))
        self.assertFalse(any(
            "unittest discover" in command
            for command in provenance["installed_package_validation_commands"]
        ))
        materials = {item["role"]: item for item in provenance["materials"]}
        self.assertNotIn("release-source", materials)
        canonical = materials["canonical-parity-source"]
        self.assertEqual(canonical["uri"], PACKAGE.CANONICAL_SOURCE_NAME)
        self.assertEqual(canonical["digest"]["sha256"], CANONICAL_DIGEST)
        self.assertTrue(canonical["required_for_validation"])
        historical = materials["historical-source-reference"]
        self.assertEqual(historical["uri"], PACKAGE.HISTORICAL_SOURCE_NAME)
        self.assertEqual(historical["digest"]["sha256"], HISTORICAL_DIGEST)
        self.assertFalse(historical["required_for_validation"])
        self.assertNotIn("UNAVAILABLE", json.dumps(materials))

    def test_optional_historical_archive_verification_is_strict(self):
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp) / "legacy.zip"
            archive.write_bytes(b"historical fixture")
            expected = sha256(archive)
            with mock.patch.object(PACKAGE, "HISTORICAL_SOURCE_SHA256", expected):
                PACKAGE.verify_historical_archive(archive)
            with self.assertRaisesRegex(RuntimeError, "digest mismatch"):
                PACKAGE.verify_historical_archive(archive)
            with self.assertRaisesRegex(RuntimeError, "does not exist"):
                PACKAGE.verify_historical_archive(Path(temp) / "missing.zip")

    def test_checked_in_canonical_source_is_exact_and_matches_target(self):
        archive = ROOT / "parity/artifacts" / PACKAGE.CANONICAL_SOURCE_NAME
        reference = json.loads(
            (ROOT / "parity/canonical-source.json").read_text(encoding="utf-8")
        )
        self.assertEqual(reference["archive_sha256"], CANONICAL_DIGEST)
        self.assertEqual(sha256(archive), CANONICAL_DIGEST)
        self.assertEqual(
            archive.with_suffix(archive.suffix + ".sha256")
            .read_text(encoding="utf-8")
            .split()[0],
            CANONICAL_DIGEST,
        )
        PACKAGE.verify_canonical_source_archive(archive, ROOT)

    def test_validated_build_fails_without_git_even_with_source_date_epoch(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "source"
            root.mkdir()
            write_fixture(root)
            output = Path(temp) / "release.zip"
            with self.assertRaisesRegex(RuntimeError, "requires a Git checkout"):
                PACKAGE.build_release(
                    output,
                    "validated",
                    root=root,
                    environ={"SOURCE_DATE_EPOCH": str(FIXTURE_COMMIT_EPOCH)},
                )
            self.assertFalse(output.exists())

    def test_preflight_without_git_is_explicit_and_never_claims_a_commit(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "source"
            root.mkdir()
            write_fixture(root)
            result = PACKAGE.build_release(
                Path(temp) / "preflight.zip", "preflight", root=root,
                environ={"SOURCE_DATE_EPOCH": str(FIXTURE_COMMIT_EPOCH)},
            )
            provenance = read_zip_json(result.output, "RELEASE-PROVENANCE.json")
            self.assertEqual(
                provenance["record_kind"], "generated-build-provenance"
            )
            self.assertIsNone(provenance["source_git_commit"])
            self.assertIsNone(provenance["source_git_dirty"])
            self.assertIn("non-publication preflight", provenance["source_identity_note"])
            self.assertNotIn("UNAVAILABLE", json.dumps(provenance))

    def test_strict_provenance_writer_rejects_non_clean_identity(self):
        contexts = (
            PACKAGE.BuildContext(
                None, False, FIXTURE_COMMIT_EPOCH,
                "2023-11-14T22:13:20Z", (2023, 11, 14, 22, 13, 20), None,
            ),
            PACKAGE.BuildContext(
                "a" * 40, True, FIXTURE_COMMIT_EPOCH,
                "2023-11-14T22:13:20Z", (2023, 11, 14, 22, 13, 20), ROOT,
            ),
        )
        for context in contexts:
            with self.subTest(commit=context.commit, dirty=context.dirty):
                with tempfile.TemporaryDirectory() as temp:
                    with self.assertRaisesRegex(
                        RuntimeError, "requires an exact clean Git commit"
                    ):
                        PACKAGE.write_provenance(Path(temp), "validated", context)

    def test_validated_build_fails_for_dirty_git_tree(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "source"
            root.mkdir()
            write_fixture(root)
            initialize_git(root)
            (root / "payload.txt").write_text("dirty payload\n", encoding="utf-8")
            output = Path(temp) / "release.zip"
            with self.assertRaisesRegex(RuntimeError, "clean Git working tree"):
                PACKAGE.build_release(output, "ci", root=root, environ={})
            self.assertFalse(output.exists())

    def test_clean_validated_build_requires_canonical_source(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "source"
            root.mkdir()
            write_fixture(root)
            initialize_git(root)
            with self.assertRaisesRegex(RuntimeError, "requires --canonical-source-archive"):
                PACKAGE.build_release(Path(temp) / "release.zip", "validated", root=root)

    def test_same_commit_is_byte_reproducible_across_clean_clones(self):
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            source = temp_root / "source"
            source.mkdir()
            write_fixture(source)
            commit = initialize_git(source)
            clone = temp_root / "clone"
            subprocess.run(
                ["git", "clone", "--quiet", "--no-local", str(source), str(clone)],
                check=True,
                capture_output=True,
                timeout=60,
            )
            info = clone / ".git/info"
            info.mkdir(parents=True, exist_ok=True)
            (info / "attributes").write_text(
                "payload.txt export-ignore\n", encoding="utf-8"
            )
            original_blob = run_git(clone, "rev-parse", "HEAD:payload.txt")
            replacement = subprocess.run(
                ["git", "-C", str(clone), "hash-object", "-w", "--stdin"],
                input=b"locally replaced payload\n",
                capture_output=True,
                check=True,
                timeout=60,
            ).stdout.decode("ascii").strip()
            run_git(clone, "replace", original_blob, replacement)
            canonical_archive = temp_root / "canonical-source.zip"
            with mock.patch.object(
                PACKAGE, "verify_canonical_source_archive"
            ) as canonical_verifier:
                first = PACKAGE.build_release(
                    temp_root / "first.zip", "ci", root=source, environ={},
                    canonical_source_archive=canonical_archive,
                )
                second = PACKAGE.build_release(
                    temp_root / "second.zip", "ci", root=clone, environ={},
                    canonical_source_archive=canonical_archive,
                )
            supplied_archive = temp_root / "legacy-anywhere.zip"
            with mock.patch.object(
                PACKAGE, "verify_historical_archive"
            ) as verifier:
                with mock.patch.object(PACKAGE, "verify_canonical_source_archive"):
                    verified = PACKAGE.build_release(
                        temp_root / "verified.zip", "ci", root=source, environ={},
                        canonical_source_archive=canonical_archive,
                        verify_source_archive=supplied_archive,
                    )
            verifier.assert_called_once_with(supplied_archive)
            self.assertEqual(canonical_verifier.call_count, 2)

            self.assertEqual(first.digest, second.digest)
            self.assertEqual(first.output.read_bytes(), second.output.read_bytes())
            self.assertEqual(first.digest, verified.digest)
            self.assertEqual(first.output.read_bytes(), verified.output.read_bytes())
            self.assertEqual(run_git(source, "status", "--porcelain=v1"), "")
            clean_env = os.environ.copy()
            clean_env["GIT_NO_REPLACE_OBJECTS"] = "1"
            self.assertEqual(
                run_git(clone, "status", "--porcelain=v1", env=clean_env), ""
            )

            provenance = read_zip_json(first.output, "RELEASE-PROVENANCE.json")
            self.assertEqual(
                provenance["record_kind"], "generated-build-provenance"
            )
            self.assertEqual(provenance["source_git_commit"], commit)
            self.assertFalse(provenance["source_git_dirty"])
            self.assertEqual(provenance["source_date_epoch"], FIXTURE_COMMIT_EPOCH)
            self.assertEqual(provenance["validation_state"], "ci")
            self.assertEqual(
                provenance["materials"][0]["digest"]["sha256"],
                CANONICAL_DIGEST,
            )
            self.assertEqual(
                provenance["materials"][2]["digest"]["gitCommit"], commit
            )

            release = read_zip_json(first.output, "RELEASE.json")
            self.assertFalse(release["source_archive_required_for_build"])
            self.assertTrue(release["source_archive_required_for_validation"])
            self.assertEqual(release["source_archive_sha256"], CANONICAL_DIGEST)
            self.assertEqual(
                release["historical_source_archive_sha256"], HISTORICAL_DIGEST
            )
            sbom = read_zip_json(first.output, "SBOM.spdx.json")
            self.assertEqual(sbom["creationInfo"]["created"], provenance["build_timestamp"])
            with zipfile.ZipFile(second.output) as archive:
                self.assertEqual(
                    archive.read(f"{PACKAGE.FOLDER}/payload.txt"),
                    (source / "payload.txt").read_bytes(),
                )

    def test_output_cannot_overwrite_or_escape_into_tracked_source(self):
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            source = temp_root / "source"
            source.mkdir()
            write_fixture(source)
            tracked = source / "dist/tracked.zip"
            tracked.parent.mkdir(parents=True)
            tracked.write_bytes(b"tracked source artifact")
            initialize_git(source)

            with self.assertRaisesRegex(RuntimeError, "outside the source root"):
                PACKAGE.build_release(source / "release.zip", "ci", root=source)
            with self.assertRaisesRegex(RuntimeError, "must not overwrite tracked"):
                PACKAGE.build_release(tracked, "ci", root=source)
            self.assertEqual(tracked.read_bytes(), b"tracked source artifact")
            with self.assertRaisesRegex(RuntimeError, "must use a .zip suffix"):
                PACKAGE.build_release(temp_root / "release.tar", "ci", root=source)

            allowed = source / "dist/untracked-release.zip"
            with mock.patch.object(PACKAGE, "verify_canonical_source_archive"):
                result = PACKAGE.build_release(
                    allowed, "ci", root=source,
                    canonical_source_archive=temp_root / "canonical-source.zip",
                )
            self.assertTrue(result.output.is_file())

    def test_committed_paths_must_be_portable_and_collision_free(self):
        seen: set[str] = set()
        self.assertEqual(
            PACKAGE._portable_git_path(b"docs/Guide.md", seen).as_posix(),
            "docs/Guide.md",
        )
        for raw, fragment in (
            (b"docs/guide.MD", "collision"),
            (b"CON.txt", "not portable"),
            (b"../escape.txt", "unsafe"),
            (b"bad\\name.txt", "unsafe"),
        ):
            with self.subTest(path=raw):
                with self.assertRaisesRegex(RuntimeError, fragment):
                    PACKAGE._portable_git_path(raw, seen)

    def test_source_date_epoch_controls_metadata_and_zip_time(self):
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            source = temp_root / "source"
            source.mkdir()
            write_fixture(source)
            initialize_git(source)
            override = 1_800_000_000
            with mock.patch.object(PACKAGE, "verify_canonical_source_archive"):
                result = PACKAGE.build_release(
                    temp_root / "release.zip", "validated", root=source,
                    canonical_source_archive=temp_root / "canonical-source.zip",
                    environ={"SOURCE_DATE_EPOCH": str(override)},
                )
            provenance = read_zip_json(result.output, "RELEASE-PROVENANCE.json")
            self.assertEqual(provenance["source_date_epoch"], override)
            with zipfile.ZipFile(result.output) as archive:
                dates = {item.date_time for item in archive.infolist()}
            self.assertEqual(dates, {result.context.zip_time})

    def test_zip_root_is_canonicalized_before_relative_paths(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "source"
            root.mkdir()
            (root / "alias-anchor").mkdir()
            (root / "payload.txt").write_bytes(b"portable payload\n")
            lexical_alias = root / "alias-anchor" / ".."
            output = Path(temp) / "release.zip"

            PACKAGE.build_zip(
                lexical_alias,
                output,
                (2026, 7, 11, 0, 0, 0),
            )

            with zipfile.ZipFile(output) as archive:
                self.assertEqual(
                    archive.read(f"{PACKAGE.FOLDER}/payload.txt"),
                    b"portable payload\n",
                )

    def test_generated_checksums_and_sbom_cover_staged_release(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "source"
            root.mkdir()
            write_fixture(root)
            commit = initialize_git(root)
            context = PACKAGE.resolve_build_context(root, "ci", {})
            # Windows runners may expose the same temp directory through an
            # 8.3 alias (for example ``RUNNER~1``) while os.walk returns the
            # long path.  Resolve both sides before computing relative paths.
            stage = (Path(temp) / "stage").resolve()
            PACKAGE.stage_source(root, stage, context)
            PACKAGE.generate_metadata(stage, "ci", context)

            for name in (
                "RELEASE.json",
                "RELEASE-PROVENANCE.json",
                "RELEASE-CHECKSUMS.txt",
                "SBOM.spdx.json",
            ):
                self.assertNotIn(b"\r", (stage / name).read_bytes(), name)

            declared = {}
            for line in (stage / "RELEASE-CHECKSUMS.txt").read_text(
                encoding="utf-8"
            ).splitlines():
                digest, relative = line.split("  ", 1)
                target = stage / relative
                self.assertTrue(target.is_file(), relative)
                self.assertEqual(sha256(target), digest, relative)
                declared[relative] = digest
            actual = {
                path.resolve().relative_to(stage).as_posix()
                for path in PACKAGE.included_files(stage)
                if path.name != "RELEASE-CHECKSUMS.txt"
            }
            self.assertEqual(set(declared), actual)

            sbom = json.loads((stage / "SBOM.spdx.json").read_text(encoding="utf-8"))
            ids = [item["SPDXID"] for item in sbom["packages"]]
            self.assertEqual(len(ids), len(set(ids)))
            packages = {item["name"]: item for item in sbom["packages"]}
            expected_licenses = {
                "PyYAML": "MIT",
                "coverage": "Apache-2.0",
                "jsonschema": "MIT",
                "attrs": "MIT",
                "jsonschema-specifications": "MIT",
                "referencing": "MIT",
                "rpds-py": "MIT",
                "typing_extensions": "PSF-2.0",
                "pip": "MIT",
                "pip-audit": "Apache-2.0",
            }
            self.assertTrue({"demo", *expected_licenses}.issubset(packages))
            for name, license_id in expected_licenses.items():
                self.assertEqual(packages[name]["licenseDeclared"], license_id)
            provenance = json.loads(
                (stage / "RELEASE-PROVENANCE.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                provenance["record_kind"], "generated-build-provenance"
            )
            self.assertEqual(provenance["source_git_commit"], commit)


if __name__ == "__main__":
    unittest.main()
