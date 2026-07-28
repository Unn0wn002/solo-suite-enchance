"""Claude animation audit skill and scanner regression checks."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SITE_DOCTOR = ROOT / "plugins" / "site-doctor"
SKILL = SITE_DOCTOR / "skills" / "animation-design-audit"
SCANNER = SKILL / "scripts" / "animation_check.py"


def run_scanner(files: dict[str, str]) -> subprocess.CompletedProcess[str]:
    with tempfile.TemporaryDirectory() as temp_dir:
        project = Path(temp_dir)
        for relative_path, content in files.items():
            target = project / relative_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        # The parent decodes as UTF-8, so the child must ENCODE as UTF-8.
        # PYTHONUTF8=1 alone is not enough: PYTHONIOENCODING takes precedence
        # over it, and the CP1252 CI leg sets PYTHONIOENCODING=cp1252 in the
        # environment this dict inherits. The scanner then wrote cp1252 (an
        # em dash as 0x97), the reader thread raised UnicodeDecodeError,
        # stdout came back as None, and the assertion died with
        # "unsupported operand type(s) for +: 'NoneType' and 'str'" --
        # masking the real result. Pin both, and never fail on a stray byte.
        # Same pattern as tests/test_installed_cwd.py.
        return subprocess.run(
            [sys.executable, str(SCANNER), str(project)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env={**os.environ, "PYTHONUTF8": "1",
                 "PYTHONIOENCODING": "utf-8"},
            check=False,
        )


class AnimationPluginTests(unittest.TestCase):
    def test_skill_command_and_scanner_exist(self) -> None:
        self.assertTrue((SKILL / "SKILL.md").is_file())
        self.assertTrue(SCANNER.is_file())
        self.assertTrue((SITE_DOCTOR / "commands" / "animation.md").is_file())

    def test_css_reduced_motion_is_project_level_evidence(self) -> None:
        result = run_scanner({
            "app.js": (
                'import gsap from "gsap";\n'
                'const ctx = gsap.context(() => gsap.to(".card", {x: 10}));\n'
                "ctx.revert();\n"
            ),
            "styles.css": (
                "@media (prefers-reduced-motion: reduce) {\n"
                "  *, *::before, *::after { animation: none !important; }\n"
                "}\n"
            ),
        })
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("[OK] prefers-reduced-motion", result.stdout)

    def test_warning_only_scan_returns_gap_exit_code(self) -> None:
        result = run_scanner({
            "app.js": (
                'import gsap from "gsap";\n'
                'const ctx = gsap.context(() => gsap.to(".card", {width: 10}));\n'
                "ctx.revert();\n"
            ),
            "styles.css": "@media (prefers-reduced-motion: reduce) {}\n",
        })
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("[WARN]", result.stdout)
        self.assertNotIn("[FAIL]", result.stdout)

    def test_overwrite_is_not_lifecycle_cleanup(self) -> None:
        result = run_scanner({
            "app.js": (
                'import gsap from "gsap";\n'
                'gsap.to(".card", {x: 10, overwrite: "auto"});\n'
            ),
            "styles.css": "@media (prefers-reduced-motion: reduce) {}\n",
        })
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("[FAIL]", result.stdout)
        self.assertIn("no cleanup signal", result.stdout)

    def test_no_gsap_remains_unverified(self) -> None:
        result = run_scanner({
            "styles.css": "@media (prefers-reduced-motion: reduce) {}\n",
        })
        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
        self.assertIn("[UNVERIFIED] no GSAP usage detected", result.stdout)


if __name__ == "__main__":
    unittest.main()
