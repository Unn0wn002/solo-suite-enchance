"""Shared, dependency-free helpers for agent platform tooling."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
FRONTMATTER_RE = re.compile(r"\A---\r?\n(?P<body>.*?)\r?\n---(?:\r?\n|\Z)", re.DOTALL)
NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def load_json_yaml(path: Path) -> Any:
    """Load the repository's JSON-compatible YAML files without PyYAML."""
    return json.loads(path.read_text(encoding="utf-8"))


def parse_frontmatter(path: Path) -> tuple[dict[str, str], str]:
    text = path.read_text(encoding="utf-8")
    match = FRONTMATTER_RE.match(text)
    if not match:
        raise ValueError("missing YAML frontmatter")
    fields: dict[str, str] = {}
    for number, raw_line in enumerate(match.group("body").splitlines(), start=2):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            raise ValueError(f"unsupported frontmatter syntax on line {number}")
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if not key or not value:
            raise ValueError(f"empty frontmatter key/value on line {number}")
        if value[:1] in {"'", '"'} and value[-1:] == value[:1]:
            value = value[1:-1]
        fields[key] = value
    return fields, text[match.end() :]


def canonical_skills() -> dict[str, Path]:
    result: dict[str, Path] = {}
    root = ROOT / ".agents" / "skills"
    if not root.is_dir():
        return result
    for directory in sorted(path for path in root.iterdir() if path.is_dir()):
        result[directory.name] = directory
    return result


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_text_lf(path: Path) -> str:
    """Hash UTF-8 text with canonical LF newlines across checkout platforms."""
    content = path.read_bytes()
    if b"\0" in content:
        raise ValueError(f"expected a text file: {path}")
    normalized = content.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(normalized).hexdigest()


def relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def is_within(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except (OSError, ValueError):
        return False
