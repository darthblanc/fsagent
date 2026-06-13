"""Read-group primitives: raw byte-level reads of files and folders."""

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class EntryInfo:
    path: Path
    kind: str  # "file" | "folder"
    size: int
    mtime: float
    mode: int


def read(path: Path) -> bytes:
    return Path(path).read_bytes()


def inspect(path: Path) -> EntryInfo:
    path = Path(path)
    stat = path.stat()
    return EntryInfo(
        path=path,
        kind="folder" if path.is_dir() else "file",
        size=stat.st_size,
        mtime=stat.st_mtime,
        mode=stat.st_mode,
    )


def list_dir(path: Path) -> list[str]:
    return sorted(os.listdir(path))
