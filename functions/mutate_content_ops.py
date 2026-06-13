"""Mutate-content primitives: raw byte-level writes to files."""

from pathlib import Path


def write(path: Path, data: bytes) -> None:
    Path(path).write_bytes(data)


def edit(path: Path, old: bytes, new: bytes) -> int:
    path = Path(path)
    content = path.read_bytes()
    count = content.count(old)
    if count:
        path.write_bytes(content.replace(old, new))
    return count


def append(path: Path, data: bytes) -> None:
    with open(path, "ab") as f:
        f.write(data)
