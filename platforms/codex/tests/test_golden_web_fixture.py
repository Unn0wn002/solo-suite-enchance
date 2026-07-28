"""Real local frontend/API/database journey used by the Full Team E2E proof."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from tests.fixtures.golden_web.app import GoldenWebApp, is_valid_email


def request_json(url: str, email: str):
    body = json.dumps({"email": email}).encode("utf-8")
    request = Request(
        url + "/api/signup", data=body, method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read())
    except HTTPError as exc:
        return exc.code, json.loads(exc.read())


class GoldenWebJourney(unittest.TestCase):
    def test_accessible_frontend_api_validation_and_database_integrity(self):
        self.assertTrue(is_valid_email("a" * 241 + "@example.test"))
        self.assertFalse(is_valid_email("a" * 242 + "@example.test"))
        for invalid in (
            "not-an-email",
            "@example.test",
            "dev@example.",
            "dev@@example.test",
            "dev @example.test",
            "a@" + "a." * 100_000 + "@",
        ):
            self.assertFalse(is_valid_email(invalid), invalid[:80])
        with tempfile.TemporaryDirectory() as temp:
            with GoldenWebApp(Path(temp)) as app:
                with urlopen(app.base_url + "/", timeout=5) as response:
                    html = response.read().decode("utf-8")
                    self.assertEqual(response.status, 200)
                    self.assertIn("default-src 'self'", response.headers["Content-Security-Policy"])
                for marker in (
                    '<html lang="en">', 'name="viewport"', '<main>',
                    '<label for="email">', 'aria-live="polite"',
                    '<script src="/app.js" defer>',
                ):
                    self.assertIn(marker, html)
                with urlopen(app.base_url + "/app.js", timeout=5) as response:
                    self.assertIn("addEventListener", response.read().decode("utf-8"))
                with urlopen(app.base_url + "/api/health", timeout=5) as response:
                    self.assertEqual(json.loads(response.read()), {"status": "ok"})
                self.assertEqual(request_json(app.base_url, "not-an-email")[0], 400)
                self.assertEqual(request_json(app.base_url, "dev@example.test")[0], 201)
                self.assertEqual(request_json(app.base_url, "DEV@example.test")[0], 409)
                self.assertEqual(app.count_users(), 1)


if __name__ == "__main__":
    unittest.main()
