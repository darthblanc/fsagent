"""Stage 3 — Friction: destructive-parameter confirmations.

First attempt fails informatively (FrictionRequired); the informed
second action is passing the destructive parameter (OVERWRITE,
RECURSIVE) or retrying with corrected/extended text (UNIQUE_MATCH).
"""

import difflib
import os
from pathlib import Path
from typing import Protocol

from core.errors import FrictionRequired
from core.tool_definition import Friction, ToolDefinition

_OVERWRITE_ALTERNATIVES = {"write": "use edit"}
_SNIPPET_LIMIT = 60
_NEAREST_CUTOFF = 0.4


def unique_match_failure(content: str, old_str: str) -> str | None:
    """Shaped message when old_str does not occur exactly once, else None.

    Shared by the friction gate and the edit handler (defense in depth):
    stale context gets pointed at the nearest line, ambiguity gets the
    match locations — silent mis-edits become recoverable failures.
    """
    count = content.count(old_str)
    if count == 1:
        return None
    if count == 0:
        nearest = _nearest_line(content, old_str)
        if nearest is None:
            return "no exact match — re-read the file and retry with the current text"
        number, line = nearest
        snippet = line if len(line) <= _SNIPPET_LIMIT else line[:_SNIPPET_LIMIT] + "…"
        return (
            f"no exact match — nearest occurrence at line {number}: "
            f"'{snippet}' — re-read and retry with the current text"
        )
    numbers = []
    start = 0
    while (index := content.find(old_str, start)) != -1:
        numbers.append(content.count("\n", 0, index) + 1)
        start = index + len(old_str)
    listed = ", ".join(str(n) for n in numbers)
    return (
        f"matched {count} locations (lines {listed}) — pass replace_all=true "
        "to replace all of them, or include more surrounding context to "
        "disambiguate one"
    )


def folder_census(path: Path) -> tuple[int, int]:
    """(files, subfolders) in the subtree, excluding .gitkeep markers —
    a folder the model sees as empty must count as empty."""
    files = dirs = 0
    for _, dirnames, filenames in os.walk(path):
        dirs += len(dirnames)
        files += sum(1 for name in filenames if name != ".gitkeep")
    return files, dirs


def non_empty_folder_failure(path) -> str | None:
    """Shaped message when deleting a non-empty folder without
    recursive=true, else None. Shared by the gate and the delete handler."""
    path = Path(path)
    if not path.is_dir():
        return None
    files, dirs = folder_census(path)
    if files == 0 and dirs == 0:
        return None
    return (
        f"'{path}' contains {files} files, {dirs} subfolders — "
        "pass recursive=true to confirm"
    )


def _nearest_line(content: str, old_str: str) -> tuple[int, str] | None:
    probe = next((line.strip() for line in old_str.splitlines() if line.strip()), old_str)
    best = None
    best_ratio = _NEAREST_CUTOFF
    for number, line in enumerate(content.splitlines(), start=1):
        ratio = difflib.SequenceMatcher(None, probe, line.strip()).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best = (number, line.strip())
    return best


class FrictionGate(Protocol):
    def check(self, definition: ToolDefinition, args: dict) -> None: ...


class NoFriction:
    def check(self, definition: ToolDefinition, args: dict) -> None:
        return None


class StandardFriction:
    def check(self, definition: ToolDefinition, args: dict) -> None:
        if Friction.OVERWRITE in definition.friction:
            self._check_overwrite(definition, args)
        if Friction.UNIQUE_MATCH in definition.friction:
            self._check_unique_match(args)
        if Friction.RECURSIVE in definition.friction:
            self._check_recursive(args)

    def _check_recursive(self, args: dict) -> None:
        if args.get("recursive"):
            return
        target = args.get("path")
        if target is None:
            return
        failure = non_empty_folder_failure(target)
        if failure:
            raise FrictionRequired(failure, kwarg="recursive")

    def _check_unique_match(self, args: dict) -> None:
        target = args.get("path")
        old_str = args.get("old_str")
        if target is None or old_str is None or not Path(target).is_file():
            return  # missing file is the handler's failure to shape
        content = Path(target).read_bytes().decode("utf-8", "replace")
        count = content.count(old_str)
        if count > 1 and args.get("replace_all"):
            return  # informed action — human approved replacing every match
        failure = unique_match_failure(content, old_str)
        if failure:
            raise FrictionRequired(failure, kwarg="replace_all" if count > 1 else None)

    def _check_overwrite(self, definition: ToolDefinition, args: dict) -> None:
        if args.get("overwrite"):
            return
        if "dest" in args:
            # Collision messages carry no line count (a dest may be a
            # folder); an existing-folder dest is the handler's hint.
            dest = args["dest"]
            if Path(dest).is_file():
                raise FrictionRequired(
                    f"destination '{dest}' exists — pass overwrite=true", kwarg="overwrite"
                )
            return
        target = args.get("path")
        if target is None or not Path(target).is_file():
            return
        lines = len(Path(target).read_bytes().decode("utf-8", "replace").splitlines())
        message = f"'{target}' exists ({lines:,} lines) — pass overwrite=true"
        alternative = _OVERWRITE_ALTERNATIVES.get(definition.name)
        if alternative:
            message += f", or {alternative}"
        raise FrictionRequired(message, kwarg="overwrite")
