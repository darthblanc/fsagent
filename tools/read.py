"""Execute-stage handler for the read tool.

Pagination plus the hard character cap guarantee no call returns
unbounded bytes — tier-3 files are fully readable, just never all at
once. The model-facing contract lives in DESCRIPTION.
"""

import csv
import io
import json
import re
from pathlib import Path

from core.errors import ToolError
from core.tool import Tool
from core.tool_definition import PRIMITIVE, Targets, ToolDefinition, ToolGroup
from functions import read as read_bytes
from tools.common import HEADING, not_found

HARD_CHAR_CAP = 30_000

DEFINITION = ToolDefinition(
    name="read",
    group=ToolGroup.READ,
    composition=PRIMITIVE,
    policy_union=frozenset({ToolGroup.READ}),
    targets=Targets.FILES,
    pagination=True,
    git=False,
)

DESCRIPTION = (
    "Read a file's contents. Returns line-numbered text. Large files are "
    "returned in pages; the truncation notice tells you how to continue. "
    "Prefer inspect first and grep to locate, so you read only what you need."
)


def run(path, offset: int = 1, limit: int = 500, selector=None) -> str:
    if offset < 1:
        raise ToolError("offset must be >= 1 — it is the 1-indexed first line to return")
    if limit < 1:
        raise ToolError("limit must be >= 1")
    path = Path(path)
    if path.is_dir():
        raise ToolError(f"'{path}' is a folder — read targets files only (use list_dir)")
    try:
        text = read_bytes(path).decode("utf-8", errors="replace")
    except FileNotFoundError:
        raise ToolError(not_found(path)) from None
    return _paginate(_select(path, text, selector), offset, limit)


TOOL = Tool(definition=DEFINITION, description=DESCRIPTION, handler=run)


def _paginate(numbered: list[tuple[int, str]], offset: int, limit: int) -> str:
    if not numbered:
        return "(empty file)"
    total = len(numbered)
    if offset > total:
        raise ToolError(f"offset {offset:,} is beyond the end — only {total:,} lines")
    page = []
    chars = 0
    end = offset - 1
    for position in range(offset - 1, min(offset - 1 + limit, total)):
        number, line = numbered[position]
        chars += len(line)
        if page and chars > HARD_CHAR_CAP:
            break
        page.append(f"{number:6d}\t{line}")
        end = position + 1
    body = "\n".join(page)
    if end < total:
        return f"{body}\nlines {offset:,}–{end:,} of {total:,} — next: offset={end + 1}"
    return body


def _select(path: Path, text: str, selector) -> list[tuple[int, str]]:
    if selector is None:
        return list(enumerate(text.splitlines(), start=1))
    suffix = path.suffix.lower()
    if suffix == ".json":
        return _select_json(text, selector)
    if suffix == ".csv":
        return _select_csv(text, selector)
    if suffix in (".md", ".markdown"):
        return _select_markdown(text, selector)
    raise ToolError(
        f"no selector support for '{suffix or 'plain text'}' files — use offset/limit instead"
    )


def _select_json(text: str, selector) -> list[tuple[int, str]]:
    if not isinstance(selector, str) or not selector:
        raise ToolError("JSON selector must be a dotted path string, e.g. 'config.database.host'")
    try:
        node = json.loads(text)
    except json.JSONDecodeError as error:
        raise ToolError(f"invalid JSON: {error}") from None
    parts = selector.split(".")
    seen: list[str] = []
    for i, part in enumerate(parts):
        where = ".".join(seen) or "root"
        if isinstance(node, list):
            if not re.fullmatch(r"\d+", part):
                suggestion = ".".join(seen + ["0"] + parts[i:])
                raise ToolError(
                    f"{where} is an array[{len(node)}], not an object — index it: {suggestion}"
                )
            index = int(part)
            if index >= len(node):
                raise ToolError(
                    f"index {index} out of range — {where} has {len(node)} elements "
                    f"(0–{len(node) - 1})"
                )
            node = node[index]
        elif isinstance(node, dict):
            if part not in node:
                raise ToolError(
                    f"no key '{part}' at {where} — available keys: {', '.join(node)}"
                )
            node = node[part]
        else:
            raise ToolError(f"{where} is a {type(node).__name__}, cannot descend into '{part}'")
        seen.append(part)
    rendered = json.dumps(node, indent=2, ensure_ascii=False)
    return list(enumerate(rendered.splitlines(), start=1))


def _select_csv(text: str, selector) -> list[tuple[int, str]]:
    if not isinstance(selector, dict):
        raise ToolError(
            'CSV selector must be an object, e.g. {"columns": ["name"], "rows": "head:50"}'
        )
    unknown = set(selector) - {"columns", "rows"}
    if unknown:
        raise ToolError(
            f"unknown CSV selector keys: {', '.join(sorted(unknown))} — "
            "use 'columns' and/or 'rows'"
        )
    records = list(csv.reader(io.StringIO(text)))
    if not records:
        return []
    header, data = records[0], records[1:]
    columns = selector.get("columns")
    if columns:
        for name in columns:
            if name not in header:
                raise ToolError(f"no column '{name}' — available columns: {', '.join(header)}")
        indices = [header.index(name) for name in columns]
    else:
        indices = list(range(len(header)))
    rows_spec = selector.get("rows")
    if rows_spec:
        data = _slice_rows(data, rows_spec)
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    for record in [header] + data:
        writer.writerow([record[i] if i < len(record) else "" for i in indices])
    return list(enumerate(out.getvalue().splitlines(), start=1))


def _slice_rows(data: list, spec) -> list:
    match = re.fullmatch(r"(head|tail|\d+):(\d+)", spec) if isinstance(spec, str) else None
    if not match:
        raise ToolError(
            f"invalid rows selector '{spec}' — use 'head:N', 'tail:N', or 'start:end'"
        )
    kind, count = match.group(1), int(match.group(2))
    if kind == "head":
        return data[:count]
    if kind == "tail":
        return data[-count:] if count else []
    return data[max(int(kind) - 1, 0):count]


def _select_markdown(text: str, selector) -> list[tuple[int, str]]:
    if not isinstance(selector, str) or not selector:
        raise ToolError("Markdown selector must be a heading or section name")
    lines = text.splitlines()
    headings = []
    for number, line in enumerate(lines, start=1):
        match = HEADING.match(line)
        if match:
            headings.append((number, len(match.group(1)), match.group(2).strip()))
    wanted = selector.strip().casefold()
    for position, (number, level, title) in enumerate(headings):
        if title.casefold() == wanted:
            end = len(lines)
            for later_number, later_level, _ in headings[position + 1:]:
                if later_level <= level:
                    end = later_number - 1
                    break
            return [(n, lines[n - 1]) for n in range(number, end + 1)]
    available = ", ".join(title for _, _, title in headings) or "none"
    raise ToolError(f"no heading '{selector}' — available headings: {available}")
