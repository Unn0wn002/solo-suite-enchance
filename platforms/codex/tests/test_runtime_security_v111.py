"""Regression coverage for v1.0.11 runtime, security, and helper fixes."""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import yaml


ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "plugins" / "site-doctor"


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SECRETS = SITE / "skills/security-review/scripts/scan_secrets.py"
HEADERS = load("check_headers_v111", SITE / "skills/website-audit/scripts/check_headers.py")
LINKS = load("check_links_v111", SITE / "skills/website-audit/scripts/check_links.py")
EMAIL = load("check_email_dns_v111", SITE / "skills/email-deliverability/scripts/check_email_dns.py")
META = load("extract_meta_v111", SITE / "skills/seo-optimization/scripts/extract_meta.py")
TRACKERS = load("scan_trackers_v111", SITE / "skills/compliance-check/scripts/scan_trackers.py")
DEPS = load("check_deps_v111", SITE / "skills/dependency-audit/scripts/check_deps.py")


class SecretScannerRegression(unittest.TestCase):
    def test_complete_secrets_never_reach_output(self):
        secrets = [
            "AKIA" + "A1B2C3D4E5F6G7H8",
            "ghp_" + "a" * 40,
            "xoxb-" + "1234567890-abcdefghij",
            "sk-" + "Z" * 32,
            "eyJ" + "a" * 12 + ".eyJ" + "b" * 12 + "." + "c" * 14,
            "db-" + "password-123456",
        ]
        private_key = (
            "-----BEGIN " + "PRIVATE KEY-----\n" + "M" * 64 +
            "\n-----END " + "PRIVATE KEY-----"
        )
        connection = (
            "postgres" + "://user:" + secrets[5] + "@db.example.test/app"
        )
        with tempfile.TemporaryDirectory() as temp:
            fixture = Path(temp) / "config.txt"
            # GitHub CodeQL alert #2 is audited as "used in tests" rather than
            # hidden by an ineffective source-level query suppression.
            # Intentional synthetic credential-shaped data in an auto-deleted
            # temporary directory; this test verifies that the scanner never
            # emits the plaintext values.  It is not production storage.
            fixture.write_text(
                "\n".join([
                    secrets[0], secrets[1], secrets[2], secrets[3], secrets[4],
                    connection,
                    private_key,
                ]),
                encoding="utf-8",
            )
            result = subprocess.run(
                [sys.executable, str(SECRETS), temp, "--json"],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=30,
            )
        self.assertEqual(result.returncode, 1, "scanner did not report fixtures")
        combined = result.stdout + result.stderr
        for secret in secrets:
            if secret in combined:
                self.fail("scanner leaked a complete fixture secret")
        if private_key in combined:
            self.fail("scanner leaked a complete private-key fixture")
        payload = json.loads(result.stdout)
        self.assertGreaterEqual(len(payload["findings"]), 7)
        allowed = {
            "path", "line", "rule", "preview", "fingerprint",
            "placeholder_hint",
        }
        for finding in payload["findings"]:
            self.assertEqual(set(finding), allowed)
            self.assertRegex(
                finding["fingerprint"], r"^hmac-sha256:[0-9a-f]{64}$"
            )

    def test_scanner_does_not_flag_its_own_rule_source(self):
        module = load("scan_secrets_self", SECRETS)
        self.assertEqual(module.scan_file(str(SECRETS), str(SECRETS.parent), 2_000_000), [])


class InstalledPathRegression(unittest.TestCase):
    def test_launcher_works_outside_plugin_working_directory(self):
        launcher = SITE / "scripts" / "run_helper.py"
        with tempfile.TemporaryDirectory() as outside:
            project = Path(outside) / "project"
            project.mkdir()
            (project / "package.json").write_text(
                '{"dependencies":{"demo":"1.2.3"}}', encoding="utf-8"
            )
            result = subprocess.run(
                [sys.executable, str(launcher), "dependency-audit/check-deps",
                 str(project)],
                cwd=outside, capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=30,
            )
        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
        self.assertIn("Node / npm", result.stdout)

    def test_documented_helper_refs_are_plugin_root_aware(self):
        affected = [
            "website-audit", "compliance-check", "dependency-audit",
            "email-deliverability", "mobile-audit", "security-review",
            "seo-optimization",
        ]
        for name in affected:
            text = (SITE / "skills" / name / "SKILL.md").read_text(encoding="utf-8")
            self.assertNotRegex(text, r"\bpython3\s+scripts[/\\]")
            self.assertIn("<skill-root>", text)
            self.assertNotIn("${CLAUDE_PLUGIN_ROOT}", text)


class ReadOnlyDatabasePolicy(unittest.TestCase):
    def test_audit_sql_blocks_contain_no_write_capable_statement(self):
        path = SITE / "skills/database-audit/references/audit-queries.md"
        text = path.read_text(encoding="utf-8")
        blocks = re.findall(r"```sql\s*(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
        self.assertTrue(blocks)
        forbidden = re.compile(
            r"\b(?:INSERT|UPDATE|DELETE|ALTER|DROP|CREATE|TRUNCATE|GRANT|REVOKE|"
            r"CALL|COPY|ANALYZE|VACUUM|REINDEX)\b|PRAGMA\s+optimize",
            re.IGNORECASE,
        )
        for block in blocks:
            executable = re.sub(r"(?m)^\s*--.*$", "", block)
            self.assertIsNone(
                forbidden.search(executable), "write-capable SQL in audit block"
            )


class HeaderAndLinkRegression(unittest.TestCase):
    def setUp(self):
        HEADERS.results.update({"PASS": 0, "WARN": 0, "FAIL": 0})

    def test_hsts_syntax_and_semantics(self):
        HEADERS.validate_hsts("max-age=31536000; includeSubDomains; preload")
        self.assertEqual(HEADERS.results["PASS"], 1)
        HEADERS.results.update({"PASS": 0, "WARN": 0, "FAIL": 0})
        HEADERS.validate_hsts("max-age=abc; includeSubDomains=1")
        self.assertGreater(HEADERS.results["FAIL"], 0)

    def test_header_cookie_flags_are_structural(self):
        HEADERS.check_cookies(["session=containssecuretext; Path=/"])
        self.assertEqual(HEADERS.results["WARN"], 1)
        HEADERS.results.update({"PASS": 0, "WARN": 0, "FAIL": 0})
        HEADERS.check_cookies([
            "session=value; Path=/; Secure; HttpOnly; SameSite=Lax"
        ])
        self.assertEqual(HEADERS.results["PASS"], 1)

    def test_unrelated_https_redirect_is_failure(self):
        with mock.patch.object(
            HEADERS, "fetch",
            return_value=(301, {"location": "https://unrelated.example/path"}, []),
        ), mock.patch.object(HEADERS, "check_url", return_value=None):
            HEADERS.check_https_redirect("https://example.test")
        self.assertGreater(HEADERS.results["FAIL"], 0)
        self.assertEqual(HEADERS.results["PASS"], 0)

    def test_redirect_timeout_is_never_pass(self):
        with mock.patch.object(
            HEADERS, "fetch", return_value=(None, {"_error": "timeout"}, [])
        ):
            HEADERS.check_https_redirect("https://example.test")
        self.assertEqual(HEADERS.results["PASS"], 0)
        self.assertGreater(HEADERS.results["WARN"] + HEADERS.results["FAIL"], 0)

    def test_link_numeric_options_must_be_positive(self):
        for args in (
            ["https://example.test", "--max-pages", "0"],
            ["https://example.test", "--max-redirects", "0"],
            ["https://example.test", "--delay", "-0.1"],
        ):
            with self.subTest(args=args), self.assertRaises(SystemExit):
                LINKS.parse_args(args)

    def test_mixed_content_can_fail_the_run(self):
        def request(url, method="HEAD", redirect_limit=10):
            if url == "https://example.test":
                return 200, url, 0, "text/html", b'<img src="http://example.test/a.png">'
            return 200, url, 0, "image/png", b""

        with mock.patch.object(LINKS, "check_url", return_value=None), \
             mock.patch.object(LINKS, "request", side_effect=request), \
             mock.patch.object(LINKS.time, "sleep", return_value=None):
            code = LINKS.main([
                "https://example.test", "--max-pages", "1", "--delay", "0",
                "--mixed-content", "fail",
            ])
        self.assertEqual(code, 1)

    def test_long_redirect_chain_fails(self):
        def request(url, method="HEAD", redirect_limit=10):
            return 200, url, 2, "text/html", b"<html></html>"

        with mock.patch.object(LINKS, "check_url", return_value=None), \
             mock.patch.object(LINKS, "request", side_effect=request):
            code = LINKS.main([
                "https://example.test", "--max-pages", "1", "--delay", "0",
                "--max-redirects", "1",
            ])
        self.assertEqual(code, 1)


class ParserRegression(unittest.TestCase):
    def test_dmarc_sp_does_not_masquerade_as_base_policy(self):
        tags, duplicates, invalid = EMAIL.parse_tag_record(
            "v=DMARC1; sp=reject; rua=mailto:x@example.test"
        )
        self.assertEqual(tags.get("sp"), "reject")
        self.assertNotIn("p", tags)
        self.assertFalse(duplicates)
        self.assertFalse(invalid)

    def test_dmarc_version_tag_requires_an_exact_value(self):
        with mock.patch.object(
            EMAIL, "dns_query", return_value=["v=DMARC1evil; p=reject"]
        ):
            EMAIL.results.update({"PASS": 0, "WARN": 0, "FAIL": 0})
            EMAIL.check_dmarc("example.test")
        self.assertGreater(EMAIL.results["FAIL"], 0)

    def test_nested_spf_lookups_are_counted(self):
        records = {
            "b.example": "v=spf1 include:c.example -all",
            "c.example": "v=spf1 exists:%{i}.spf.example -all",
        }
        with mock.patch.object(EMAIL, "_spf_record", side_effect=lambda domain: records.get(domain)):
            count = EMAIL.count_spf_dns_lookups(
                "a.example", "v=spf1 a mx include:b.example -all"
            )
        self.assertEqual(count, 5)

    def test_h1_with_nested_nodes_counts_once(self):
        parser = META.MetaParser()
        parser.feed("<h1>Hello <span>nested</span><em> world</em></h1>")
        self.assertEqual(parser.h1s, ["Hello nested world"])

    def test_tracker_resources_are_deduplicated(self):
        parser = TRACKERS.SrcParser()
        parser.feed(
            '<script src="https://cdn.example/a.js"></script>'
            '<script src="https://cdn.example/a.js"></script>'
            '<a href="https://tracker.example/not-loaded">link</a>'
        )
        self.assertEqual(parser.srcs, ["https://cdn.example/a.js"])

    def test_cookie_flags_are_parsed_not_substring_matched(self):
        cookie = TRACKERS.parse_cookie_header("session=notsecurevalue; Path=/")[0]
        self.assertNotIn("secure", cookie["flags"])
        flagged = TRACKERS.parse_cookie_header(
            "session=value; Path=/; Secure; HttpOnly; SameSite=Lax"
        )[0]
        self.assertEqual(set(flagged["flags"]), {"secure", "httponly", "samesite"})

    def test_numeric_prefix_ranges_are_not_exact_pins(self):
        self.assertEqual(DEPS.pin_kind("1.2.3"), "exact")
        for value in ("1.2", "1.x", "1.2.3 - 2.0.0", ">=1.2.3"):
            with self.subTest(value=value):
                self.assertEqual(DEPS.pin_kind(value), "range")


class SideEffectPolicy(unittest.TestCase):
    def _policy(self, plugin: str, skill: str) -> bool:
        path = ROOT / "plugins" / plugin / "skills" / skill / "agents/openai.yaml"
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return data.get("policy", {}).get("allow_implicit_invocation", True)

    def test_sync_and_browser_submission_are_explicit_only(self):
        for plugin, skill in (
            ("solo", "memory-sync"),
            ("solo", "solo-sync-grafana"),
            ("solo", "solo-sync-obsidian"),
            ("browser", "browser-qa-engineer"),
            ("browser", "browser-form-submit-test"),
        ):
            with self.subTest(skill=skill):
                self.assertFalse(self._policy(plugin, skill))

    def test_sensitive_specialist_skills_are_explicit_only(self):
        for plugin, skill in (
            ("ai", "agent-room-templates"),
            ("gate", "production-readiness-reviewer"),
            ("gate", "quality-gatekeeper"),
            ("site-doctor", "data-migration"),
            ("site-doctor", "database-fix"),
            ("site-doctor", "security-review"),
        ):
            with self.subTest(skill=skill):
                self.assertFalse(self._policy(plugin, skill))

    def test_memory_config_example_stores_env_name_not_token(self):
        text = (ROOT / "plugins/solo/skills/memory-sync/SKILL.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("token_env: GRAFANA_API_TOKEN", text)
        self.assertNotRegex(text, r"(?m)^\s*(?:token|api_key|password):")
        self.assertIn("preview", text.lower())
        self.assertIn("explicit confirmation", text.lower())

    def test_migrated_sync_workflows_keep_preview_and_secret_exclusions(self):
        for skill in ("solo-sync-grafana", "solo-sync-obsidian"):
            text = (
                ROOT / "plugins/solo/skills" / skill / "SKILL.md"
            ).read_text(encoding="utf-8").lower()
            with self.subTest(skill=skill):
                self.assertIn("preview", text)
                self.assertIn("explicit confirmation", text)
                self.assertIn("never", text)
                self.assertIn(".solo/config.md", text)
                self.assertNotIn("url+token", text)

    def test_migrated_form_workflow_is_manual_only(self):
        text = (
            ROOT / "plugins/browser/skills/browser-form-submit-test/SKILL.md"
        ).read_text(encoding="utf-8").lower()
        self.assertIn("manual-only", text)
        self.assertIn("stop before the final", text)
        self.assertIn("synthetic", text)
        self.assertIn("do not trigger real", text)

    def test_release_planning_skills_cannot_execute_production_actions(self):
        for skill, forbidden_action in (
            ("release-deploy-plan", "must not deploy"),
            ("release-rollback-plan", "must not revert a deployment"),
        ):
            text = (
                ROOT / "plugins/release/skills" / skill / "SKILL.md"
            ).read_text(encoding="utf-8").lower()
            with self.subTest(skill=skill):
                self.assertIn("plan only", text)
                self.assertIn(forbidden_action, text)
                self.assertIn("plan approval is not execution authorization", text)
                self.assertIn("distinct explicit user confirmation", text)
                self.assertIn("separately authorized execution workflow", text)


if __name__ == "__main__":
    unittest.main()
