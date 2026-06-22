"""Tool wrappers and the human approval gate for friction.

Every FrictionRequired carries a `kwarg` (set in core/friction.py — the only
place that knows which check fired): the parameter the agent layer should
force to True on a human-approved retry, or None when there's nothing to
force and the model must self-correct instead (a zero-match edit). Gated
kwargs (overwrite, recursive, replace_all) pause the run via interrupt() and
ask the human, who can approve once ("yes") or, for overwrite/recursive,
for the rest of the session ("always") — replace_all always re-asks, since
each ambiguous edit is a fresh decision.
"""

from langchain_core.tools import StructuredTool, ToolException
from langgraph.types import interrupt

from agent.schema import args_schema_for
from core.errors import FrictionRequired, ToolError
from tools import ALL_TOOLS


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
            kwarg = error.kwarg
            if kwarg is None:
                raise ToolException(message)  # zero-match edit — model self-corrects, no gate
            if not approvals.is_allowed(kwarg):
                decision = interrupt({"tool": name, "args": kwargs, "message": message})
                if decision not in ("yes", "always"):
                    raise ToolException(
                        f"the user did not approve this {kwarg} — try a different approach"
                    )
                if decision == "always" and kwarg != "replace_all":
                    approvals.allow_always(kwarg)
            try:
                return pipeline.call(name, **{**kwargs, kwarg: True})
            except ToolError as second_error:
                raise ToolException(str(second_error))
        except ToolError as error:
            raise ToolException(str(error))

    handler.__name__ = name
    return handler


def build_tools(pipeline, approvals, tools=None) -> list[StructuredTool]:
    tools = ALL_TOOLS.values() if tools is None else tools
    return [
        StructuredTool.from_function(
            func=_make_handler(tool, pipeline, approvals),
            name=tool.definition.name,
            description=tool.description,
            args_schema=args_schema_for(tool),
        )
        for tool in tools
    ]
