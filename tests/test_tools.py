import pytest
from langchain_core.tools import ToolException

from agent.tools import Approvals, build_tools
from cli.repl import ToolActivityCallback
from core.policy import PolicyDecision
from tests.test_pipeline import make_pipeline
from tools import ALL_TOOLS


class DenyWrite:
    def check(self, path, group, tool=None):
        if group.value == "mutate-content":
            return PolicyDecision(allowed=False, reason="writes are disabled this session")
        return PolicyDecision(allowed=True)


def get_tool(tools, name):
    return next(t for t in tools if t.name == name)


def test_build_tools_accepts_explicit_subset(tmp_path):
    pipeline, _, _ = make_pipeline(tmp_path)
    tools = build_tools(pipeline, Approvals(), tools=[ALL_TOOLS["read"]])

    assert [t.name for t in tools] == ["read"]


def test_write_succeeds_on_fresh_path(tmp_path):
    pipeline, root, _ = make_pipeline(tmp_path)
    tools = build_tools(pipeline, Approvals())
    write = get_tool(tools, "write")

    result = write.func(path="note.txt", content="hello\n")

    assert (root / "note.txt").read_text() == "hello\n"
    assert "+hello" in result


def test_sandbox_violation_raises_tool_exception(tmp_path):
    pipeline, root, _ = make_pipeline(tmp_path)
    tools = build_tools(pipeline, Approvals())
    write = get_tool(tools, "write")

    with pytest.raises(ToolException) as excinfo:
        write.func(path="../escape.txt", content="x")

    assert str(excinfo.value) == (
        f"'../escape.txt' resolves outside the sandbox — the world ends at {root}"
    )


def test_policy_denial_raises_tool_exception(tmp_path):
    pipeline, root, _ = make_pipeline(tmp_path, policy=DenyWrite())
    tools = build_tools(pipeline, Approvals())
    write = get_tool(tools, "write")

    with pytest.raises(ToolException) as excinfo:
        write.func(path="note.txt", content="hello\n")

    assert str(excinfo.value) == (
        f"policy denied mutate-content on '{root / 'note.txt'}': "
        "writes are disabled this session"
    )


def test_unique_match_zero_match_is_autonomous_no_interrupt(tmp_path, monkeypatch):
    pipeline, root, _ = make_pipeline(tmp_path)
    (root / "a.txt").write_text("one\ntwo\nthree\n")

    def boom(payload):
        raise AssertionError("interrupt should not be called for a zero-match edit")

    monkeypatch.setattr("agent.tools.interrupt", boom)
    tools = build_tools(pipeline, Approvals())
    edit = get_tool(tools, "edit")

    with pytest.raises(ToolException) as excinfo:
        edit.func(path="a.txt", old_str="nonexistent", new_str="x")

    assert "re-read and retry" in str(excinfo.value)


def test_unique_match_ambiguous_interrupt_yes_replaces_all(tmp_path, monkeypatch):
    pipeline, root, _ = make_pipeline(tmp_path)
    (root / "a.txt").write_text("foo\nbar\nfoo\n")
    monkeypatch.setattr("agent.tools.interrupt", lambda payload: "yes")
    tools = build_tools(pipeline, Approvals())
    edit = get_tool(tools, "edit")

    result = edit.func(path="a.txt", old_str="foo", new_str="FOO")

    assert (root / "a.txt").read_text() == "FOO\nbar\nFOO\n"
    assert "+FOO" in result


def test_unique_match_ambiguous_declined_raises_tool_exception(tmp_path, monkeypatch):
    pipeline, root, _ = make_pipeline(tmp_path)
    (root / "a.txt").write_text("foo\nbar\nfoo\n")
    monkeypatch.setattr("agent.tools.interrupt", lambda payload: "no")
    tools = build_tools(pipeline, Approvals())
    edit = get_tool(tools, "edit")

    with pytest.raises(ToolException) as excinfo:
        edit.func(path="a.txt", old_str="foo", new_str="FOO")

    assert "did not approve" in str(excinfo.value)
    assert (root / "a.txt").read_text() == "foo\nbar\nfoo\n"


def test_unique_match_ambiguous_always_does_not_persist(tmp_path, monkeypatch):
    pipeline, root, _ = make_pipeline(tmp_path)
    (root / "a.txt").write_text("foo\nbar\nfoo\n")
    (root / "b.txt").write_text("baz\nfoo\nfoo\n")
    calls = []
    monkeypatch.setattr("agent.tools.interrupt", lambda payload: calls.append(payload) or "always")
    approvals = Approvals()
    tools = build_tools(pipeline, approvals)
    edit = get_tool(tools, "edit")

    edit.func(path="a.txt", old_str="foo", new_str="FOO")
    edit.func(path="b.txt", old_str="foo", new_str="FOO")

    assert len(calls) == 2  # "always" must not suppress the second prompt
    assert not approvals.is_allowed("replace_all")


def test_unique_match_ambiguous_interrupt_payload_shape(tmp_path, monkeypatch):
    pipeline, root, _ = make_pipeline(tmp_path)
    (root / "a.txt").write_text("foo\nbar\nfoo\n")
    captured = {}

    def fake_interrupt(payload):
        captured.update(payload)
        return "yes"

    monkeypatch.setattr("agent.tools.interrupt", fake_interrupt)
    tools = build_tools(pipeline, Approvals())
    edit = get_tool(tools, "edit")

    edit.func(path="a.txt", old_str="foo", new_str="FOO")

    assert captured["tool"] == "edit"
    assert captured["message"] == (
        "matched 2 locations (lines 1, 3) — pass replace_all=true to "
        "replace all of them, or include more surrounding context to "
        "disambiguate one"
    )


def test_model_supplied_overwrite_is_dropped_by_schema_validation(tmp_path, monkeypatch):
    """Regression test for the self-approval bypass: a model can no longer
    smuggle overwrite=true through its own tool call — Pydantic silently
    drops the field since it's excluded from the schema, so the friction
    gate always fires and interrupt() is always reached, even when the
    model's raw call already says overwrite=true."""
    pipeline, root, _ = make_pipeline(tmp_path)
    (root / "r.txt").write_text("old\n")
    calls = []
    monkeypatch.setattr("agent.tools.interrupt", lambda payload: calls.append(payload) or "no")
    tools = build_tools(pipeline, Approvals())
    write = get_tool(tools, "write")

    with pytest.raises(ToolException, match="did not approve"):
        write.invoke({"path": "r.txt", "content": "clobbered\n", "overwrite": True})

    assert len(calls) == 1  # interrupt() was reached despite the model's overwrite=True
    assert (root / "r.txt").read_text() == "old\n"


def test_overwrite_interrupt_yes_allows_once(tmp_path, monkeypatch):
    pipeline, root, _ = make_pipeline(tmp_path)
    (root / "r.txt").write_text("old\n")
    monkeypatch.setattr("agent.tools.interrupt", lambda payload: "yes")
    approvals = Approvals()
    tools = build_tools(pipeline, approvals)
    write = get_tool(tools, "write")

    result = write.func(path="r.txt", content="new\n")

    assert (root / "r.txt").read_text() == "new\n"
    assert "+new" in result
    assert not approvals.is_allowed("overwrite")


def test_overwrite_interrupt_yes_with_explicit_default_kwarg(tmp_path, monkeypatch):
    """StructuredTool fills in the 'overwrite' default (False) before
    calling the handler — the retry call must not collide with it."""
    pipeline, root, _ = make_pipeline(tmp_path)
    (root / "r.txt").write_text("old\n")
    monkeypatch.setattr("agent.tools.interrupt", lambda payload: "yes")
    tools = build_tools(pipeline, Approvals())
    write = get_tool(tools, "write")

    result = write.func(path="r.txt", content="new\n", overwrite=False)

    assert (root / "r.txt").read_text() == "new\n"
    assert "+new" in result


def test_overwrite_interrupt_payload_shape(tmp_path, monkeypatch):
    pipeline, root, _ = make_pipeline(tmp_path)
    (root / "r.txt").write_text("old\nsecond\n")
    captured = {}

    def fake_interrupt(payload):
        captured.update(payload)
        return "yes"

    monkeypatch.setattr("agent.tools.interrupt", fake_interrupt)
    tools = build_tools(pipeline, Approvals())
    write = get_tool(tools, "write")

    write.func(path="r.txt", content="new\n")

    assert captured["tool"] == "write"
    assert captured["args"] == {"path": "r.txt", "content": "new\n"}
    assert captured["message"] == (
        f"'{root / 'r.txt'}' exists (2 lines) — pass overwrite=true, or use edit"
    )


def test_overwrite_interrupt_always_persists_within_approvals(tmp_path, monkeypatch):
    pipeline, root, _ = make_pipeline(tmp_path)
    (root / "a.txt").write_text("old-a\n")
    (root / "b.txt").write_text("old-b\n")
    calls = []

    def fake_interrupt(payload):
        calls.append(payload)
        return "always"

    monkeypatch.setattr("agent.tools.interrupt", fake_interrupt)
    approvals = Approvals()
    tools = build_tools(pipeline, approvals)
    write = get_tool(tools, "write")

    write.func(path="a.txt", content="new-a\n")
    write.func(path="b.txt", content="new-b\n")

    assert len(calls) == 1
    assert (root / "a.txt").read_text() == "new-a\n"
    assert (root / "b.txt").read_text() == "new-b\n"
    assert approvals.is_allowed("overwrite")


def test_overwrite_declined_raises_tool_exception(tmp_path, monkeypatch):
    pipeline, root, _ = make_pipeline(tmp_path)
    (root / "r.txt").write_text("old\n")
    monkeypatch.setattr("agent.tools.interrupt", lambda payload: "no")
    tools = build_tools(pipeline, Approvals())
    write = get_tool(tools, "write")

    with pytest.raises(ToolException) as excinfo:
        write.func(path="r.txt", content="new\n")

    assert "did not approve" in str(excinfo.value)
    assert (root / "r.txt").read_text() == "old\n"


def test_recursive_interrupt_yes_deletes(tmp_path, monkeypatch):
    pipeline, root, _ = make_pipeline(tmp_path)
    (root / "folder").mkdir()
    (root / "folder" / "file.txt").write_text("x")
    monkeypatch.setattr("agent.tools.interrupt", lambda payload: "yes")
    tools = build_tools(pipeline, Approvals())
    delete = get_tool(tools, "delete")

    result = delete.func(path="folder")

    assert "deleted" in result
    assert not (root / "folder").exists()


def test_recursive_declined_raises_tool_exception(tmp_path, monkeypatch):
    pipeline, root, _ = make_pipeline(tmp_path)
    (root / "folder").mkdir()
    (root / "folder" / "file.txt").write_text("x")
    monkeypatch.setattr("agent.tools.interrupt", lambda payload: "no")
    tools = build_tools(pipeline, Approvals())
    delete = get_tool(tools, "delete")

    with pytest.raises(ToolException) as excinfo:
        delete.func(path="folder")

    assert "did not approve" in str(excinfo.value)
    assert (root / "folder").exists()


def test_write_tool_invoke_triggers_callback_with_path_and_diff(tmp_path, capsys):
    pipeline, root, _ = make_pipeline(tmp_path)
    tools = build_tools(pipeline, Approvals())
    write = get_tool(tools, "write")
    callback = ToolActivityCallback()

    write.invoke({"path": "note.txt", "content": "hello\n"}, config={"callbacks": [callback]})

    out = capsys.readouterr().out
    assert "[write] note.txt" in out
    assert "+hello" in out


def test_edit_tool_invoke_triggers_callback_with_diff(tmp_path, capsys):
    pipeline, root, _ = make_pipeline(tmp_path)
    (root / "a.txt").write_text("old\n")
    tools = build_tools(pipeline, Approvals())
    edit = get_tool(tools, "edit")
    callback = ToolActivityCallback()

    edit.invoke({"path": "a.txt", "old_str": "old", "new_str": "new"}, config={"callbacks": [callback]})

    out = capsys.readouterr().out
    assert "[edit] a.txt" in out
    assert "+new" in out


def test_read_tool_invoke_triggers_callback_with_path_and_content(tmp_path, capsys):
    pipeline, root, _ = make_pipeline(tmp_path)
    (root / "a.txt").write_text("hello\n")
    tools = build_tools(pipeline, Approvals())
    read = get_tool(tools, "read")
    callback = ToolActivityCallback()

    read.invoke({"path": "a.txt"}, config={"callbacks": [callback]})

    out = capsys.readouterr().out
    assert "[read] a.txt" in out
    assert "hello" in out
