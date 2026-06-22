import pytest
from langchain_core.tools import ToolException

from agent.subagent import build_subagent_tool, read_only_tools
from core.tool_definition import ToolGroup
from tests.test_pipeline import make_pipeline
from tools import ALL_TOOLS


def test_read_only_tools_excludes_mutating_groups():
    names = {tool.definition.name for tool in read_only_tools()}

    assert names == {"read", "inspect", "list_dir", "glob", "grep"}
    for tool in read_only_tools():
        assert tool.definition.group in (ToolGroup.READ, ToolGroup.SEARCH)


def test_read_only_tools_enforces_real_pipeline(tmp_path):
    from agent.tools import Approvals, build_tools

    pipeline, root, _ = make_pipeline(tmp_path)
    tools = build_tools(pipeline, Approvals(), tools=read_only_tools())
    read = next(t for t in tools if t.name == "read")

    with pytest.raises(ToolException) as excinfo:
        read.func(path="../escape.txt")

    assert str(excinfo.value) == (
        f"'../escape.txt' resolves outside the sandbox — the world ends at {root}"
    )


class FakeMessage:
    def __init__(self, text):
        self.text = text


class FakeSubagent:
    def __init__(self, response=None, error=None):
        self._response = response
        self._error = error
        self.invocations = []

    def invoke(self, input_, config=None):
        self.invocations.append(input_)
        if self._error is not None:
            raise self._error
        return self._response


def test_build_subagent_tool_constructs_nested_agent_with_read_only_tools(tmp_path, monkeypatch):
    pipeline, _, _ = make_pipeline(tmp_path)
    captured = {}

    def fake_create_agent(model, **kwargs):
        captured["model"] = model
        captured.update(kwargs)
        return FakeSubagent(response={"messages": [FakeMessage("done")]})

    monkeypatch.setattr("agent.subagent.create_agent", fake_create_agent)

    build_subagent_tool("fake-model", pipeline, "system prompt")

    assert captured["model"] == "fake-model"
    assert captured["name"] == "explorer"
    assert captured["system_prompt"] == "system prompt"
    tool_names = {t.name for t in captured["tools"]}
    assert tool_names == {"read", "inspect", "list_dir", "glob", "grep"}


def test_dispatch_invokes_nested_agent_and_returns_final_text(tmp_path, monkeypatch):
    pipeline, _, _ = make_pipeline(tmp_path)
    fake_subagent = FakeSubagent(response={"messages": [FakeMessage("synthesis")]})
    monkeypatch.setattr("agent.subagent.create_agent", lambda model, **kwargs: fake_subagent)

    tool = build_subagent_tool("fake-model", pipeline, "system prompt")
    result = tool.func(task="find all configs")

    assert result == "synthesis"
    assert fake_subagent.invocations == [
        {"messages": [{"role": "user", "content": "find all configs"}]}
    ]


def test_dispatch_wraps_unexpected_exception_in_tool_exception(tmp_path, monkeypatch):
    pipeline, _, _ = make_pipeline(tmp_path)
    fake_subagent = FakeSubagent(error=RuntimeError("boom"))
    monkeypatch.setattr("agent.subagent.create_agent", lambda model, **kwargs: fake_subagent)

    tool = build_subagent_tool("fake-model", pipeline, "system prompt")

    with pytest.raises(ToolException) as excinfo:
        tool.func(task="find all configs")

    assert "boom" in str(excinfo.value)


def test_dispatch_tool_description_mentions_parallel_use(tmp_path, monkeypatch):
    pipeline, _, _ = make_pipeline(tmp_path)
    monkeypatch.setattr(
        "agent.subagent.create_agent",
        lambda model, **kwargs: FakeSubagent(response={"messages": [FakeMessage("done")]}),
    )

    tool = build_subagent_tool("fake-model", pipeline, "system prompt")

    lower = tool.description.lower()
    assert "multiple" in lower or "parallel" in lower or "concurrently" in lower
