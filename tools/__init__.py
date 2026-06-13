from tools.append import TOOL as APPEND_TOOL
from tools.copy import TOOL as COPY_TOOL
from tools.create_dir import TOOL as CREATE_DIR_TOOL
from tools.delete import TOOL as DELETE_TOOL
from tools.edit import TOOL as EDIT_TOOL
from tools.glob import TOOL as GLOB_TOOL
from tools.grep import TOOL as GREP_TOOL
from tools.inspect import TOOL as INSPECT_TOOL
from tools.list_dir import TOOL as LIST_DIR_TOOL
from tools.move import TOOL as MOVE_TOOL
from tools.read import TOOL as READ_TOOL
from tools.write import TOOL as WRITE_TOOL

ALL_TOOLS = {
    tool.definition.name: tool
    for tool in (
        READ_TOOL, INSPECT_TOOL, LIST_DIR_TOOL, GLOB_TOOL, GREP_TOOL,
        WRITE_TOOL, EDIT_TOOL, APPEND_TOOL, CREATE_DIR_TOOL, MOVE_TOOL, COPY_TOOL,
        DELETE_TOOL,
    )
}
