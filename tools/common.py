"""Failure shaping and format helpers shared across tools."""

import difflib
import re
from pathlib import Path

from core.tiers import Tier, classify


def unified_diff(old: str, new: str, name: str, new_file: bool = False) -> str:
    if old == new:
        return "(no change)"
    lines = difflib.unified_diff(
        old.splitlines(),
        new.splitlines(),
        fromfile="/dev/null" if new_file else f"a/{name}",
        tofile=f"b/{name}",
        lineterm="",
    )
    return "\n".join(lines)


def with_tier_flag(result: str, path: Path, tier_threshold: int) -> str:
    if classify(path, tier_threshold) is Tier.OVERSIZED:
        return f"{result}\ntier 3 — this change is NOT reversible"
    return result

HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")

# Deleted entries are staged here by the harness, below the membrane.
TRASH_DIR = "_trash"

# Harness plumbing the model never observes: read/search tools filter
# these from every listing, match set, scan, and folder summary.
HIDDEN_DIRS = frozenset({TRASH_DIR, ".git"})

_SNIFF_BYTES = 8192


def is_binary(path: Path) -> bool:
    with open(path, "rb") as f:
        return b"\x00" in f.read(_SNIFF_BYTES)


def not_found(path: Path) -> str:
    parent = path.parent
    if parent.is_dir():
        candidates = sorted(entry.name for entry in parent.iterdir())
        matches = difflib.get_close_matches(path.name, candidates, n=3, cutoff=0.5)
        if matches:
            similar = ", ".join(str(parent / match) for match in matches)
            return f"'{path}' not found — similar paths: {similar}"
    return f"'{path}' not found"
