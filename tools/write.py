"""Execute-stage handler for the write tool.

The returned diff is the model's self-verification loop. The overwrite
guard here is defense in depth — the pipeline's friction stage fires
first with the richer message (line count + alternative). Handler
validation (e.g. CSV column-count check) is a deferred option. The
model-facing contract lives in DESCRIPTION.
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
from functions import write as write_bytes
from tools.common import not_found, unified_diff, with_tier_flag

DEFINITION = ToolDefinition(
    name="write",
    group=ToolGroup.MUTATE_CONTENT,
    composition=PRIMITIVE,
    friction=frozenset({Friction.OVERWRITE}),
    policy_union=frozenset({ToolGroup.MUTATE_CONTENT}),
    targets=Targets.FILES,
    pagination=False,
    git=True,
)

DESCRIPTION = (
    "Write content to a file. Creating a new file needs no flag; replacing "
    "an existing file requires overwrite=true. For changing part of an "
    "existing file, use edit instead — it is cheaper and safer."
)


def run(path, content: str, overwrite: bool = False,
        tier_threshold: int = DEFAULT_SIZE_THRESHOLD) -> str:
    path = Path(path)
    if path.is_dir():
        raise ToolError(f"'{path}' is a folder — write targets files only")
    exists = path.is_file()
    if exists and not overwrite:
        raise ToolError(f"'{path}' exists — pass overwrite=true, or use edit")
    if not path.parent.is_dir():
        raise ToolError(f"{not_found(path.parent)} — create it first with create_dir")
    old = path.read_bytes().decode("utf-8", errors="replace") if exists else ""
    write_bytes(path, content.encode("utf-8"))
    diff = unified_diff(old, content, path.name, new_file=not exists)
    return with_tier_flag(diff, path, tier_threshold)


TOOL = Tool(definition=DEFINITION, description=DESCRIPTION, handler=run)
