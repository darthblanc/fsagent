"""Execute-stage handler for the append tool.

No friction param: append is non-destructive to existing content, and
git covers the rest. CSV appends are validated against the header's
column count before any byte is written. The model-facing contract
lives in DESCRIPTION.
"""

import csv
import io
from pathlib import Path

from core.errors import ToolError
from core.tiers import DEFAULT_SIZE_THRESHOLD
from core.tool import Tool
from core.tool_definition import PRIMITIVE, Targets, ToolDefinition, ToolGroup
from functions import append as append_bytes
from functions import read as read_bytes
from tools.common import not_found, unified_diff, with_tier_flag

DEFINITION = ToolDefinition(
    name="append",
    group=ToolGroup.MUTATE_CONTENT,
    composition=PRIMITIVE,
    policy_union=frozenset({ToolGroup.MUTATE_CONTENT}),
    targets=Targets.FILES,
    pagination=False,
    git=True,
)

DESCRIPTION = "Append content as new line(s) at the end of a file."


def run(path, content: str, tier_threshold: int = DEFAULT_SIZE_THRESHOLD) -> str:
    path = Path(path)
    if path.is_dir():
        raise ToolError(f"'{path}' is a folder — append targets files only")
    if not path.is_file():
        raise ToolError(f"{not_found(path)} — use write to create it")
    if not content:
        raise ToolError("content must not be empty")
    old_text = read_bytes(path).decode("utf-8", errors="replace")
    if path.suffix.lower() == ".csv":
        _validate_csv(old_text, content)
    block = content if content.endswith("\n") else content + "\n"
    if old_text and not old_text.endswith("\n"):
        block = "\n" + block
    append_bytes(path, block.encode("utf-8"))
    diff = unified_diff(old_text, old_text + block, path.name)
    return with_tier_flag(diff, path, tier_threshold)


TOOL = Tool(definition=DEFINITION, description=DESCRIPTION, handler=run)


def _validate_csv(old_text: str, content: str) -> None:
    records = csv.reader(io.StringIO(old_text))
    header = next(records, None)
    if header is None:
        return
    expected = len(header)
    for row in csv.reader(io.StringIO(content)):
        if row and len(row) != expected:
            raise ToolError(
                f"file has {expected} columns ({','.join(header)}); got {len(row)}"
            )
