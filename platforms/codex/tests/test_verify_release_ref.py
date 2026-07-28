"""Regression tests for release-tag/default-branch commit binding."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "verify_release_ref", ROOT / "tools/verify_release_ref.py"
)
assert SPEC is not None and SPEC.loader is not None
VERIFY = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = VERIFY
SPEC.loader.exec_module(VERIFY)


COMMIT = "a" * 40
TAG_OBJECT = "b" * 40


class ReleaseRefVerification(unittest.TestCase):
    def test_lightweight_tag_default_branch_and_local_head_must_match(self):
        payloads = {
            "repos/example/project/git/ref/tags/v1.0.27": {
                "object": {"type": "commit", "sha": COMMIT}
            },
            "repos/example/project/commits/main": {"sha": COMMIT},
        }
        VERIFY.verify_release_ref(
            "example/project",
            "v1.0.27",
            COMMIT,
            "main",
            check_local_head=True,
            fetch=payloads.__getitem__,
            read_local_head=lambda: COMMIT,
        )

    def test_annotated_tag_is_peeled_to_its_commit(self):
        payloads = {
            "repos/example/project/git/ref/tags/v1.0.27": {
                "object": {"type": "tag", "sha": TAG_OBJECT}
            },
            f"repos/example/project/git/tags/{TAG_OBJECT}": {
                "object": {"type": "commit", "sha": COMMIT}
            },
            "repos/example/project/commits/main": {"sha": COMMIT},
        }
        VERIFY.verify_release_ref(
            "example/project",
            "v1.0.27",
            COMMIT,
            "main",
            fetch=payloads.__getitem__,
        )

    def test_tag_branch_and_checkout_drift_fail_closed(self):
        other = "c" * 40
        baseline = {
            "repos/example/project/git/ref/tags/v1.0.27": {
                "object": {"type": "commit", "sha": COMMIT}
            },
            "repos/example/project/commits/main": {"sha": COMMIT},
        }
        cases = (
            (
                "tag",
                {
                    **baseline,
                    "repos/example/project/git/ref/tags/v1.0.27": {
                        "object": {"type": "commit", "sha": other}
                    },
                },
                lambda: COMMIT,
                "remote tag",
            ),
            (
                "branch",
                {
                    **baseline,
                    "repos/example/project/commits/main": {"sha": other},
                },
                lambda: COMMIT,
                "default branch",
            ),
            ("checkout", baseline, lambda: other, "checked-out HEAD"),
        )
        for label, payloads, local, message in cases:
            with self.subTest(label=label):
                with self.assertRaisesRegex(VERIFY.ReleaseRefError, message):
                    VERIFY.verify_release_ref(
                        "example/project",
                        "v1.0.27",
                        COMMIT,
                        "main",
                        check_local_head=True,
                        fetch=payloads.__getitem__,
                        read_local_head=local,
                    )

    def test_non_commit_tag_targets_and_annotation_cycles_are_rejected(self):
        invalid = {
            "repos/example/project/git/ref/tags/v1.0.27": {
                "object": {"type": "tree", "sha": TAG_OBJECT}
            }
        }
        with self.assertRaisesRegex(VERIFY.ReleaseRefError, "unsupported"):
            VERIFY.peel_tag("example/project", "v1.0.27", invalid.__getitem__)

        cycle = {
            "repos/example/project/git/ref/tags/v1.0.27": {
                "object": {"type": "tag", "sha": TAG_OBJECT}
            },
            f"repos/example/project/git/tags/{TAG_OBJECT}": {
                "object": {"type": "tag", "sha": TAG_OBJECT}
            },
        }
        with self.assertRaisesRegex(VERIFY.ReleaseRefError, "cycle"):
            VERIFY.peel_tag("example/project", "v1.0.27", cycle.__getitem__)


if __name__ == "__main__":
    unittest.main()
