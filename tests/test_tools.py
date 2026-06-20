import pytest
from langchain_core.tools import ToolException

from agent.tools import Approvals, build_tools
from cli.repl import ToolActivityCallback
from core.policy import PolicyDecision
from tests.test_pipeline import make_pipeline


class DenyWrite:
    def check(self, path, group, tool=None):
        if group.value == "mutate-content":
            return PolicyDecision(allowed=False, reason="writes are disabled this session")
        return PolicyDecision(allowed=True)


def get_tool(tools, name):
    return next(t for t in tools if t.name == name)


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


def test_unique_match_is_autonomous_no_interrupt(tmp_path, monkeypatch):
    pipeline, root, _ = make_pipeline(tmp_path)
    (root / "a.txt").write_text("one\ntwo\nthree\n")

    def boom(payload):
        raise AssertionError("interrupt should not be called for UNIQUE_MATCH")

    monkeypatch.setattr("agent.tools.interrupt", boom)
    tools = build_tools(pipeline, Approvals())
    edit = get_tool(tools, "edit")

    with pytest.raises(ToolException) as excinfo:
        edit.func(path="a.txt", old_str="nonexistent", new_str="x")

    assert "re-read and retry" in str(excinfo.value)


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


def test_read_tool_invoke_triggers_start_print_only(tmp_path, capsys):
    pipeline, root, _ = make_pipeline(tmp_path)
    (root / "a.txt").write_text("hello\n")
    tools = build_tools(pipeline, Approvals())
    read = get_tool(tools, "read")
    callback = ToolActivityCallback()

    read.invoke({"path": "a.txt"}, config={"callbacks": [callback]})

    out = capsys.readouterr().out
    assert "[read] a.txt" in out
    assert "hello" not in out
