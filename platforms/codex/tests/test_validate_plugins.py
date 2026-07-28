"""Regression tests for portable versus official plugin-validation reporting."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ValidationReportTests(unittest.TestCase):
    def test_report_separates_portable_pass_from_official_availability(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            report = Path(temp) / "validation.json"
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "tools/validate_plugins.py"),
                    "--official-if-available",
                    "--report",
                    str(report),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=120,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(payload["schema"], "solo-suite/plugin-validation-report-v1")
            self.assertEqual(payload["plugin_count"], 19)
            self.assertEqual(payload["portable"], {"failure_count": 0, "status": "pass"})
            self.assertIn(payload["official"]["status"], {"pass", "unavailable"})
            expected = {
                "pass": "pass",
                "unavailable": "portable_pass_official_unavailable",
            }
            self.assertEqual(
                payload["overall_status"], expected[payload["official"]["status"]]
            )

    def test_report_does_not_claim_full_pass_when_official_check_not_requested(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            report = Path(temp) / "validation.json"
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "tools/validate_plugins.py"),
                    "--report",
                    str(report),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=120,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(payload["official"]["status"], "not_requested")
            self.assertEqual(
                payload["overall_status"],
                "portable_pass_official_not_requested",
            )


if __name__ == "__main__":
    unittest.main()
