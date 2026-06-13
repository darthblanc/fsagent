"""Search-group primitives: raw matching over paths and file contents."""

import re
from pathlib import Path


def glob(root: Path, pattern: str) -> list[Path]:
    return sorted(Path(root).glob(pattern))


def grep(path: Path, pattern: bytes) -> list[tuple[int, bytes]]:
    regex = re.compile(pattern)
    matches = []
    for number, line in enumerate(Path(path).read_bytes().splitlines(), start=1):
        if regex.search(line):
            matches.append((number, line))
    return matches
