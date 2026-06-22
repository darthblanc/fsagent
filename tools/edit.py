"""Execute-stage handler for the edit tool.

The uniqueness rule forces read-before-edit and converts silent
mis-edits into explicit, recoverable failures — the membrane's biggest
budget and safety win in one mechanism. The pipeline's friction stage
enforces it first; the check here is defense in depth via the same
shaping helper. Structured handler selectors (edit a JSON path, a CSV
cell) are the designed extension; str-replace is the v2 baseline. The
model-facing contract lives in DESCRIPTION.
"""

from pathlib import Path

from core.errors import FrictionRequired, ToolError
from core.friction import unique_match_failure
from core.tiers import DEFAULT_SIZE_THRESHOLD
from core.tool import Tool
from core.tool_definition import (
    PRIMITIVE,
    Friction,
    Targets,
    ToolDefinition,
    ToolGroup,
)
from functions import edit as replace_bytes
from functions import read as read_bytes
from tools.common import not_found, unified_diff, with_tier_flag

DEFINITION = ToolDefinition(
    name="edit",
    group=ToolGroup.MUTATE_CONTENT,
    composition=PRIMITIVE,
    friction=frozenset({Friction.UNIQUE_MATCH}),
    policy_union=frozenset({ToolGroup.MUTATE_CONTENT}),
    targets=Targets.FILES,
    pagination=False,
    git=True,
)

DESCRIPTION = (
    "Replace one exact string in a file with another. old_str must match "
    "the current file content exactly and appear exactly once — read the "
    "file first to get the exact text. new_str empty deletes the text. "
    "This is the preferred way to modify files."
)


def run(path, old_str: str, new_str: str, replace_all: bool = False,
        tier_threshold: int = DEFAULT_SIZE_THRESHOLD) -> str:
    path = Path(path)
    if path.is_dir():
        raise ToolError(f"'{path}' is a folder — edit targets files only")
    if not path.is_file():
        raise ToolError(not_found(path))
    if not old_str:
        raise ToolError("old_str must not be empty — read the file and quote the exact text to replace")
    if old_str == new_str:
        raise ToolError("old_str and new_str are identical — nothing to change")
    old_text = read_bytes(path).decode("utf-8", errors="replace")
    count = old_text.count(old_str)
    if not (count > 1 and replace_all):
        failure = unique_match_failure(old_text, old_str)
        if failure:
            raise FrictionRequired(failure, kwarg="replace_all" if count > 1 else None)
    replace_bytes(path, old_str.encode("utf-8"), new_str.encode("utf-8"))
    new_text = old_text.replace(old_str, new_str)
    diff = unified_diff(old_text, new_text, path.name)
    return with_tier_flag(diff, path, tier_threshold)


TOOL = Tool(definition=DEFINITION, description=DESCRIPTION, handler=run)
