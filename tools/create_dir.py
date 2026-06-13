"""Execute-stage handler for the create_dir tool.

Silently drops a .gitkeep inside the new folder so the empty directory
is tracked and rollback restores it (git does not track empty dirs);
list_dir filters .gitkeep from display. Parents are created by walking
the create_dir primitive up the missing ancestry. The model-facing
contract lives in DESCRIPTION.
"""

from pathlib import Path

from core.errors import ToolError
from core.tool import Tool
from core.tool_definition import PRIMITIVE, Targets, ToolDefinition, ToolGroup
from functions import create_dir as make_dir
from functions import write as write_bytes

DEFINITION = ToolDefinition(
    name="create_dir",
    group=ToolGroup.MUTATE_STRUCTURE,
    composition=PRIMITIVE,
    policy_union=frozenset({ToolGroup.MUTATE_STRUCTURE}),
    targets=Targets.FOLDERS,
    pagination=False,
    git=True,
)

DESCRIPTION = "Create a directory (parents created as needed)."


def run(path) -> str:
    path = Path(path)
    if path.is_dir():
        return f"'{path}' already exists"
    if path.exists():
        raise ToolError(f"'{path}' is a file — cannot create a folder there")
    missing = []
    current = path
    while not current.exists():
        missing.append(current)
        current = current.parent
    for folder in reversed(missing):
        make_dir(folder)
    write_bytes(path / ".gitkeep", b"")
    parents = len(missing) - 1
    if parents:
        plural = "folder" if parents == 1 else "folders"
        return f"created '{path}' (including {parents} parent {plural})"
    return f"created '{path}'"


TOOL = Tool(definition=DEFINITION, description=DESCRIPTION, handler=run)
