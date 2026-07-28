"""Structural checks for the updated Codex Site Doctor cheat sheet."""

from __future__ import annotations

import json
from pathlib import Path
import re
import unittest
import xml.etree.ElementTree as ET
import zipfile


ROOT = Path(__file__).resolve().parents[1]
DOCX = ROOT / "site-doctor-cheatsheet.docx"
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


class Cheatsheet(unittest.TestCase):
    def setUp(self):
        self.archive = zipfile.ZipFile(DOCX)
        self.addCleanup(self.archive.close)

    def test_every_xml_part_is_well_formed_and_comments_are_removed(self):
        names = self.archive.namelist()
        for name in names:
            if name.endswith((".xml", ".rels")):
                with self.subTest(name=name):
                    ET.fromstring(self.archive.read(name))
        self.assertFalse(any("comment" in name.lower() for name in names))
        content_types = self.archive.read("[Content_Types].xml").decode("utf-8")
        self.assertNotIn("comments", content_types.lower())

    def test_content_uses_codex_invocations_and_current_version(self):
        document = ET.fromstring(self.archive.read("word/document.xml"))
        text = "".join(node.text or "" for node in document.iter(W + "t"))
        self.assertIn("v1.0.27", text)
        self.assertIn("site-doctor@solo-suite-codex", text)
        self.assertIn("<resolved-plugin-root>/scripts/run_helper.py", text)
        self.assertNotIn("v3.3.0", text)
        self.assertNotIn("site-doctor@personal", text)
        self.assertNotIn("owner/repository", text)
        self.assertNotIn("slash command", text.lower())
        self.assertNotIn("Claude", text)
        self.assertIsNone(
            re.search(r"(?<![\w/])/[a-z][a-z0-9-]*:[a-z][a-z0-9-]*", text)
        )
        mapping = json.loads((ROOT / "command-map.json").read_text(encoding="utf-8"))
        expected = {
            entry["codex_invocation"]
            for entry in mapping
            if entry["plugin"] == "site-doctor"
        }
        missing = sorted(invocation for invocation in expected if invocation not in text)
        self.assertEqual(missing, [])

    def test_metadata_and_trailing_structure_are_clean(self):
        core = ET.fromstring(self.archive.read("docProps/core.xml"))
        core_text = " ".join(node.text or "" for node in core.iter())
        self.assertIn("Solo Suite", core_text)
        self.assertIn("Codex", core_text)

        document = ET.fromstring(self.archive.read("word/document.xml"))
        paragraphs = []
        for paragraph in document.iter(W + "p"):
            paragraphs.append(
                "".join(node.text or "" for node in paragraph.iter(W + "t")).strip()
            )
        trailing_empty = 0
        for text in reversed(paragraphs):
            if text:
                break
            trailing_empty += 1
        self.assertLessEqual(trailing_empty, 1)


if __name__ == "__main__":
    unittest.main()
