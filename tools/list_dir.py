"""Execute-stage handler for the list_dir tool.

Pagination is entry-based with a 0-based offset (a skip count), unlike
read's 1-indexed line offset. .gitkeep is create_dir's git-stage
artifact, hidden here. The model-facing contract lives in DESCRIPTION.
"""

from pathlib import Path

from core.errors import ToolError
from core.tool import Tool
from core.tool_definition import PRIMITIVE, Targets, ToolDefinition, ToolGroup
from functions import list_dir as list_entries
from tools.common import HIDDEN_DIRS, not_found

MAX_DEPTH = 3

DEFINITION = ToolDefinition(
    name="list_dir",
    group=ToolGroup.READ,
    composition=PRIMITIVE,
    policy_union=frozenset({ToolGroup.READ}),
    targets=Targets.FOLDERS,
    pagination=True,
    git=False,
)

DESCRIPTION = (
    "List a folder's entries with name, type, and size. depth > 1 returns "
    "an indented tree (max 3). For 'what's in here structurally' prefer "
    "inspect; for 'find by name' prefer glob."
)


def run(path, offset: int = 0, limit: int = 200, depth: int = 1) -> str:
    if offset < 0:
        raise ToolError("offset must be >= 0 — it is the number of entries to skip")
    if limit < 1:
        raise ToolError("limit must be >= 1")
    if not 1 <= depth <= MAX_DEPTH:
        raise ToolError(f"depth must be between 1 and {MAX_DEPTH}, got {depth}")
    path = Path(path)
    try:
        lines = _collect(path, depth, level=0)
    except FileNotFoundError:
        raise ToolError(not_found(path)) from None
    except NotADirectoryError:
        raise ToolError(
            f"'{path}' is a file — list_dir targets folders only (use read)"
        ) from None
    if not lines:
        return "(empty folder)"
    total = len(lines)
    if offset >= total:
        raise ToolError(f"offset {offset:,} is beyond the end — only {total:,} entries")
    page = lines[offset : offset + limit]
    body = "\n".join(page)
    end = offset + len(page)
    if end < total:
        return f"{body}\nentries {offset + 1:,}–{end:,} of {total:,} — next: offset={end}"
    return body


TOOL = Tool(definition=DEFINITION, description=DESCRIPTION, handler=run)


def _collect(path: Path, depth: int, level: int) -> list[str]:
    lines = []
    indent = "  " * level
    for name in list_entries(path):
        if name == ".gitkeep" or name in HIDDEN_DIRS:
            continue
        entry = path / name
        if entry.is_dir():
            lines.append(f"{indent}{name} · folder · -")
            if depth > 1:
                lines.extend(_collect(entry, depth - 1, level + 1))
        else:
            lines.append(f"{indent}{name} · file · {entry.stat().st_size}")
    return lines
