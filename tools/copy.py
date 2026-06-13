"""Execute-stage handler for the copy tool — the canonical composed tool.

write_bytes(dest, read_bytes(src)) below the membrane: zero tokens
regardless of file size, perfect fidelity (vs. ~2× file size in tokens
plus regeneration-corruption risk through context). Its policy_map is
the anti-exfiltration rule: read on src, mutate-structure on dest —
otherwise copy smuggles content out of read-denied zones. This is the
worked example for the transform pattern: every future transform is a
named, parameterized composition of primitives, entering the registry
exactly like copy did. The model-facing contract lives in DESCRIPTION.
"""

import os
from pathlib import Path

from core.errors import ToolError
from core.tiers import DEFAULT_SIZE_THRESHOLD
from core.tool import Tool
from core.tool_definition import Friction, Targets, ToolDefinition, ToolGroup
from functions import read as read_bytes
from functions import write as write_bytes
from tools.common import not_found, with_tier_flag

DEFINITION = ToolDefinition(
    name="copy",
    group=ToolGroup.MUTATE_STRUCTURE,
    composition=("read", "write"),
    friction=frozenset({Friction.OVERWRITE}),
    policy_union=frozenset({ToolGroup.READ, ToolGroup.MUTATE_STRUCTURE}),
    policy_map={"src": ToolGroup.READ, "dest": ToolGroup.MUTATE_STRUCTURE},
    targets=Targets.BOTH,
    pagination=False,
    git=True,
)

DESCRIPTION = (
    "Copy a file or folder to a new path. Use this to duplicate content — "
    "never read a file and re-write it to copy it. Replacing an existing "
    "destination file requires overwrite=true."
)


def run(src, dest, overwrite: bool = False,
        tier_threshold: int = DEFAULT_SIZE_THRESHOLD) -> str:
    src, dest = Path(src), Path(dest)
    if not src.exists():
        raise ToolError(not_found(src))
    if src == dest:
        raise ToolError("src and dest are identical — nothing to copy")
    if dest.is_dir():
        raise ToolError(
            f"'{dest}' is an existing folder — pass the full destination path, "
            f"e.g. '{dest / src.name}'"
        )
    if src.is_dir() and dest.is_relative_to(src):
        raise ToolError(f"cannot copy '{src}' into itself")
    if dest.is_file() and not overwrite:
        raise ToolError(f"destination '{dest}' exists — pass overwrite=true")
    if not dest.parent.is_dir():
        raise ToolError(f"{not_found(dest.parent)} — create it first with create_dir")
    if src.is_dir():
        _copy_tree(src, dest)
    else:
        write_bytes(dest, read_bytes(src))
    result = f"copied '{src}' → '{dest}'"
    if dest.is_file():
        result = with_tier_flag(result, dest, tier_threshold)
    return result


TOOL = Tool(definition=DEFINITION, description=DESCRIPTION, handler=run)


def _copy_tree(src: Path, dest: Path) -> None:
    os.makedirs(dest)
    for root, dirnames, filenames in os.walk(src):
        base = dest / Path(root).relative_to(src)
        for name in dirnames:
            os.makedirs(base / name, exist_ok=True)
        for name in filenames:
            write_bytes(base / name, read_bytes(Path(root) / name))
