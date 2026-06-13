"""Execute-stage handler for the grep tool.

Files-only default is a budget decision — unbounded content-mode
results are the read-side equivalent of copying through context. The
capped notice deliberately offers no offset continuation: paging deep
into a capped scan defeats the budget; narrowing is the answer.
Handler-aware match modes (e.g. CSV column-scoped search) are a
deferred extension. The model-facing contract lives in DESCRIPTION.
"""

import re
from pathlib import Path

from core.errors import ToolError
from core.tool import Tool
from core.tool_definition import PRIMITIVE, Targets, ToolDefinition, ToolGroup
from functions import grep as grep_lines
from functions import read as read_bytes
from tools.common import HIDDEN_DIRS, is_binary, not_found

RESULT_CAP = 200
MODES = ("files", "content")

DEFINITION = ToolDefinition(
    name="grep",
    group=ToolGroup.SEARCH,
    composition=PRIMITIVE,
    policy_union=frozenset({ToolGroup.SEARCH}),
    targets=Targets.FILES,
    pagination=True,
    git=False,
)

DESCRIPTION = (
    "Search file contents for a pattern (substring or regex). Default "
    "returns matching file paths only (cheap). Use mode=\"content\" to see "
    "the matching lines with context. Use when you know roughly what's "
    "inside the file."
)


def run(
    pattern,
    scope=None,
    mode: str = "files",
    context_lines: int = 2,
    offset: int = 0,
    limit: int = 50,
    sandbox_root=None,
) -> str:
    if mode not in MODES:
        raise ToolError(f"unknown mode '{mode}' — use 'files' (paths only) or 'content'")
    if context_lines < 0:
        raise ToolError("context_lines must be >= 0")
    if offset < 0:
        raise ToolError("offset must be >= 0 — it is the number of results to skip")
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

    regex = _compile(pattern)
    results, capped = _scan(root, regex, mode, context_lines)
    if not results:
        return f"no matches for '{pattern}'"
    total = len(results)
    if offset >= total:
        raise ToolError(f"offset {offset:,} is beyond the end — only {total:,} results")
    page = results[offset : offset + limit]
    end = offset + len(page)
    body = ("\n--\n" if mode == "content" else "\n").join(page)
    if capped:
        return (
            f"{body}\n{total:,}+ matches, showing {offset + 1:,}–{end:,} — "
            "narrow the pattern or scope"
        )
    if end < total:
        return (
            f"{body}\n{total:,} matches, showing {offset + 1:,}–{end:,} — "
            f"narrow the pattern or scope, or continue with offset={end}"
        )
    return body


def _conditional_groups(args: dict) -> tuple:
    # Content mode returns file content (matched lines + context), so it
    # additionally requires read — find-but-not-read zones stay sealed.
    # Files mode stays search-only.
    if args.get("mode") == "content":
        return (ToolGroup.READ,)
    return ()


TOOL = Tool(
    definition=DEFINITION,
    description=DESCRIPTION,
    handler=run,
    conditional_groups=_conditional_groups,
)


def _compile(pattern: str):
    raw = pattern.encode("utf-8", errors="replace")
    try:
        return re.compile(raw)
    except re.error:
        return re.compile(re.escape(raw))


def _scan(root: Path, regex, mode: str, context_lines: int) -> tuple[list[str], bool]:
    results: list[str] = []
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        if HIDDEN_DIRS.intersection(path.relative_to(root).parts) or is_binary(path):
            continue
        matches = grep_lines(path, regex)
        if not matches:
            continue
        rel = str(path.relative_to(root))
        if mode == "files":
            if len(results) >= RESULT_CAP:
                return results, True
            results.append(f"{rel} · {len(matches)}")
            continue
        lines = read_bytes(path).decode("utf-8", errors="replace").splitlines()
        for line_number, _ in matches:
            if len(results) >= RESULT_CAP:
                return results, True
            results.append(_block(rel, lines, line_number, context_lines))
    return results, False


def _block(rel: str, lines: list[str], line_number: int, context_lines: int) -> str:
    start = max(1, line_number - context_lines)
    end = min(len(lines), line_number + context_lines)
    return "\n".join(
        f"{rel}:{n}{':' if n == line_number else '-'} {lines[n - 1]}"
        for n in range(start, end + 1)
    )
