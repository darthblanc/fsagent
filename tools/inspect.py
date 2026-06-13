"""Execute-stage handler for the inspect tool.

~100-token JSON budget — this schema is the most load-bearing in the
system. The pipeline injects the live policy and tier threshold via
handler extras. The model-facing contract lives in DESCRIPTION.
"""

import csv
import io
import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from core.errors import ToolError
from core.tiers import DEFAULT_SIZE_THRESHOLD, Tier, classify
from core.tool import Tool
from core.tool_definition import PRIMITIVE, Targets, ToolDefinition, ToolGroup
from functions import inspect as inspect_entry
from functions import read as read_bytes
from tools.common import HEADING, HIDDEN_DIRS, not_found

_GROUPS = (
    ToolGroup.READ,
    ToolGroup.SEARCH,
    ToolGroup.MUTATE_CONTENT,
    ToolGroup.MUTATE_STRUCTURE,
)
_LIST_CAP = 20

DEFINITION = ToolDefinition(
    name="inspect",
    group=ToolGroup.READ,
    composition=PRIMITIVE,
    policy_union=frozenset({ToolGroup.READ}),
    targets=Targets.BOTH,
    pagination=False,
    git=False,
)

DESCRIPTION = (
    "Describe a file or folder without reading its contents: type, size, "
    "structure, versioning tier, and what you are permitted to do to it. "
    "Call this before expensive reads and before any mutation."
)


def run(path, policy=None, tier_threshold: int = DEFAULT_SIZE_THRESHOLD) -> str:
    path = Path(path)
    try:
        info = inspect_entry(path)
    except FileNotFoundError:
        raise ToolError(not_found(path)) from None
    if info.kind == "folder":
        result = _describe_folder(path, tier_threshold)
    else:
        result = _describe_file(path, info, tier_threshold)
    result["permissions"] = _permissions(path, policy)
    return json.dumps(result)


TOOL = Tool(definition=DEFINITION, description=DESCRIPTION, handler=run)


def _permissions(path: Path, policy) -> list[str]:
    if policy is None:
        return [group.value for group in _GROUPS]
    return [group.value for group in _GROUPS if policy.check(path, group).allowed]


def _describe_file(path: Path, info, tier_threshold: int) -> dict:
    tier = classify(path, tier_threshold)
    extension = path.suffix[1:].lower()
    result = {
        "type": "file",
        "format": extension or ("binary" if tier is Tier.BINARY else "text"),
        "size_bytes": info.size,
        "tier": int(tier),
        "mtime": datetime.fromtimestamp(info.mtime, tz=timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z"),
    }
    if tier is Tier.TEXT:
        structure = _structure(path, extension)
        if structure is not None:
            result["structure"] = structure
    return result


def _structure(path: Path, extension: str):
    text = read_bytes(path).decode("utf-8", errors="replace")
    if extension == "csv":
        records = csv.reader(io.StringIO(text))
        headers = next(records, None)
        if headers is None:
            return None
        return {"headers": headers[:_LIST_CAP], "rows": sum(1 for _ in records)}
    if extension == "json":
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return None
        if isinstance(data, dict):
            return {"keys": list(data)[:_LIST_CAP]}
        if isinstance(data, list):
            return {"length": len(data)}
        return {"value": type(data).__name__}
    if extension in ("md", "markdown"):
        outline = [
            f"{match.group(1)} {match.group(2).strip()}"
            for line in text.splitlines()
            if (match := HEADING.match(line))
        ]
        return {"outline": outline[:_LIST_CAP]}
    return {"lines": len(text.splitlines())}


def _describe_folder(path: Path, tier_threshold: int) -> dict:
    files = dirs = 0
    for entry in path.iterdir():
        if entry.name in HIDDEN_DIRS:
            continue
        if entry.is_dir():
            dirs += 1
        else:
            files += 1
    subtree_size = 0
    tier_3_files = 0
    max_depth = 0
    by_extension: Counter = Counter()
    for root, dirnames, filenames in os.walk(path):
        dirnames[:] = [name for name in dirnames if name not in HIDDEN_DIRS]
        base_depth = len(Path(root).relative_to(path).parts)
        if dirnames or filenames:
            max_depth = max(max_depth, base_depth + 1)
        for name in filenames:
            size = (Path(root) / name).stat().st_size
            subtree_size += size
            if size > tier_threshold:
                tier_3_files += 1
            suffix = Path(name).suffix[1:].lower()
            by_extension[suffix or "(no ext)"] += 1
    return {
        "type": "folder",
        "entries": {"files": files, "dirs": dirs},
        "subtree_size_bytes": subtree_size,
        "max_depth": max_depth,
        "tier_3_files": tier_3_files,
        "by_extension": dict(sorted(by_extension.items())),
    }
