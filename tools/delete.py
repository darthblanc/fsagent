"""Execute-stage handler for the delete tool — the sharpest tool.

Friction-as-informed-consent: the first attempt on a non-empty folder
reports the census; the recursive=true retry is an informed action, no
human gate needed. Tier-1/2 deletions are recoverable (content lives in
git history); tier-3 contents were never tracked, so their flag is
computed before the bytes disappear.

Below the membrane, deletion is staged: the target moves to
_trash/<relative path> under the sandbox root (collisions get ~N
suffixes). The model never learns this — confirmations say "deleted"
and the read/search tools filter _trash/ — and the user empties the
trash at will. A delete targeting a path already inside _trash/ is a
real deletion (that is the emptying path). Without an injected
sandbox_root (direct handler use), deletion is real. The model-facing
contract lives in DESCRIPTION.
"""

import os
from pathlib import Path

from core.errors import FrictionRequired, ToolError
from core.friction import folder_census, non_empty_folder_failure
from core.tiers import DEFAULT_SIZE_THRESHOLD
from core.tool import Tool
from core.tool_definition import (
    PRIMITIVE,
    Friction,
    Targets,
    ToolDefinition,
    ToolGroup,
)
from functions import delete as delete_entry
from functions import move as move_entry
from tools.common import TRASH_DIR, not_found

TIER_3_NOTE = "tier 3 — contents NOT recoverable from history"

DEFINITION = ToolDefinition(
    name="delete",
    group=ToolGroup.MUTATE_STRUCTURE,
    composition=PRIMITIVE,
    friction=frozenset({Friction.RECURSIVE}),
    policy_union=frozenset({ToolGroup.MUTATE_STRUCTURE}),
    targets=Targets.BOTH,
    pagination=False,
    git=True,
)

DESCRIPTION = (
    "Delete a file or folder. Deleting a non-empty folder requires "
    "recursive=true — the first attempt will tell you what's inside."
)


def run(path, recursive: bool = False,
        tier_threshold: int = DEFAULT_SIZE_THRESHOLD, sandbox_root=None) -> str:
    path = Path(path)
    if not path.exists():
        raise ToolError(not_found(path))
    if path.is_dir():
        failure = non_empty_folder_failure(path)
        if failure and not recursive:
            raise FrictionRequired(failure)
        files, dirs = folder_census(path)
        oversized = _subtree_has_oversized(path, tier_threshold)
        _remove(path, sandbox_root)
        confirmation = f"deleted '{path}'"
        if files or dirs:
            confirmation += f" ({files} files, {dirs} subfolders)"
    else:
        oversized = path.stat().st_size > tier_threshold
        _remove(path, sandbox_root)
        confirmation = f"deleted '{path}'"
    if oversized:
        return f"{confirmation}\n{TIER_3_NOTE}"
    return confirmation


TOOL = Tool(definition=DEFINITION, description=DESCRIPTION, handler=run)


def _remove(path: Path, sandbox_root) -> None:
    staged = _trash_destination(path, sandbox_root)
    if staged is None:
        if path.is_dir():
            delete_entry(path, recursive=True)
        else:
            delete_entry(path)
        return
    os.makedirs(staged.parent, exist_ok=True)
    move_entry(path, staged)


def _trash_destination(path: Path, sandbox_root) -> Path | None:
    if sandbox_root is None or TRASH_DIR in path.parts:
        return None
    root = Path(sandbox_root)
    try:
        relative = path.relative_to(root.resolve())
    except ValueError:
        relative = Path(path.name)
    destination = root / TRASH_DIR / relative
    suffix = 0
    while destination.exists():
        suffix += 1
        destination = destination.with_name(f"{relative.name}~{suffix}")
    return destination


def _subtree_has_oversized(path: Path, tier_threshold: int) -> bool:
    for root, _, filenames in os.walk(path):
        for name in filenames:
            if (Path(root) / name).stat().st_size > tier_threshold:
                return True
    return False
