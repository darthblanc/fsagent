"""A read-only sub-agent exposed to the main agent as the `explore` tool.

Restricted to the READ/SEARCH tool groups, which declare no friction
(`Friction.OVERWRITE/RECURSIVE/UNIQUE_MATCH` only exist on
write/edit/move/copy/delete) — so the sub-agent can never raise
FrictionRequired, and never needs interrupt()/Command(resume=...) plumbing.
That matters because a nested agent dispatched from inside a tool call may
run inside LangGraph's tool-call thread pool, where there is no path back to
the outer REPL's resume loop.

It shares the main agent's Pipeline (same Sandbox + Policy) rather than
building its own, so it can't escape the sandbox or any policy rule the main
agent doesn't already see — see core/pipeline.py and core/policy.py for why
that sharing is safe under concurrent dispatches (Sandbox is immutable,
YamlPolicy.check is a pure function, and Trajectory appends are safe under
POSIX O_APPEND).
"""

from langchain.agents import create_agent
from langchain_core.tools import StructuredTool, ToolException

from agent.tools import Approvals, build_tools
from core.tool_definition import ToolGroup
from tools import ALL_TOOLS

_READ_ONLY_GROUPS = {ToolGroup.READ, ToolGroup.SEARCH}


def read_only_tools() -> list:
    return [tool for tool in ALL_TOOLS.values() if tool.definition.group in _READ_ONLY_GROUPS]


def build_subagent_tool(model, pipeline, system_prompt) -> StructuredTool:
    subagent = create_agent(
        model,
        tools=build_tools(pipeline, Approvals(), tools=read_only_tools()),
        system_prompt=system_prompt,
        name="explorer",
    )

    def explore(task: str) -> str:
        try:
            result = subagent.invoke({"messages": [{"role": "user", "content": task}]})
        except Exception as error:
            raise ToolException(str(error)) from error
        return result["messages"][-1].text

    return StructuredTool.from_function(
        func=explore,
        name="explore",
        description=(
            "Delegate a read-only investigation to a sub-agent restricted to "
            "read/search tools (read, inspect, list_dir, glob, grep). Give it "
            "a self-contained task description and it returns a written "
            "summary, without spending your own context on every "
            "intermediate read/grep call. Call it multiple times in the same "
            "turn for independent investigations — they run concurrently."
        ),
    )
