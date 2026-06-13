"""Execute-stage handler for the move tool.

One tool for both targets — one intent: "relocate this thing".
Whole-tree staging (git add -A) makes moves appear as renames in diffs
and history, so review reads naturally and revert restores the old
path. The collision guard here is defense in depth — the pipeline's
friction stage fires first. The model-facing contract lives in
DESCRIPTION.
"""

from pathlib import Path

from core.errors import ToolError
from core.tiers import DEFAULT_SIZE_THRESHOLD
from core.tool import Tool
from core.tool_definition import (
    PRIMITIVE,
    Friction,
    Targets,
    ToolDefinition,
    ToolGroup,
)
from functions import move as move_entry
from tools.common import not_found, with_tier_flag

DEFINITION = ToolDefinition(
    name="move",
    group=ToolGroup.MUTATE_STRUCTURE,
    composition=PRIMITIVE,
    friction=frozenset({Friction.OVERWRITE}),
    policy_union=frozenset({ToolGroup.MUTATE_STRUCTURE}),
    targets=Targets.BOTH,
    pagination=False,
    git=True,
)

DESCRIPTION = (
    "Move a file or folder to a new path. Renaming is moving within the "
    "same directory. Replacing an existing destination file requires "
    "overwrite=true."
)


def run(src, dest, overwrite: bool = False,
        tier_threshold: int = DEFAULT_SIZE_THRESHOLD) -> str:
    src, dest = Path(src), Path(dest)
    if not src.exists():
        raise ToolError(not_found(src))
    if src == dest:
        raise ToolError("src and dest are identical — nothing to move")
    if dest.is_dir():
        raise ToolError(
            f"'{dest}' is an existing folder — pass the full destination path, "
            f"e.g. '{dest / src.name}'"
        )
    if src.is_dir() and dest.is_relative_to(src):
        raise ToolError(f"cannot move '{src}' into itself")
    if dest.is_file() and not overwrite:
        raise ToolError(f"destination '{dest}' exists — pass overwrite=true")
    if not dest.parent.is_dir():
        raise ToolError(f"{not_found(dest.parent)} — create it first with create_dir")
    move_entry(src, dest)
    result = f"moved '{src}' → '{dest}'"
    if dest.is_file():
        result = with_tier_flag(result, dest, tier_threshold)
    return result


TOOL = Tool(definition=DEFINITION, description=DESCRIPTION, handler=run)
