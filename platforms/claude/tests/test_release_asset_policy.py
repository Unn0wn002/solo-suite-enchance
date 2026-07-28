"""Regression tests for the fixed canonical-release asset contract.

These tests inspect the reviewed workflow and README.  The privileged signer
and publisher intentionally do not check out or execute repository helpers, so
their allowlists must remain visible inline in ``ci.yml``.
"""
import json
import os
import re
import unittest


REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKFLOW = os.path.join(REPO, ".github", "workflows", "ci.yml")
README = os.path.join(REPO, "README.md")
CONTRIBUTING = os.path.join(REPO, "CONTRIBUTING.md")
CHANGELOG = os.path.join(REPO, "CHANGELOG.md")
INVENTORY = os.path.join(REPO, "release", "previous-release-inventory.json")


def read(path):
    with open(path, encoding="utf-8") as stream:
        return stream.read()


def job_block(workflow, name):
    match = re.search(
        r"(?ms)^  %s:\n.*?(?=^  [A-Za-z0-9_-]+:\n|\Z)" % re.escape(name),
        workflow,
    )
    if match is None:
        raise AssertionError("workflow job is missing: %s" % name)
    return match.group(0)


class ReleaseAssetPolicy(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = read(WORKFLOW)
        cls.build = job_block(cls.workflow, "release-build")
        cls.signer = job_block(cls.workflow, "release-sign")
        cls.publisher = job_block(cls.workflow, "release-publish")

    def test_reviewed_baseline_matches_previous_release_inventory(self):
        with open(INVENTORY, encoding="utf-8") as stream:
            inventory = json.load(stream)
        match = re.search(
            r'(?m)^  RELEASE_BASELINE_VERSION: "([0-9]+\.[0-9]+\.[0-9]+)"$',
            self.workflow,
        )
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1), "1.0.26")
        self.assertEqual(match.group(1), inventory["release"])
        self.assertIn(
            'test "$INVENTORY_VERSION" = "$RELEASE_BASELINE_VERSION"',
            self.build,
        )

    def test_allowlist_graph_is_fixed_at_seven_eight_sixteen_eighteen(self):
        for block in (self.signer, self.publisher):
            self.assertIn("expected-release-manifest-payloads.txt", block)
            self.assertIn("expected-unsigned-release-assets.txt", block)
            self.assertIn("expected-signed-inner-assets.txt", block)
            self.assertIn("expected-final-release-assets.txt", block)
            for count in ("7", "8", "16", "18"):
                self.assertIn(')" = "%s"' % count, block)

        versioned = (
            "changed_files_v${RELEASE_BASELINE_VERSION}_to_v${CURRENT_VERSION}.txt",
            "solo-suite-plugin-v${CURRENT_VERSION}.zip",
            "validation-logs-v${CURRENT_VERSION}.zip",
        )
        for name in versioned:
            self.assertGreaterEqual(self.workflow.count(name), 3, name)

        for obsolete_threshold in ('-gt 6', '-gt 7', '-gt 12'):
            self.assertNotIn(obsolete_threshold, self.signer + self.publisher)

    def test_manifests_are_built_from_expected_names_without_cycles(self):
        self.assertIn(
            'done < "$RUNNER_TEMP/expected-release-manifest-payloads.txt"',
            self.build,
        )
        self.assertIn(
            'done < "$RUNNER_TEMP/expected-signed-inner-assets.txt"',
            self.signer,
        )
        self.assertIn(
            "rm -f dist/SIGNED-BUNDLE-SHA256SUMS "
            "dist/SIGNED-BUNDLE-SHA256SUMS.sigstore.json",
            self.signer,
        )
        self.assertNotIn(
            "find dist -type f ! -name '*.sigstore.json'", self.signer
        )
        self.assertNotIn("mapfile -d '' assets", self.publisher)
        self.assertIn(
            'while IFS= read -r rel; do assets+=("dist/$rel"); '
            'done < "$EXPECTED"',
            self.publisher,
        )

    def test_exact_sets_are_checked_at_every_release_boundary(self):
        for marker in (
            "canonical-unsigned-release",
            "unsigned transfer differs from the fixed eight-asset allowlist",
        ):
            self.assertIn(marker, self.build)
        for marker in (
            "signer input differs from the fixed eight-asset allowlist",
            "fixed sixteen-file inner bundle",
            "fixed eighteen-asset allowlist",
        ):
            self.assertIn(marker, self.signer)
        for marker in (
            "publisher-input",
            "publisher-upload",
            "remote-draft-download",
            "public-release-download",
        ):
            self.assertIn(marker, self.publisher)

    def test_publisher_authenticates_outer_manifest_before_using_checksums(self):
        outer_verify = "cosign verify-blob dist/SIGNED-BUNDLE-SHA256SUMS"
        outer_check = (
            "sha256sum --check --strict SIGNED-BUNDLE-SHA256SUMS"
        )
        release_verify = "cosign verify-blob dist/RELEASE-SHA256SUMS"
        release_check = "sha256sum --check --strict RELEASE-SHA256SUMS"
        self.assertLess(self.publisher.index(outer_verify),
                        self.publisher.index(outer_check))
        self.assertLess(self.publisher.index(outer_check),
                        self.publisher.index(release_verify))
        self.assertLess(self.publisher.index(release_verify),
                        self.publisher.index(release_check))
        self.assertIn("assert_manifest_names dist/SIGNED-BUNDLE-SHA256SUMS",
                      self.publisher)
        self.assertIn("assert_manifest_names dist/RELEASE-SHA256SUMS",
                      self.publisher)

    def test_public_release_is_redownloaded_and_fully_reverified(self):
        promote = (
            'gh release edit "$GITHUB_REF_NAME" --repo "$GH_REPO" '
            '--draft=false'
        )
        self.assertEqual(self.publisher.count("gh release download"), 2)
        self.assertLess(self.publisher.index("remote-draft-download"),
                        self.publisher.index(promote))
        self.assertLess(self.publisher.index(promote),
                        self.publisher.index('PUBLIC_DIR="$(mktemp -d'))
        self.assertLess(self.publisher.index('PUBLIC_DIR="$(mktemp -d'),
                        self.publisher.index("public-release-download"))
        self.assertIn("isDraft,isImmutable,isPrerelease,tagName,assets",
                      self.publisher)
        self.assertIn('if len(actual) != 18:', self.publisher)
        self.assertIn('if release["isImmutable"] is not expected_immutable:',
                      self.publisher)
        self.assertIn('if release["isPrerelease"] is not False:',
                      self.publisher)
        self.assertIn('if release["tagName"] != sys.argv[5]:', self.publisher)
        self.assertIn(
            '"$RUNNER_TEMP/draft-release.json" true false remote-draft',
            self.publisher,
        )
        self.assertIn(
            '"$RUNNER_TEMP/public-release.json" false true public-release',
            self.publisher,
        )
        self.assertIn(
            '"$RUNNER_TEMP/final-public-release.json" false true '
            'final-public-release',
            self.publisher,
        )
        self.assertNotIn("assert release[", self.publisher)

    def test_publisher_preflights_repository_immutability_controls(self):
        preflight = self.publisher.index(
            "Require immutable releases and protected release tags"
        )
        artifact_download = self.publisher.index(
            "Download the exact signed release artifact"
        )
        self.assertLess(preflight, artifact_download)
        for marker in (
            "RELEASE_SETTINGS_AUDIT_TOKEN",
            'repos/$GH_REPO/immutable-releases',
            'repos/$GH_REPO/rulesets?includes_parents=true&targets=tag&per_page=100',
            'settings.get("enabled") is not True',
            'ruleset.get("target") != "tag"',
            'ruleset.get("enforcement") != "active"',
            'accepted_includes = {"refs/tags/v*", "~ALL"}',
            'required_rules = {"update", "deletion"}',
            'excludes != []',
            'ruleset.get("bypass_actors") != []',
            'ruleset.get("current_user_can_bypass") != "never"',
        ):
            self.assertIn(marker, self.publisher)
        self.assertIn("no active, no-bypass tag ruleset protects", self.publisher)
        self.assertIn("GH_TOKEN: ${{ secrets.RELEASE_SETTINGS_AUDIT_TOKEN }}",
                      self.publisher)
        self.assertIn("GH_TOKEN: ${{ github.token }}", self.publisher)
        preflight_block = self.publisher.split(
            "Require immutable releases and protected release tags", 1
        )[1].split("Download the exact signed release artifact", 1)[0]
        self.assertGreaterEqual(preflight_block.count("gh api --method GET"), 3)
        for mutating_method in ("POST", "PUT", "PATCH", "DELETE"):
            self.assertNotIn("--method " + mutating_method, preflight_block)

    def test_annotated_tag_is_api_peeled_at_publication_boundaries(self):
        pre_create = self.publisher.index(
            "verify_api_annotated_tag_peel pre-create"
        )
        create = self.publisher.index('gh release create "$GITHUB_REF_NAME"')
        pre_promotion = self.publisher.index(
            "verify_api_annotated_tag_peel pre-promotion"
        )
        promote = self.publisher.index(
            'gh release edit "$GITHUB_REF_NAME" --repo "$GH_REPO" --draft=false'
        )
        post_public = self.publisher.index(
            "verify_api_annotated_tag_peel post-public"
        )
        final_metadata = self.publisher.index(
            '"$RUNNER_TEMP/final-public-release.json" false true '
            'final-public-release'
        )
        self.assertLess(pre_create, create)
        self.assertLess(pre_promotion, promote)
        self.assertLess(final_metadata, post_public)
        self.assertEqual(
            self.publisher.count("verify_api_annotated_tag_peel "), 3
        )
        self.assertIn("git/ref/tags/$GITHUB_REF_NAME", self.publisher)
        self.assertIn("git/tags/$tag_object_sha", self.publisher)
        self.assertIn("peeled tag target differs from the event commit",
                      self.publisher)

    def test_signed_provenance_is_bound_to_event_commit_before_and_after_upload(self):
        self.assertGreaterEqual(
            self.publisher.count(
                'provenance.get("source_commit") != expected_commit'
            ),
            2,
        )
        self.assertGreaterEqual(
            self.publisher.count(
                'provenance.get("version") != expected_version'
            ),
            2,
        )
        self.assertGreaterEqual(
            self.publisher.count(
                'provenance.get("source_dirty") is not False'
            ),
            2,
        )
        self.assertIn("verify_provenance_binding dist publisher-upload",
                      self.publisher)
        self.assertIn('verify_provenance_binding "$root" "$label"',
                      self.publisher)


class ReadmeReleaseVerification(unittest.TestCase):
    def test_readme_uses_the_same_exact_contract_and_trust_order(self):
        readme = read(README)
        section = readme.split("### Verify a published release", 1)[1].split(
            "\n---", 1
        )[0]
        self.assertIn("TAG=v1.0.27", section)
        self.assertIn("BASELINE=v1.0.26", section)
        self.assertIn("Run this verifier on GNU/Linux or Git Bash", section)
        self.assertIn("Stock macOS utilities do not support", section)
        self.assertIn('test "$(wc -l < "$VERIFY_TMP/final-assets")" = 18',
                      section)
        self.assertIn("release does not contain the exact 18 assets", section)
        outer = section.index("cosign verify-blob SIGNED-BUNDLE-SHA256SUMS")
        outer_check = section.index(
            "sha256sum --check --strict SIGNED-BUNDLE-SHA256SUMS"
        )
        release = section.index("cosign verify-blob RELEASE-SHA256SUMS")
        self.assertLess(outer, outer_check)
        self.assertLess(outer_check, release)
        self.assertIn("manifest_names SIGNED-BUNDLE-SHA256SUMS", section)
        self.assertIn("manifest_names RELEASE-SHA256SUMS", section)
        self.assertIn('for payload in "${payloads[@]}"', section)
        self.assertNotIn("done < RELEASE-SHA256SUMS", section)
        self.assertIn("neither checksum graph is circular", section)
        self.assertIn("--json isDraft,isImmutable,isPrerelease,tagName", section)
        self.assertIn("GitHub release is not immutable", section)
        self.assertIn("git/ref/tags/$TAG", section)
        self.assertIn("git/tags/$TAG_OBJECT_SHA", section)
        provenance = section.index('python - provenance.json "$TAG_COMMIT"')
        payload_signatures = section.index('for payload in "${payloads[@]}"')
        self.assertLess(payload_signatures, provenance)
        self.assertIn(
            'provenance.get("source_commit") != sys.argv[2]', section
        )
        self.assertIn("signed provenance commit differs from peeled tag target",
                      section)

    def test_operator_docs_require_repository_side_release_controls(self):
        contributing = read(CONTRIBUTING)
        for marker in (
            "Before pushing any `v*` tag",
            "GitHub Immutable Releases",
            "active tag ruleset",
            "`refs/tags/v*` (or `~ALL`)",
            "both tag updates and tag deletions",
            "no bypass actors",
            "RELEASE_SETTINGS_AUDIT_TOKEN",
            "Administration: write",
            "`current_user_can_bypass: never`",
            "every request in that step uses `GET`",
            "The workflow never changes",
            "repository settings",
        ):
            self.assertIn(marker, contributing)

    def test_changelog_describes_new_controls_without_rewriting_old_release_state(self):
        changelog = read(CHANGELOG)
        current = changelog.split("## 1.0.27", 1)[1].split("\n## ", 1)[0]
        self.assertNotIn("immutable v1.0.25", current.lower())
        self.assertNotIn("8-payload", current)
        for marker in (
            "exact 7-payload, 8-unsigned-file",
            "GitHub Immutable Releases",
            "no-bypass `refs/tags/v*` ruleset",
            "Administration-write audit token",
            "GET-only settings checks",
            "API-peels the annotated tag",
            "authenticated, signed",
            "upload, draft-download, and public-download boundaries",
        ):
            self.assertIn(marker, current)


if __name__ == "__main__":
    unittest.main()
