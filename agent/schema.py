"""Per-tool args_schema generation for StructuredTool.

agent/tools.py wraps each handler in a function that takes **kwargs, so
StructuredTool can't infer a schema from the wrapper itself — it must be
built from the handler's own signature instead.
"""

import inspect
from typing import Literal, Optional, Union

from pydantic import BaseModel, Field, create_model

from core.tool import Tool

# Injected by Pipeline._handler_extras, or a friction-confirmation flag the
# agent layer sets only after a human approves a retry — never model-settable.
_EXCLUDED = {
    "policy", "tier_threshold", "sandbox_root",
    "overwrite", "recursive", "replace_all",
}

# (tool_name, param_name) -> (annotation, Field) overrides, for params whose
# handler signature doesn't carry enough type information on its own.
_OVERRIDES = {
    ("read", "selector"): (
        Optional[Union[str, dict]],
        Field(
            default=None,
            description=(
                "Narrows the returned content. For .json files, a dotted "
                "path string (e.g. 'config.database.host'). For .csv "
                "files, an object like "
                '{"columns": ["name"], "rows": "head:50"}. For .md files, '
                "a heading name. Omit to read the whole file."
            ),
        ),
    ),
    ("grep", "mode"): (
        Literal["files", "content"],
        Field(default="files"),
    ),
}


def args_schema_for(tool: Tool) -> type[BaseModel]:
    name = tool.definition.name
    fields: dict[str, tuple] = {}
    for param_name, param in inspect.signature(tool.handler).parameters.items():
        if param_name in _EXCLUDED:
            continue
        override = _OVERRIDES.get((name, param_name))
        if override is not None:
            fields[param_name] = override
            continue
        annotation = param.annotation if param.annotation is not inspect.Parameter.empty else str
        default = ... if param.default is inspect.Parameter.empty else param.default
        fields[param_name] = (annotation, default)
    return create_model(f"{name}_args", **fields)
