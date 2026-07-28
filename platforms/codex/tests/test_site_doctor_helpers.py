"""Behavior-focused coverage for Site Doctor's standalone audit helpers."""

from __future__ import annotations

import argparse
from contextlib import redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "plugins" / "site-doctor"


def load(name: str, relative: str):
    path = SITE / relative
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SECRETS = load(
    "helper_scan_secrets",
    "skills/security-review/scripts/scan_secrets.py",
)
DEPS = load(
    "helper_check_deps",
    "skills/dependency-audit/scripts/check_deps.py",
)
TRACKERS = load(
    "helper_scan_trackers",
    "skills/compliance-check/scripts/scan_trackers.py",
)
META = load(
    "helper_extract_meta",
    "skills/seo-optimization/scripts/extract_meta.py",
)
HEADERS = load(
    "helper_check_headers",
    "skills/website-audit/scripts/check_headers.py",
)
EMAIL = load(
    "helper_check_email_dns",
    "skills/email-deliverability/scripts/check_email_dns.py",
)


class FakeHeaders(dict):
    def __init__(self, *args, cookies=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.cookies = list(cookies or [])

    def get_all(self, name):
        return self.cookies if name.lower() == "set-cookie" else []


class FakeResponse:
    def __init__(self, status=200, headers=None, body=b""):
        self.status = status
        self.headers = headers or FakeHeaders()
        self.body = body


class SecretScannerBehavior(unittest.TestCase):
    def test_argument_validation_and_sanitized_finding(self):
        self.assertEqual(SECRETS.positive_int("7"), 7)
        with self.assertRaises(argparse.ArgumentTypeError):
            SECRETS.positive_int("0")
        short = SECRETS._finding("a.txt", 2, "test", "tiny")
        long = SECRETS._finding("a.txt", 3, "test", "abcd12345678wxyz")
        self.assertEqual(short["redacted"], "<redacted>")
        self.assertEqual(long["redacted"], "abcd...wxyz")
        self.assertRegex(long["fingerprint"], r"^[0-9a-f]{64}$")

    def test_file_scanning_handles_keys_long_lines_and_size_limits(self):
        token = "ghp_" + "A" * 40
        begin_key = "-" * 5 + "BEGIN " + "PRIVATE KEY" + "-" * 5
        end_key = "-" * 5 + "END " + "PRIVATE KEY" + "-" * 5
        begin_rsa_key = "-" * 5 + "BEGIN RSA " + "PRIVATE KEY" + "-" * 5
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            fixture = root / "settings.txt"
            fixture.write_text(
                "x" * 2001 + "\n"
                f"{begin_key}\n"
                "material\n"
                f"{end_key}\n"
                f"token={token}\n",
                encoding="utf-8",
            )
            findings = SECRETS.scan_file(str(fixture), str(root), 100_000)
            self.assertEqual(
                [item["rule"] for item in findings],
                ["Private key block", "GitHub token"],
            )
            self.assertNotIn(token, json.dumps(findings))
            self.assertEqual(SECRETS.scan_file(str(fixture), str(root), 4), [])

            unfinished = root / "unfinished.pem"
            unfinished.write_text(
                f"{begin_rsa_key}\nmaterial\n",
                encoding="utf-8",
            )
            self.assertEqual(
                SECRETS.scan_file(str(unfinished), str(root), 100_000)[0]["rule"],
                "Private key block",
            )

    def test_tree_skips_generated_directories_and_binary_extensions(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "node_modules").mkdir()
            (root / "node_modules" / "ignored.txt").write_text(
                "password='" + "hidden-value" + "'", encoding="utf-8"
            )
            (root / "image.png").write_bytes(b"not an image")
            (root / "clean.txt").write_text("ordinary content", encoding="utf-8")
            scanned, findings = SECRETS.scan_tree(str(root), 10_000)
        self.assertEqual(scanned, 1)
        self.assertEqual(findings, [])

    def test_human_and_json_modes_have_stable_exit_codes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            clean = io.StringIO()
            with redirect_stdout(clean):
                clean_code = SECRETS.main([str(root)])
            self.assertEqual(clean_code, 3)
            self.assertIn("INCOMPLETE COVERAGE", clean.getvalue())

            (root / "config.txt").write_text(
                "password='" + "runtime-fixture" + "'", encoding="utf-8"
            )
            output = io.StringIO()
            with redirect_stdout(output):
                code = SECRETS.main([str(root), "--json"])
            payload = json.loads(output.getvalue())
            self.assertEqual(code, 1)
            self.assertEqual(payload["findings"][0]["rule"],
                             "Hardcoded password assignment")

        with redirect_stdout(io.StringIO()):
            self.assertEqual(SECRETS.main([str(ROOT / "does-not-exist")]), 2)


class DependencyInventoryBehavior(unittest.TestCase):
    def test_node_inventory_reports_reproducibility_and_tree_risk(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "package.json").write_text(json.dumps({
                "dependencies": {"exact": "1.2.3", "loose": "*"},
                "devDependencies": {"dev": "^2.0.0"},
                "scripts": {"postinstall": "node setup.js"},
            }), encoding="utf-8")
            (root / "package-lock.json").write_text(json.dumps({
                "packages": {"": {}} | {
                    f"node_modules/pkg-{n}": {} for n in range(50)
                }
            }), encoding="utf-8")
            report = []
            DEPS.analyze_node(str(root), report)
        text = "\n".join(report)
        self.assertIn("1 unpinned", text)
        self.assertIn("large tree", text)
        self.assertIn("lifecycle scripts", text)

    def test_node_inventory_handles_missing_lock_and_invalid_json(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            report = []
            DEPS.analyze_node(str(root), report)
            self.assertEqual(report, [])
            (root / "package.json").write_text("{broken", encoding="utf-8")
            self.assertIsNone(DEPS.read_json(str(root / "package.json")))
            DEPS.analyze_node(str(root), report)
            self.assertEqual(report, [])
            (root / "package.json").write_text(
                '{"dependencies":{"demo":"~1.2.3"}}', encoding="utf-8"
            )
            DEPS.analyze_node(str(root), report)
        self.assertIn("NO LOCKFILE", "\n".join(report))

    def test_python_and_other_ecosystems_report_locks_and_next_steps(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "requirements.txt").write_text(
                "# comment\nrequests==2.0.0\nflask>=3\n", encoding="utf-8"
            )
            (root / "uv.lock").write_text("version = 1", encoding="utf-8")
            for manifest, lock in (
                ("Cargo.toml", "Cargo.lock"),
                ("go.mod", "go.sum"),
                ("composer.json", "composer.lock"),
                ("Gemfile", "Gemfile.lock"),
            ):
                (root / manifest).write_text("fixture", encoding="utf-8")
                if manifest != "composer.json":
                    (root / lock).write_text("fixture", encoding="utf-8")
            report = []
            DEPS.analyze_python(str(root), report)
            DEPS.analyze_other(str(root), report)
        text = "\n".join(report)
        self.assertIn("1 exact-pinned, 1 loose", text)
        self.assertIn("lockfile present: uv.lock", text)
        self.assertIn("=== Rust ===", text)
        self.assertIn("Lockfile: MISSING", text)

    def test_main_distinguishes_invalid_empty_and_recognized_projects(self):
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(DEPS.main(str(ROOT / "missing-project")), 2)
        self.assertIn("Not a directory", output.getvalue())

        with tempfile.TemporaryDirectory() as temp:
            empty = io.StringIO()
            with redirect_stdout(empty):
                self.assertEqual(DEPS.main(temp), 0)
            self.assertIn("No recognized dependency manifests", empty.getvalue())
            Path(temp, "pyproject.toml").write_text("[project]", encoding="utf-8")
            recognized = io.StringIO()
            with redirect_stdout(recognized):
                self.assertEqual(DEPS.main(temp), 0)
            self.assertIn("=== Python ===", recognized.getvalue())

    def test_pin_classification_covers_supported_spec_families(self):
        expected = {
            "": "unpinned (*)",
            "latest": "unpinned (*)",
            "X": "unpinned (*)",
            "^1.2.3": "caret (^)",
            "~1.2.3": "tilde (~)",
            "=1.2.3": "exact",
            "git+https://example.test/repo": "non-registry",
            "workspace:*": "non-registry",
            ">=1.0": "range",
        }
        for spec, kind in expected.items():
            with self.subTest(spec=spec):
                self.assertTrue(DEPS.pin_kind(spec).startswith(kind))


class TrackerScannerBehavior(unittest.TestCase):
    def test_fetch_success_http_error_block_and_transport_error(self):
        response = FakeResponse(
            headers=FakeHeaders(
                {"content-type": "text/html"},
                cookies=["session=abc; Secure; HttpOnly; SameSite=Lax"],
            ),
            body=b"<html>ok</html>",
        )
        with mock.patch.object(TRACKERS, "safe_get", return_value=response):
            self.assertEqual(TRACKERS.fetch("https://example.test")[0], 200)
        response.status = 503
        with mock.patch.object(TRACKERS, "safe_get", return_value=response):
            self.assertEqual(TRACKERS.fetch("https://example.test"),
                             (503, response.headers.cookies, ""))
        with mock.patch.object(
            TRACKERS, "safe_get",
            side_effect=TRACKERS.BlockedUrlError("private address"),
        ), redirect_stdout(io.StringIO()):
            self.assertEqual(TRACKERS.fetch("http://127.0.0.1"), (None, [], ""))
        with mock.patch.object(TRACKERS, "safe_get", side_effect=OSError("down")), \
             redirect_stdout(io.StringIO()):
            self.assertEqual(TRACKERS.fetch("https://example.test"),
                             (None, [], ""))

    def test_main_reports_cookie_flags_trackers_and_third_parties(self):
        html = (
            '<script src="https://www.googletagmanager.com/gtm.js"></script>'
            '<script src="https://www.googletagmanager.com/gtm.js#copy"></script>'
            '<img src="//cdn.example.net/pixel.png">'
            '<link rel="stylesheet" href="/local.css">'
            '<object data="https://objects.example.net/widget"></object>'
        )
        output = io.StringIO()
        with mock.patch.object(
            TRACKERS, "fetch",
            return_value=(200, [
                "session=abc; Secure; HttpOnly; SameSite=Lax; Max-Age=60",
                "malformed-cookie",
            ], html),
        ), redirect_stdout(output):
            self.assertEqual(TRACKERS.main("https://example.test"), 1)
        text = output.getvalue()
        self.assertIn("Google Tag Manager  (x1)", text)
        # Untrusted hostnames are fingerprinted rather than echoed into audit
        # output; this keeps tracker reports safe to publish.
        self.assertGreaterEqual(text.count("host-id="), 3)
        self.assertNotIn("cdn.example.net", text)
        self.assertNotIn("objects.example.net", text)
        self.assertIn("persistent-max-age", text)
        self.assertIn("(malformed)", text)

    def test_main_returns_unavailable_when_fetch_is_blocked(self):
        with mock.patch.object(TRACKERS, "fetch", return_value=(None, [], "")):
            self.assertEqual(TRACKERS.main("https://example.test"), 2)


class SeoMetadataBehavior(unittest.TestCase):
    def test_parser_extracts_supported_metadata(self):
        parser = META.MetaParser()
        parser.feed(
            "<title> Example </title>"
            '<meta name="description" content="Summary">'
            '<meta name="robots" content="noindex">'
            '<meta property="og:title" content="Example">'
            '<link rel="canonical" href="https://example.test/canonical">'
            '<h1>Hello <span>world</span></h1>'
            '<a href="/next">next</a>'
            '<script type="application/ld+json">{}</script>'
        )
        self.assertEqual(parser.title, "Example")
        self.assertEqual(parser.description, "Summary")
        self.assertEqual(parser.robots, "noindex")
        self.assertEqual(parser.h1s, ["Hello world"])
        self.assertEqual(parser.links, ["/next"])
        self.assertEqual(parser.jsonld, 1)

    def test_fetch_handles_html_non_html_http_error_and_guard_failures(self):
        html = FakeResponse(
            headers=FakeHeaders({"Content-Type": "text/html",
                                 "X-Robots-Tag": "noindex"}),
            body=b"<title>x</title>",
        )
        with mock.patch.object(META, "safe_get", return_value=html):
            self.assertEqual(META.fetch("https://example.test"),
                             (200, "<title>x</title>", "noindex"))
        html.headers["Content-Type"] = "application/pdf"
        with mock.patch.object(META, "safe_get", return_value=html):
            self.assertEqual(META.fetch("https://example.test"),
                             (None, None, "noindex"))
        html.status = 404
        with mock.patch.object(META, "safe_get", return_value=html):
            self.assertEqual(META.fetch("https://example.test"), (404, None, ""))
        with mock.patch.object(
            META, "safe_get", side_effect=META.BlockedUrlError("blocked")
        ):
            self.assertTrue(str(META.fetch("http://127.0.0.1")[0]).startswith("BLOCKED"))
        with mock.patch.object(META, "safe_get", side_effect=OSError("down")):
            self.assertEqual(META.fetch("https://example.test"), (None, None, ""))

    def test_crawl_reports_duplicates_noindex_and_internal_links(self):
        page = (
            '<title>Shared title</title>'
            '<meta name="description" content="Shared description">'
            '<meta name="robots" content="noindex">'
            '<h1>Heading</h1><a href="/about#team">About</a>'
        )
        calls = {
            "https://example.test": (200, page, ""),
            "https://example.test/about": (200, page, "noarchive"),
        }
        output = io.StringIO()
        argv = ["extract_meta.py", "https://example.test/", "--max-pages", "2",
                "--delay", "0"]
        with mock.patch.object(sys, "argv", argv), \
             mock.patch.object(META, "check_url", return_value=None), \
             mock.patch.object(META, "fetch", side_effect=lambda url: calls[url]), \
             mock.patch.object(META.time, "sleep", return_value=None), \
             redirect_stdout(output):
            self.assertEqual(META.main(), 1)
        text = output.getvalue()
        self.assertIn("DUPLICATE TITLES", text)
        self.assertIn("DUPLICATE DESCRIPTIONS", text)
        self.assertIn("NOINDEX present", text)
        self.assertIn("2 pages", text)

    def test_invalid_and_blocked_start_urls_are_rejected(self):
        with mock.patch.object(sys, "argv", ["extract_meta.py", "not-a-url"]), \
             redirect_stdout(io.StringIO()):
            self.assertEqual(META.main(), 2)
        with mock.patch.object(sys, "argv", ["extract_meta.py", "http://127.0.0.1"]), \
             mock.patch.object(
                 META, "check_url", side_effect=META.BlockedUrlError("private")
             ), redirect_stdout(io.StringIO()):
            self.assertEqual(META.main(), 2)


class HeaderAuditBehavior(unittest.TestCase):
    def setUp(self):
        HEADERS.results.update({"PASS": 0, "WARN": 0, "FAIL": 0})

    def test_fetch_normalizes_headers_and_handles_guard_errors(self):
        response = FakeResponse(
            headers=FakeHeaders({"Server": "Example/1.0"}, cookies=["a=b"])
        )
        with mock.patch.object(HEADERS, "safe_get", return_value=response):
            self.assertEqual(
                HEADERS.fetch("https://example.test"),
                (200, {"server": "Example/1.0"}, ["a=b"]),
            )
        with mock.patch.object(
            HEADERS, "safe_get", side_effect=HEADERS.BlockedUrlError("private")
        ):
            self.assertIn("BLOCKED", HEADERS.fetch("http://127.0.0.1")[1]["_error"])
        with mock.patch.object(HEADERS, "safe_get", side_effect=OSError("down")):
            self.assertIn("OSError", HEADERS.fetch("https://example.test")[1]["_error"])

    def test_redirect_audit_accepts_only_safe_same_host_https_completion(self):
        with mock.patch.object(
            HEADERS, "fetch",
            side_effect=[
                (301, {"location": "https://example.test/path"}, []),
                (200, {}, []),
            ],
        ), mock.patch.object(HEADERS, "check_url", return_value=None):
            HEADERS.check_https_redirect("https://example.test/path")
        self.assertEqual(HEADERS.results["PASS"], 1)

        cases = [
            ("http://example.test", None, "Target is not HTTPS"),
            ("https://example.test", [(200, {}, [])], "does not redirect"),
            ("https://example.test", [(301, {}, [])], "no Location"),
            ("https://example.test", [
                (301, {"location": "https://other.test"}, [])
            ], "unrelated host"),
        ]
        for url, responses, message in cases:
            with self.subTest(message=message):
                HEADERS.results.update({"PASS": 0, "WARN": 0, "FAIL": 0})
                patcher = (mock.patch.object(HEADERS, "fetch", side_effect=responses)
                           if responses is not None else mock.patch.object(
                               HEADERS, "fetch"))
                with patcher, mock.patch.object(HEADERS, "check_url", return_value=None):
                    HEADERS.check_https_redirect(url)
                self.assertEqual(HEADERS.results["FAIL"], 1)

    def test_redirect_audit_warns_for_temporary_or_intermediate_http_hops(self):
        with mock.patch.object(
            HEADERS, "fetch",
            side_effect=[
                (302, {"location": "/middle"}, []),
                (307, {"location": "https://example.test/final"}, []),
                (200, {}, []),
            ],
        ), mock.patch.object(HEADERS, "check_url", return_value=None):
            HEADERS.check_https_redirect("https://example.test/start")
        self.assertEqual(HEADERS.results["WARN"], 1)
        self.assertEqual(HEADERS.results["PASS"], 0)

    def test_hsts_security_caching_and_sensitive_path_branches(self):
        invalid_values = [
            "", "max-age=1;; preload", "max-age=1; max-age=2",
            "includeSubDomains=1", "max-age=abc", "max-age=1; bad value@",
        ]
        for value in invalid_values:
            with self.subTest(value=value):
                before = HEADERS.results["FAIL"]
                HEADERS.validate_hsts(value)
                self.assertGreater(HEADERS.results["FAIL"], before)
        for value, is_https in (("max-age=0", True), ("max-age=10", True),
                                ("max-age=31536000", False)):
            HEADERS.validate_hsts(value, is_https=is_https)

        headers = {
            "strict-transport-security": "max-age=31536000",
            "content-security-policy": "default-src 'self'; frame-ancestors 'none'",
            "x-content-type-options": "nosniff",
            "referrer-policy": "strict-origin",
            "permissions-policy": "camera=()",
            "server": "Example/1.2",
        }
        HEADERS.check_security_headers(headers)
        HEADERS.check_caching_and_compression({
            "content-encoding": "br", "cache-control": "public,max-age=60"
        })
        HEADERS.check_caching_and_compression({})

        with mock.patch.object(
            HEADERS, "fetch",
            side_effect=[
                (200, {"content-type": "text/plain"}, []),
                (200, {"content-type": "text/html"}, []),
                (403, {}, []),
                (500, {}, []),
            ],
        ):
            HEADERS.check_sensitive_paths("https://example.test/page")
        self.assertGreater(HEADERS.results["FAIL"], 0)
        self.assertGreater(HEADERS.results["WARN"], 0)
        self.assertGreater(HEADERS.results["PASS"], 0)

    def test_main_preserves_blocked_and_failed_exit_severity(self):
        with mock.patch.object(
            HEADERS, "check_url",
            side_effect=[HEADERS.BlockedUrlError("private"), None, None],
        ), mock.patch.object(
            HEADERS, "fetch",
            side_effect=[(None, {"_error": "down"}, []), (200, {}, [])],
        ), mock.patch.object(HEADERS, "check_https_redirect"), \
             mock.patch.object(HEADERS, "check_security_headers",
                               side_effect=lambda *_args, **_kwargs: HEADERS.report(
                                   "FAIL", "fixture failure")), \
             mock.patch.object(HEADERS, "check_caching_and_compression"), \
             mock.patch.object(HEADERS, "check_cookies"), \
             mock.patch.object(HEADERS, "check_sensitive_paths"), \
             redirect_stdout(io.StringIO()):
            code = HEADERS.main([
                "http://127.0.0.1", "https://down.example", "https://example.test"
            ])
        self.assertEqual(code, 2)
        self.assertEqual(HEADERS.results["FAIL"], 1)


class EmailDnsBehavior(unittest.TestCase):
    def setUp(self):
        EMAIL.results.update({"PASS": 0, "WARN": 0, "FAIL": 0})

    def test_dns_query_decodes_txt_chunks_and_handles_failures(self):
        payload = {"Answer": [{"data": '"v=spf1 include:a" " -all"'}]}
        response = FakeResponse(body=json.dumps(payload).encode("utf-8"))
        with mock.patch.object(EMAIL, "safe_get", return_value=response):
            self.assertEqual(EMAIL.dns_query("example.test", "TXT"),
                             ["v=spf1 include:a -all"])
        with mock.patch.object(
            EMAIL, "safe_get", side_effect=EMAIL.BlockedUrlError("private")
        ), redirect_stdout(io.StringIO()):
            self.assertEqual(EMAIL.dns_query("example.test", "MX"), [])
        with mock.patch.object(EMAIL, "safe_get", side_effect=ValueError("bad json")), \
             redirect_stdout(io.StringIO()):
            self.assertEqual(EMAIL.dns_query("example.test", "MX"), [])

    def test_spf_cycle_is_bounded_and_policy_outcomes_are_reported(self):
        records = {
            "a.test": "v=spf1 include:b.test -all",
            "b.test": "v=spf1 include:a.test exists:x.test -all",
        }
        with mock.patch.object(
            EMAIL, "_spf_record", side_effect=lambda domain: records.get(domain)
        ):
            self.assertEqual(
                EMAIL.count_spf_dns_lookups("a.test", records["a.test"]), 3
            )

        scenarios = [
            ([], "FAIL"),
            (["v=spf1 +all", "v=spf1 -all"], "FAIL"),
            (["v=spf1 -all"], "PASS"),
            (["v=spf1 ~all"], "WARN"),
            (["v=spf1 a"], "WARN"),
        ]
        for records, expected_level in scenarios:
            with self.subTest(records=records):
                EMAIL.results.update({"PASS": 0, "WARN": 0, "FAIL": 0})
                with mock.patch.object(EMAIL, "dns_query", return_value=records), \
                     mock.patch.object(EMAIL, "count_spf_dns_lookups", return_value=0), \
                     redirect_stdout(io.StringIO()):
                    EMAIL.check_spf("example.test")
                self.assertGreater(EMAIL.results[expected_level], 0)

        EMAIL.results.update({"PASS": 0, "WARN": 0, "FAIL": 0})
        with mock.patch.object(EMAIL, "dns_query", return_value=["v=spf1 ~all"]), \
             mock.patch.object(EMAIL, "count_spf_dns_lookups", return_value=11), \
             redirect_stdout(io.StringIO()):
            EMAIL.check_spf("example.test")
        self.assertGreater(EMAIL.results["FAIL"], 0)

    def test_mx_dmarc_and_dkim_cover_secure_and_broken_configurations(self):
        with mock.patch.object(EMAIL, "dns_query", return_value=["10 mx.example"]), \
             redirect_stdout(io.StringIO()):
            EMAIL.check_mx("example.test")
        with mock.patch.object(EMAIL, "dns_query", return_value=[]), \
             redirect_stdout(io.StringIO()):
            EMAIL.check_mx("example.test")

        dmarc_records = [
            "v=DMARC1; p=reject; p=quarantine",
            "v=DMARC1; p=reject; rua=mailto:reports@example.test",
            "v=DMARC1; p=none",
            "v=DMARC1; p=invalid",
        ]
        for record in dmarc_records:
            with self.subTest(record=record), \
                 mock.patch.object(EMAIL, "dns_query", return_value=[record]), \
                 redirect_stdout(io.StringIO()):
                EMAIL.check_dmarc("example.test")

        with mock.patch.object(EMAIL, "dns_query", return_value=[]), \
             redirect_stdout(io.StringIO()):
            EMAIL.check_dmarc("example.test")

        with redirect_stdout(io.StringIO()):
            EMAIL.check_dkim("example.test", None)
        for records in (["v=DKIM1; p=abc"], ["v=DKIM1; p="], []):
            with self.subTest(records=records), \
                 mock.patch.object(EMAIL, "dns_query", return_value=records), \
                 redirect_stdout(io.StringIO()):
                EMAIL.check_dkim("example.test", "s1")
        self.assertGreater(EMAIL.results["PASS"], 0)
        self.assertGreater(EMAIL.results["WARN"], 0)
        self.assertGreater(EMAIL.results["FAIL"], 0)

    def test_main_normalizes_domain_and_runs_all_checks(self):
        called = []
        argv = ["check_email_dns.py", "@Example.TEST", "--dkim-selector", "s1"]
        with mock.patch.object(sys, "argv", argv), \
             mock.patch.object(EMAIL, "check_mx", side_effect=lambda d: called.append(("mx", d))), \
             mock.patch.object(EMAIL, "check_spf", side_effect=lambda d: called.append(("spf", d))), \
             mock.patch.object(EMAIL, "check_dmarc", side_effect=lambda d: called.append(("dmarc", d))), \
             mock.patch.object(EMAIL, "check_dkim", side_effect=lambda d, s: called.append(("dkim", d, s))), \
             redirect_stdout(io.StringIO()):
            self.assertEqual(EMAIL.main(), 0)
        self.assertEqual(called[-1], ("dkim", "example.test", "s1"))


if __name__ == "__main__":
    unittest.main()
