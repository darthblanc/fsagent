"""File tiers: what guarantee the harness can honestly make.

Tier 1 — text formats: tracked, diffable, revertible — full contract.
Tier 2 — ordinary binaries: tracked and revertible; diffs degrade to size changes.
Tier 3 — over the size threshold: untracked — not reversible, flagged loudly.
"""

from enum import IntEnum
from pathlib import Path

DEFAULT_SIZE_THRESHOLD = 50 * 1024 * 1024
_SNIFF_BYTES = 8192


class Tier(IntEnum):
    TEXT = 1
    BINARY = 2
    OVERSIZED = 3


GUARANTEES = {
    Tier.TEXT: "tracked, diffable, revertible — full contract",
    Tier.BINARY: "tracked and revertible; diffs degrade to size changes",
    Tier.OVERSIZED: "untracked — not reversible, flagged loudly",
}


def classify(path: Path, size_threshold: int = DEFAULT_SIZE_THRESHOLD) -> Tier:
    path = Path(path)
    if path.stat().st_size > size_threshold:
        return Tier.OVERSIZED
    with open(path, "rb") as f:
        chunk = f.read(_SNIFF_BYTES)
    return Tier.BINARY if b"\x00" in chunk else Tier.TEXT
