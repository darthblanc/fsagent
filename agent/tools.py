"""Tool wrappers and the human approval gate for OVERWRITE/RECURSIVE friction.

UNIQUE_MATCH friction passes straight through as a ToolException — the
model retries with corrected old_str/new_str itself (the existing
two-attempt protocol). OVERWRITE/RECURSIVE pause the run via interrupt()
and ask the human, who can approve once ("yes") or for the rest of the
session ("always").
"""

from langchain_core.tools import StructuredTool, ToolException
from langgraph.types import interrupt

from agent.schema import args_schema_for
from core.errors import FrictionRequired, ToolError
from tools import ALL_TOOLS

_CONFIRM_KWARGS = {"overwrite=true": "overwrite", "recursive=true": "recursive"}


class Approvals:
    """Tracks 'always allow' decisions for one session."""

    def __init__(self):
        self._always: set[str] = set()

    def is_allowed(self, kwarg: str) -> bool:
        return kwarg in self._always

    def allow_always(self, kwarg: str) -> None:
        self._always.add(kwarg)


def _make_handler(tool, pipeline, approvals):
    name = tool.definition.name

    def handler(**kwargs):
        try:
            return pipeline.call(name, **kwargs)
        except FrictionRequired as error:
            message = str(error)
            kwarg = next((k for pat, k in _CONFIRM_KWARGS.items() if pat in message), None)
            if kwarg is None:
                raise ToolException(message)  # UNIQUE_MATCH — model self-corrects, no gate
            if not approvals.is_allowed(kwarg):
                decision = interrupt({"tool": name, "args": kwargs, "message": message})
                if decision == "always":
                    approvals.allow_always(kwarg)
                elif decision != "yes":
                    raise ToolException(
                        f"the user did not approve this {kwarg} — try a different approach"
                    )
            try:
                return pipeline.call(name, **{**kwargs, kwarg: True})
            except ToolError as second_error:
                raise ToolException(str(second_error))
        except ToolError as error:
            raise ToolException(str(error))

    handler.__name__ = name
    return handler


def build_tools(pipeline, approvals) -> list[StructuredTool]:
    return [
        StructuredTool.from_function(
            func=_make_handler(tool, pipeline, approvals),
            name=tool.definition.name,
            description=tool.description,
            args_schema=args_schema_for(tool),
        )
        for tool in ALL_TOOLS.values()
    ]
