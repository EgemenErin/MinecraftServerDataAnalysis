"""Minimal SNBT helpers for FTB Quests files (no external deps)."""

from __future__ import annotations

import re
from pathlib import Path


def _find_block(text: str, key: str) -> tuple[int, int] | None:
    pattern = re.compile(rf"(?:^|\n)\s*{re.escape(key)}\s*:\s*\{{", re.MULTILINE)
    match = pattern.search(text)
    if not match:
        return None
    start = text.find("{", match.start())
    depth = 0
    for idx in range(start, len(text)):
        char = text[idx]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return start, idx + 1
    return None


def parse_snbt_map(text: str, key: str) -> dict[str, int]:
    """Extract a flat string->int map from an SNBT section like completed or started."""
    block = _find_block(text, key)
    if not block:
        return {}

    body = text[block[0] : block[1]]
    entries: dict[str, int] = {}
    for match in re.finditer(
        r'"?([0-9A-Fa-f]{16})"?\s*:\s*(-?\d+)L?',
        body,
    ):
        entries[match.group(1).upper()] = int(match.group(2))
    return entries


def load_snbt_map_file(path: Path, key: str) -> dict[str, int]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    return parse_snbt_map(text, key)


def strip_mc_formatting(text: str) -> str:
    return re.sub(r"&[0-9a-fk-or]", "", text).strip()
