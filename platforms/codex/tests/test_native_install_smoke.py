"""Regression tests for the native Codex marketplace smoke guard."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

from tools import native_install_smoke as SMOKE


class NativeInstallSmokeTests(unittest.TestCase):
    def test_hashes_are_portable_and_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "nested").mkdir()
            (root / "a.txt").write_bytes(b"a")
            (root / "nested" / "b.txt").write_bytes(b"b")
            first = SMOKE._file_hashes(root)
            second = SMOKE._file_hashes(root)
            self.assertEqual(first, second)
            self.assertEqual(set(first), {"a.txt", "nested/b.txt"})

    def test_duplicate_marketplace_is_reported_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            payload = {
                "marketplaces": [
                    {"name": "solo-suite-codex", "root": str(root)},
                    {"name": "solo-suite-codex", "root": str(root / "old")},
                ]
            }
            completed = subprocess.CompletedProcess(
                ["codex"], 0, json.dumps(payload), ""
            )
            with mock.patch.object(SMOKE, "_run", return_value=completed):
                message = SMOKE._current_collision(
                    "codex", root, "solo-suite-codex"
                )
            self.assertIsNotNone(message)
            self.assertIn("duplicate configured marketplace name", message)
            self.assertTrue(root.is_dir())

    def test_unavailable_cli_is_explicit_and_optional(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            report = Path(temp) / "native.json"
            result = SMOKE.main([
                "--codex", str(Path(temp) / "missing-codex.exe"),
                "--if-available",
                "--report", str(report),
            ])
            self.assertEqual(result, 0)
            payload = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "unavailable")


if __name__ == "__main__":
    unittest.main()
