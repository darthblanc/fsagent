"""Mutate-structure primitives: raw creation, movement, and removal of entries."""

import os
import shutil
from pathlib import Path


def create_dir(path: Path) -> None:
    os.mkdir(path)


def move(src: Path, dest: Path) -> None:
    os.replace(src, dest)


def delete(path: Path, recursive: bool = False) -> None:
    path = Path(path)
    if not path.is_dir():
        os.unlink(path)
    elif recursive:
        shutil.rmtree(path)
    else:
        os.rmdir(path)
