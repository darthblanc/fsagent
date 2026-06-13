"""Execute-stage handler for the glob tool.

BFS/DFS is implementation, not interface — tool boundaries match
intent categories, so only pattern and scope cross the membrane.
The model-facing contract lives in DESCRIPTION.
"""

from pathlib import Path

from core.errors import ToolError
from core.tool import Tool
from core.tool_definition import PRIMITIVE, Targets, ToolDefinition, ToolGroup
from functions import glob as glob_paths
from tools.common import HIDDEN_DIRS, not_found

DEFINITION = ToolDefinition(
    name="glob",
    group=ToolGroup.SEARCH,
    composition=PRIMITIVE,
    policy_union=frozenset({ToolGroup.SEARCH}),
    targets=Targets.BOTH,
    pagination=True,
    git=False,
)

DESCRIPTION = (
    "Find files and folders whose paths match a glob pattern, e.g. '**/*.csv'. "
    "Returns paths only — cheap. Use when you know roughly the name."
)


def run(pattern, scope=None, offset: int = 1, limit: int = 100, sandbox_root=None) -> str:
    if offset < 1:
        raise ToolError("offset must be >= 1 — it is the 1-indexed first match to return")
    if limit < 1:
        raise ToolError("limit must be >= 1")
    root = scope if scope is not None else sandbox_root
    if root is None:
        raise ToolError("no scope available — provide a scope folder to search in")
    root = Path(root)
    if not root.exists():
        raise ToolError(not_found(root))
    if not root.is_dir():
        raise ToolError(f"'{root}' is a file — scope must be a folder")
    try:
        matches = glob_paths(root, pattern)
    except (ValueError, NotImplementedError) as error:
        raise ToolError(f"invalid pattern '{pattern}': {error}") from None
    paths = [
        str(relative)
        for match in matches
        if not HIDDEN_DIRS.intersection((relative := match.relative_to(root)).parts)
    ]
    if not paths:
        return f"no matches for '{pattern}'"
    total = len(paths)
    if offset > total:
        raise ToolError(f"offset {offset:,} is beyond the end — only {total:,} matches")
    page = paths[offset - 1 : offset - 1 + limit]
    end = offset - 1 + len(page)
    body = "\n".join(page)
    if end < total:
        return (
            f"{body}\n{total:,} matches, showing {offset:,}–{end:,} — "
            f"narrow the pattern or continue with offset={end + 1}"
        )
    return body


TOOL = Tool(definition=DEFINITION, description=DESCRIPTION, handler=run)
