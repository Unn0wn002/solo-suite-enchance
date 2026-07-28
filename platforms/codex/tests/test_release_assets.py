"""Tests for draft-release asset byte verification."""

from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from tools.verify_release_assets import ReleaseAssetError, verify_release_assets


class ReleaseAssetVerificationTests(unittest.TestCase):
    def _fixture(self):
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        paths = []
        assets = []
        for name, content in (("package.zip", b"package"), ("package.zip.sha256", b"sidecar\n")):
            path = root / name
            path.write_bytes(content)
            paths.append(path)
            assets.append(
                {
                    "id": len(assets) + 1,
                    "name": name,
                    "size": len(content),
                    "state": "uploaded",
                    "digest": f"sha256:{hashlib.sha256(content).hexdigest()}",
                }
            )
        release = {"tag_name": "v1.0.27", "draft": True, "assets": assets}
        downloaded = {asset["id"]: path.read_bytes() for asset, path in zip(assets, paths)}
        return temp, paths, release, downloaded

    def test_verifies_exact_set_sizes_and_downloaded_bytes(self):
        temp, paths, release, downloaded = self._fixture()
        self.addCleanup(temp.cleanup)
        verified = verify_release_assets(
            "owner/repo",
            "v1.0.27",
            paths,
            fetch_release=lambda endpoint: release,
            fetch_asset=lambda _repo, asset_id: downloaded[asset_id],
        )
        self.assertEqual([item[0] for item in verified], ["package.zip", "package.zip.sha256"])

    def test_rejects_missing_or_unexpected_assets(self):
        temp, paths, release, downloaded = self._fixture()
        self.addCleanup(temp.cleanup)
        release["assets"].pop()
        with self.assertRaisesRegex(ReleaseAssetError, "missing"):
            verify_release_assets(
                "owner/repo",
                "v1.0.27",
                paths,
                fetch_release=lambda _endpoint: release,
                fetch_asset=lambda _repo, asset_id: downloaded[asset_id],
            )

    def test_rejects_mutated_remote_bytes(self):
        temp, paths, release, downloaded = self._fixture()
        self.addCleanup(temp.cleanup)
        downloaded[1] = b"tamper!"
        with self.assertRaisesRegex(ReleaseAssetError, "digest mismatch"):
            verify_release_assets(
                "owner/repo",
                "v1.0.27",
                paths,
                fetch_release=lambda _endpoint: release,
                fetch_asset=lambda _repo, asset_id: downloaded[asset_id],
            )

    def test_requires_draft_release(self):
        temp, paths, release, downloaded = self._fixture()
        self.addCleanup(temp.cleanup)
        release["draft"] = False
        with self.assertRaisesRegex(ReleaseAssetError, "draft"):
            verify_release_assets(
                "owner/repo",
                "v1.0.27",
                paths,
                fetch_release=lambda _endpoint: release,
                fetch_asset=lambda _repo, asset_id: downloaded[asset_id],
            )

    def test_rejects_missing_or_unsupported_advertised_digest(self):
        for advertised in (None, "md5:deadbeef"):
            with self.subTest(advertised=advertised):
                temp, paths, release, downloaded = self._fixture()
                self.addCleanup(temp.cleanup)
                release["assets"][0]["digest"] = advertised
                with self.assertRaisesRegex(
                    ReleaseAssetError, "missing a sha256 advertised digest"
                ):
                    verify_release_assets(
                        "owner/repo",
                        "v1.0.27",
                        paths,
                        fetch_release=lambda _endpoint: release,
                        fetch_asset=lambda _repo, asset_id: downloaded[asset_id],
                    )


if __name__ == "__main__":
    unittest.main()
