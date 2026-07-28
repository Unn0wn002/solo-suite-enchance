#!/usr/bin/env python3
"""Apply the minimal Codex v1.0.27 OOXML edits to the release cheat sheet."""

from __future__ import annotations

import argparse
import re
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path


COMMAND = re.compile(r"(?<![<\w])/([a-z][a-z0-9-]*):([a-z][a-z0-9-]*)")


def patch_document(xml: str) -> str:
    xml = (
        xml.replace("v1.0.26", "v1.0.27")
        .replace("v1.0.12", "v1.0.27")
        .replace("v1.0.11", "v1.0.27")
        .replace("v1.0.10", "v1.0.27")
        .replace("v3.3.0", "v1.0.27")
    )
    xml = xml.replace("Claude", "Codex")
    replacements = {
        "site-doctor Command &amp; Prompt Cheat Sheet":
            "site-doctor Skill &amp; Prompt Cheat Sheet",
        "Codex Code": "Codex",
        "26 skills, 24 slash commands, and 8 helper scripts":
            "26 specialist skills, 24 command-derived skills, and 8 helper scripts",
        "Skills trigger automatically when your request matches; the slash commands "
        "are quick shortcuts into them.":
            "Specialist skills can trigger on matching work; command-derived skills "
            "require explicit $name invocation.",
        "This sheet lists every command, what it does, and a ready-to-paste prompt "
        "for each.":
            "This sheet lists every command-derived skill, what it does, and a "
            "ready-to-paste prompt for each.",
        "From a local clone of the plugin folder, inside Codex:":
            "From the Solo Suite Codex repository, add the marketplace with the "
            "Codex CLI:",
        "/plugin marketplace add /path/to/site-doctor":
            "codex plugin marketplace add /path/to/solo-suite-codex",
        "/plugin install site-doctor@site-doctor":
            "codex plugin add site-doctor@solo-suite-codex",
        "/reload-plugins": "Restart the Codex app, then start a new task.",
        "Or, if you push the repo to GitHub:":
            "For another verified local marketplace clone:",
        "/plugin marketplace add your-username/site-doctor":
            "codex plugin marketplace add /verified/path/to/solo-suite-codex",
        "Prefer no plugin? ": "Standalone use: ",
        "Copy any folder from ": "Skills with helper scripts must remain inside ",
        " into ": " because they use ",
        "~/.claude/skills/": "plugins/site-doctor/lib/url_guard.py",
        " (global) or ": "; do not copy only the skill folder to ",
        ".claude/skills/": "~/.codex/skills/",
        " (per project).": " unless its shared dependencies are packaged too.",
        "Slash Commands — Quick Reference":
            "Command-derived Skills — Quick Reference",
        "Type these in Codex after installing. Arguments in [brackets] are optional "
        "— if you omit them, Codex asks.":
            "Invoke these explicit skills with $. Arguments in [brackets] are "
            "optional — if omitted, Codex asks.",
    }
    for old, new in replacements.items():
        xml = xml.replace(old, new)
    xml = xml.replace("slash commands", "command-derived skills")
    xml = xml.replace("site-doctor@personal", "site-doctor@solo-suite-codex")
    xml = xml.replace(
        "They also work standalone — run python3 &lt;script&gt; &lt;target&gt;:",
        "From an intact installed plugin, run helpers through scripts/run_helper.py "
        "with python3, python, or py -3:",
    )
    xml = xml.replace(
        "Each prompt names the skill so it triggers reliably even if you don't use "
        "the slash command.",
        "Each prompt names the skill so the intended Codex workflow is explicit.",
    )
    xml = xml.replace(
        "codex plugin marketplace add owner/repository --ref main",
        "codex plugin marketplace add /verified/path/to/solo-suite-codex",
    )
    xml = xml.replace(
        "Stdlib-only Python the skills run for you. They also work standalone — run ",
        "Bundled helpers resolve from the intact installed plugin root. Run ",
    )
    xml = xml.replace(
        "python3 &lt;script&gt; &lt;target&gt;",
        "&lt;python-command&gt; &lt;resolved-plugin-root&gt;/scripts/run_helper.py "
        "&lt;helper-id&gt; &lt;target&gt;",
    )
    xml = xml.replace(
        "&lt;python-command&gt; scripts/run_helper.py &lt;helper-id&gt; &lt;target&gt;",
        "&lt;python-command&gt; &lt;resolved-plugin-root&gt;/scripts/run_helper.py "
        "&lt;helper-id&gt; &lt;target&gt;",
    )
    xml = xml.replace(
        "Each prompt names the skill so it triggers reliably even if you don&apos;t "
        "use the slash command.",
        "Each prompt names the skill so the intended Codex workflow is explicit.",
    )
    xml = COMMAND.sub(lambda match: f"${match.group(1)}-{match.group(2)}", xml)
    xml = xml.replace(
        "Tip: after any audit, ask Codex to &quot;apply the fixes&quot; — the fix "
        "skills create a restore point, change one thing at a time, verify each, "
        "and never auto-touch auth, payments, or destructive operations without "
        "confirming.",
        "Tip: invoke a specific fix skill explicitly. Preview the plan, create a "
        "restore point, and confirm before any mutation — especially auth, payments, "
        "or destructive operations.",
    )
    # The two large trailing spacers caused the short final note to spill onto an
    # otherwise empty page in Word. Preserve the note and border, but tighten only
    # the local spacing at the end of the document.
    trailing_spacer = '<w:p><w:pPr><w:spacing w:after="160"/></w:pPr></w:p>'
    index = xml.rfind(trailing_spacer)
    if index >= 0:
        xml = (xml[:index] +
               '<w:p><w:pPr><w:spacing w:after="20"/></w:pPr></w:p>' +
               xml[index + len(trailing_spacer):])
    xml = xml.replace(
        '<w:pBdr><w:top w:val="single" w:color="C9D4E0" w:sz="8" '
        'w:space="6"/></w:pBdr><w:spacing w:before="120"/>',
        '<w:pBdr><w:top w:val="single" w:color="C9D4E0" w:sz="8" '
        'w:space="4"/></w:pBdr><w:spacing w:before="40" w:after="0"/>',
        1,
    )
    return xml


def patch_core(xml: str) -> str:
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )
    replacements = {
        "dc:title": "Site Doctor for Codex - Cheat Sheet",
        "dc:subject": "Solo Suite Codex v1.0.27",
        "cp:lastModifiedBy": "",
    }
    for tag, value in replacements.items():
        pattern = rf"<{re.escape(tag)}(?:\s[^>]*)?>.*?</{re.escape(tag)}>"
        replacement = f"<{tag}>{value}</{tag}>"
        if re.search(pattern, xml, flags=re.DOTALL):
            xml = re.sub(pattern, replacement, xml, count=1, flags=re.DOTALL)
        else:
            xml = xml.replace("</cp:coreProperties>",
                              f"<{tag}>{value}</{tag}></cp:coreProperties>")
    xml = re.sub(
        r"<dcterms:modified[^>]*>.*?</dcterms:modified>",
        '<dcterms:modified xsi:type="dcterms:W3CDTF">'
        f"{now}</dcterms:modified>",
        xml,
        count=1,
        flags=re.DOTALL,
    )
    return xml


def update(source: Path, destination: Path) -> None:
    source = source.resolve()
    destination = destination.resolve()
    with tempfile.NamedTemporaryFile(
        dir=destination.parent, suffix=".docx", delete=False
    ) as handle:
        temp = Path(handle.name)
    try:
        with zipfile.ZipFile(source, "r") as incoming, zipfile.ZipFile(
            temp, "w", compression=zipfile.ZIP_DEFLATED
        ) as outgoing:
            for item in incoming.infolist():
                if "comments" in item.filename.lower():
                    continue
                data = incoming.read(item.filename)
                if item.filename == "word/document.xml":
                    data = patch_document(data.decode("utf-8")).encode("utf-8")
                elif item.filename == "docProps/core.xml":
                    data = patch_core(data.decode("utf-8")).encode("utf-8")
                outgoing.writestr(item, data)
        temp.replace(destination)
    finally:
        temp.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    update(args.source, args.destination)


if __name__ == "__main__":
    main()
