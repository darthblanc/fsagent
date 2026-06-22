import os
import re
import readline
import uuid

import pytest
from langchain.agents.middleware import SummarizationMiddleware
from langchain_anthropic.middleware import AnthropicPromptCachingMiddleware
from langchain_core.messages import ToolMessage
from langchain_core.tools import StructuredTool
from langgraph.types import Interrupt

from cli.models import load_model_config
from cli.repl import (
    SUMMARIZATION_MODEL,
    AnnouncingSummarizationMiddleware,
    ToolActivityCallback,
    build_pipeline,
    cli_decision,
    load_env,
    load_history,
    main,
    make_session_id,
    save_history,
    stream_response,
)


@pytest.fixture(autouse=True)
def _isolate_history_file(tmp_path, monkeypatch):
    monkeypatch.setattr("cli.repl.HISTORY_FILE", tmp_path / "history")


def test_load_env_reads_dotenv_file(tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text("FSAGENT_TEST_VAR=from-dotenv\n")

    try:
        load_env(env_path)
        assert os.environ["FSAGENT_TEST_VAR"] == "from-dotenv"
    finally:
        os.environ.pop("FSAGENT_TEST_VAR", None)


def test_load_env_does_not_override_existing_env_var(tmp_path, monkeypatch):
    env_path = tmp_path / ".env"
    env_path.write_text("FSAGENT_TEST_VAR=from-dotenv\n")
    monkeypatch.setenv("FSAGENT_TEST_VAR", "from-shell")

    load_env(env_path)

    assert os.environ["FSAGENT_TEST_VAR"] == "from-shell"


def test_load_env_missing_file_does_not_raise(tmp_path):
    load_env(tmp_path / "no-such-env")


def test_load_env_sets_default_langsmith_project(tmp_path, monkeypatch):
    monkeypatch.delenv("LANGSMITH_PROJECT", raising=False)
    monkeypatch.delenv("LANGCHAIN_PROJECT", raising=False)

    try:
        load_env(tmp_path / "no-such-env")
        assert os.environ["LANGSMITH_PROJECT"] == "fsagent"
    finally:
        os.environ.pop("LANGSMITH_PROJECT", None)


def test_load_env_does_not_override_existing_langsmith_project(tmp_path, monkeypatch):
    monkeypatch.setenv("LANGSMITH_PROJECT", "custom-project")

    load_env(tmp_path / "no-such-env")

    assert os.environ["LANGSMITH_PROJECT"] == "custom-project"


def test_load_env_does_not_override_existing_langchain_project(tmp_path, monkeypatch):
    monkeypatch.delenv("LANGSMITH_PROJECT", raising=False)
    monkeypatch.setenv("LANGCHAIN_PROJECT", "custom-project")

    try:
        load_env(tmp_path / "no-such-env")
        assert "LANGSMITH_PROJECT" not in os.environ
    finally:
        os.environ.pop("LANGSMITH_PROJECT", None)


def test_make_session_id_format():
    session_id = make_session_id()
    assert re.fullmatch(r"s-\d{8}T\d{6}Z-[0-9a-f]{8}", session_id)


def test_build_pipeline_works(tmp_path):
    sandbox_root = tmp_path / "sandbox"
    sandbox_root.mkdir()
    trajectories_dir = tmp_path / "trajectories"
    trajectories_dir.mkdir()

    pipeline = build_pipeline(
        "s-test", sandbox_root=sandbox_root, trajectories_dir=trajectories_dir
    )
    result = pipeline.call("write", path="note.txt", content="hi\n")

    assert (sandbox_root / "note.txt").read_text() == "hi\n"
    assert (trajectories_dir / "s-test.jsonl").exists()
    assert "+hi" in result


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("y", "yes"),
        ("yes", "yes"),
        ("Y", "yes"),
        ("YES", "yes"),
        ("a", "always"),
        ("always", "always"),
        ("ALWAYS", "always"),
        ("n", "no"),
        ("no", "no"),
        ("", "no"),
        ("whatever", "no"),
    ],
)
def test_cli_decision_maps_input(monkeypatch, raw, expected):
    monkeypatch.setattr("builtins.input", lambda prompt="": raw)
    payload = {"tool": "write", "args": {"path": "x"}, "message": "msg"}
    assert cli_decision(payload) == expected


def test_on_tool_start_prints_path_and_action_for_watched_tools(capsys):
    callback = ToolActivityCallback()
    run_id = uuid.uuid4()

    callback.on_tool_start(
        {"name": "write"}, "", run_id=run_id, inputs={"path": "note.txt", "content": "hi"}
    )

    assert "[write] note.txt" in capsys.readouterr().out


def test_on_tool_start_prints_header_for_any_tool(capsys):
    callback = ToolActivityCallback()
    run_id = uuid.uuid4()

    callback.on_tool_start({"name": "list_dir"}, "", run_id=run_id, inputs={"path": "."})

    assert "[list_dir] ." in capsys.readouterr().out


@pytest.mark.parametrize(
    "inputs, expected_label",
    [
        ({"src": "a.txt", "dest": "b.txt"}, "a.txt"),
        ({"pattern": "TODO", "scope": "src"}, "TODO"),
        ({"task": "find the config loader"}, "find the config loader"),
        ({"limit": 50}, ""),
    ],
)
def test_on_tool_start_falls_back_through_label_keys(capsys, inputs, expected_label):
    callback = ToolActivityCallback()
    run_id = uuid.uuid4()

    callback.on_tool_start({"name": "tool"}, "", run_id=run_id, inputs=inputs)

    assert f"[tool] {expected_label}" in capsys.readouterr().out


def test_on_tool_end_prints_diff_for_write(capsys):
    callback = ToolActivityCallback()
    run_id = uuid.uuid4()
    callback.on_tool_start(
        {"name": "write"}, "", run_id=run_id, inputs={"path": "note.txt", "content": "hi"}
    )
    capsys.readouterr()

    callback.on_tool_end("--- a/note.txt\n+++ b/note.txt\n+hi", run_id=run_id)

    assert "+hi" in capsys.readouterr().out


def test_on_tool_end_unwraps_tool_message_content(capsys):
    # LangGraph's ToolNode invokes tools with a ToolCall-shaped input, which
    # makes the tool wrap its string return value in a ToolMessage before
    # on_tool_end sees it — print the diff text, not the message repr.
    callback = ToolActivityCallback()
    run_id = uuid.uuid4()
    callback.on_tool_start(
        {"name": "edit"}, "", run_id=run_id, inputs={"path": "hello.py", "old_str": "a", "new_str": "b"}
    )
    capsys.readouterr()

    diff = '--- a/hello.py\n+++ b/hello.py\n@@ -1 +1 @@\n-a\n+b'
    callback.on_tool_end(ToolMessage(content=diff, name="edit", tool_call_id="call_1"), run_id=run_id)

    out = capsys.readouterr().out
    assert out == diff + "\n"


def test_on_tool_end_prints_result_for_read(capsys):
    callback = ToolActivityCallback()
    run_id = uuid.uuid4()
    callback.on_tool_start({"name": "read"}, "", run_id=run_id, inputs={"path": "note.txt"})
    capsys.readouterr()

    callback.on_tool_end("     1\thello", run_id=run_id)

    assert capsys.readouterr().out == "     1\thello\n"


def test_on_tool_end_for_unknown_run_id_does_not_raise():
    callback = ToolActivityCallback()
    callback.on_tool_end("whatever", run_id=uuid.uuid4())


def test_on_tool_error_clears_state_without_printing(capsys):
    callback = ToolActivityCallback()
    run_id = uuid.uuid4()
    callback.on_tool_start(
        {"name": "write"}, "", run_id=run_id, inputs={"path": "note.txt", "content": "x"}
    )
    capsys.readouterr()

    callback.on_tool_error(ValueError("boom"), run_id=run_id)

    assert capsys.readouterr().out == ""
    assert run_id not in callback._runs


class FakeMessage:
    def __init__(self, text):
        self.text = text


class FakeAgent:
    def __init__(self, responses):
        self._responses = list(responses)
        self.configs = []

    def stream(self, _input, config=None, stream_mode=None):
        self.configs.append(config)
        yield from self._responses.pop(0)


def test_stream_response_prints_text_chunks_and_trailing_newline(capsys):
    fake_agent = FakeAgent([[
        ("messages", (FakeMessage("hel"), {})),
        ("messages", (FakeMessage("lo"), {})),
    ]])

    result = stream_response(fake_agent, {"messages": []}, config={})

    assert capsys.readouterr().out == "hello\n"
    assert result is None


def test_stream_response_skips_empty_text_chunks(capsys):
    fake_agent = FakeAgent([[
        ("messages", (FakeMessage(""), {})),
        ("messages", (FakeMessage("ok"), {})),
    ]])

    stream_response(fake_agent, {"messages": []}, config={})

    assert capsys.readouterr().out == "ok\n"


def test_stream_response_skips_tool_message_content(capsys):
    # Tool output is already printed by ToolActivityCallback; stream_response
    # must not also print it, or results show up duplicated and run together
    # with the model's own text (no separating newline between the two).
    fake_agent = FakeAgent([[
        ("messages", (ToolMessage(content="tool output", name="read", tool_call_id="1"), {})),
        ("messages", (FakeMessage("answer"), {})),
    ]])

    stream_response(fake_agent, {"messages": []}, config={})

    assert capsys.readouterr().out == "answer\n"


def test_stream_response_returns_interrupt_payload_without_trailing_newline(capsys):
    payload = {"tool": "write", "args": {}, "message": "exists"}
    fake_agent = FakeAgent([[("values", {"__interrupt__": (Interrupt(value=payload),)})]])

    result = stream_response(fake_agent, {"messages": []}, config={})

    assert result == payload
    assert capsys.readouterr().out == ""


def _drive_input(values):
    iterator = iter(values)

    def fake_input(prompt=""):
        value = next(iterator)
        if value is EOFError:
            raise EOFError
        return value

    return fake_input


def test_main_simple_round_trip(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr("cli.repl.SANDBOX_ROOT", tmp_path / "sandbox")
    monkeypatch.setattr("cli.repl.TRAJECTORIES_DIR", tmp_path / "trajectories")
    (tmp_path / "sandbox").mkdir()
    (tmp_path / "trajectories").mkdir()

    fake_agent = FakeAgent([[("messages", (FakeMessage("hello there"), {}))]])
    monkeypatch.setattr("cli.repl.create_agent", lambda *a, **k: fake_agent)
    monkeypatch.setattr("builtins.input", _drive_input(["hi", EOFError]))

    main(["--model", "anthropic:claude-opus-4-8"])

    assert "hello there" in capsys.readouterr().out


def test_main_handles_interrupt_and_resumes(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr("cli.repl.SANDBOX_ROOT", tmp_path / "sandbox")
    monkeypatch.setattr("cli.repl.TRAJECTORIES_DIR", tmp_path / "trajectories")
    (tmp_path / "sandbox").mkdir()
    (tmp_path / "trajectories").mkdir()

    interrupt_payload = {
        "tool": "write",
        "args": {"path": "r.txt"},
        "message": "'r.txt' exists (1 lines) — pass overwrite=true, or use edit",
    }
    responses = [
        [("values", {"__interrupt__": (Interrupt(value=interrupt_payload),)})],
        [("messages", (FakeMessage("done"), {}))],
    ]
    fake_agent = FakeAgent(responses)
    monkeypatch.setattr("cli.repl.create_agent", lambda *a, **k: fake_agent)
    monkeypatch.setattr("builtins.input", _drive_input(["overwrite r.txt", "yes", EOFError]))

    main(["--model", "anthropic:claude-opus-4-8"])

    out = capsys.readouterr().out
    assert "exists (1 lines)" in out
    assert "done" in out


def test_main_tags_agent_config_for_observability(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr("cli.repl.SANDBOX_ROOT", tmp_path / "sandbox")
    monkeypatch.setattr("cli.repl.TRAJECTORIES_DIR", tmp_path / "trajectories")
    (tmp_path / "sandbox").mkdir()
    (tmp_path / "trajectories").mkdir()
    monkeypatch.setattr("cli.repl.make_session_id", lambda: "s-test")

    fake_agent = FakeAgent([[("messages", (FakeMessage("hello there"), {}))]])
    monkeypatch.setattr("cli.repl.create_agent", lambda *a, **k: fake_agent)
    monkeypatch.setattr("builtins.input", _drive_input(["hi", EOFError]))

    main(["--model", "anthropic:claude-opus-4-8"])

    config = fake_agent.configs[0]
    assert config["configurable"]["thread_id"] == "s-test"
    assert config["tags"] == ["anthropic:claude-opus-4-8"]
    assert config["metadata"] == {"session_id": "s-test", "model": "anthropic:claude-opus-4-8"}


def test_main_attaches_tool_activity_callback(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr("cli.repl.SANDBOX_ROOT", tmp_path / "sandbox")
    monkeypatch.setattr("cli.repl.TRAJECTORIES_DIR", tmp_path / "trajectories")
    (tmp_path / "sandbox").mkdir()
    (tmp_path / "trajectories").mkdir()

    fake_agent = FakeAgent([[("messages", (FakeMessage("hello there"), {}))]])
    monkeypatch.setattr("cli.repl.create_agent", lambda *a, **k: fake_agent)
    monkeypatch.setattr("builtins.input", _drive_input(["hi", EOFError]))

    main(["--model", "anthropic:claude-opus-4-8"])

    callbacks = fake_agent.configs[0]["callbacks"]
    assert len(callbacks) == 1
    assert isinstance(callbacks[0], ToolActivityCallback)


def test_main_uses_model_flag(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr("cli.repl.SANDBOX_ROOT", tmp_path / "sandbox")
    monkeypatch.setattr("cli.repl.TRAJECTORIES_DIR", tmp_path / "trajectories")
    (tmp_path / "sandbox").mkdir()
    (tmp_path / "trajectories").mkdir()

    captured_models = []

    def fake_create_agent(model, **kwargs):
        captured_models.append(model)
        return FakeAgent([[("messages", (FakeMessage("hello there"), {}))]])

    monkeypatch.setattr("cli.repl.create_agent", fake_create_agent)
    monkeypatch.setattr("builtins.input", _drive_input(["hi", EOFError]))

    main(["--model", "ollama:qwen3:8b"])

    assert captured_models == ["ollama:qwen3:8b"]
    assert "model: ollama:qwen3:8b" in capsys.readouterr().out


def test_main_wires_explore_tool_into_main_agent(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr("cli.repl.SANDBOX_ROOT", tmp_path / "sandbox")
    monkeypatch.setattr("cli.repl.TRAJECTORIES_DIR", tmp_path / "trajectories")
    (tmp_path / "sandbox").mkdir()
    (tmp_path / "trajectories").mkdir()

    fake_explore_tool = StructuredTool.from_function(
        func=lambda task: "ok", name="explore", description="delegate a read-only task"
    )
    monkeypatch.setattr("cli.repl.build_subagent_tool", lambda *a, **k: fake_explore_tool)

    captured = {}

    def fake_create_agent(model, **kwargs):
        captured.update(kwargs)
        return FakeAgent([[("messages", (FakeMessage("hello there"), {}))]])

    monkeypatch.setattr("cli.repl.create_agent", fake_create_agent)
    monkeypatch.setattr("builtins.input", _drive_input(["hi", EOFError]))

    main(["--model", "anthropic:claude-opus-4-8"])

    tool_names = [t.name for t in captured["tools"]]
    assert "explore" in tool_names


def test_load_history_missing_file_does_not_raise(tmp_path):
    load_history(tmp_path / "no-such-history")


def test_load_history_unparseable_file_does_not_raise(tmp_path):
    # Missing libedit's "_HiStOrY_V2_" header — e.g. written by a GNU-readline
    # build of Python on a different machine. libedit's reader rejects this
    # with OSError rather than treating it as empty.
    history_path = tmp_path / "history"
    history_path.write_text("hi\n")

    load_history(history_path)


def test_save_and_load_history_roundtrip(tmp_path):
    history_path = tmp_path / "history"
    readline.clear_history()
    readline.add_history("ls sandbox")
    save_history(history_path)

    readline.clear_history()
    load_history(history_path)

    assert readline.get_history_item(1) == "ls sandbox"


def test_main_persists_history(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr("cli.repl.SANDBOX_ROOT", tmp_path / "sandbox")
    monkeypatch.setattr("cli.repl.TRAJECTORIES_DIR", tmp_path / "trajectories")
    (tmp_path / "sandbox").mkdir()
    (tmp_path / "trajectories").mkdir()

    history_path = tmp_path / "history"
    monkeypatch.setattr("cli.repl.HISTORY_FILE", history_path)

    fake_agent = FakeAgent([[("messages", (FakeMessage("hello there"), {}))]])
    monkeypatch.setattr("cli.repl.create_agent", lambda *a, **k: fake_agent)
    monkeypatch.setattr("builtins.input", _drive_input(["hi", EOFError]))

    main(["--model", "anthropic:claude-opus-4-8"])

    assert history_path.exists()
    assert "hi" in history_path.read_text()


def test_main_enables_anthropic_prompt_caching(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr("cli.repl.SANDBOX_ROOT", tmp_path / "sandbox")
    monkeypatch.setattr("cli.repl.TRAJECTORIES_DIR", tmp_path / "trajectories")
    (tmp_path / "sandbox").mkdir()
    (tmp_path / "trajectories").mkdir()

    captured_kwargs = {}

    def fake_create_agent(model, **kwargs):
        captured_kwargs.update(kwargs)
        return FakeAgent([[("messages", (FakeMessage("hello there"), {}))]])

    monkeypatch.setattr("cli.repl.create_agent", fake_create_agent)
    monkeypatch.setattr("builtins.input", _drive_input(["hi", EOFError]))

    main(["--model", "anthropic:claude-opus-4-8"])

    middleware = captured_kwargs["middleware"]
    assert len(middleware) == 2
    assert isinstance(middleware[0], AnthropicPromptCachingMiddleware)


def test_main_skips_anthropic_prompt_caching_for_non_anthropic_model(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr("cli.repl.SANDBOX_ROOT", tmp_path / "sandbox")
    monkeypatch.setattr("cli.repl.TRAJECTORIES_DIR", tmp_path / "trajectories")
    (tmp_path / "sandbox").mkdir()
    (tmp_path / "trajectories").mkdir()

    captured_kwargs = {}

    def fake_create_agent(model, **kwargs):
        captured_kwargs.update(kwargs)
        return FakeAgent([[("messages", (FakeMessage("hello there"), {}))]])

    monkeypatch.setattr("cli.repl.create_agent", fake_create_agent)
    monkeypatch.setattr("builtins.input", _drive_input(["hi", EOFError]))

    main(["--model", "ollama:qwen3:8b"])

    middleware = captured_kwargs["middleware"]
    assert not any(isinstance(m, AnthropicPromptCachingMiddleware) for m in middleware)


def test_main_enables_summarization_middleware(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr("cli.repl.SANDBOX_ROOT", tmp_path / "sandbox")
    monkeypatch.setattr("cli.repl.TRAJECTORIES_DIR", tmp_path / "trajectories")
    (tmp_path / "sandbox").mkdir()
    (tmp_path / "trajectories").mkdir()

    captured_kwargs = {}

    def fake_create_agent(model, **kwargs):
        captured_kwargs.update(kwargs)
        return FakeAgent([[("messages", (FakeMessage("hello there"), {}))]])

    monkeypatch.setattr("cli.repl.create_agent", fake_create_agent)
    monkeypatch.setattr("builtins.input", _drive_input(["hi", EOFError]))

    main(["--model", "anthropic:claude-opus-4-8"])

    middleware = captured_kwargs["middleware"]
    summarization = [m for m in middleware if isinstance(m, SummarizationMiddleware)]
    assert len(summarization) == 1
    assert summarization[0].trigger == ("tokens", 800_000)
    assert summarization[0].keep == ("tokens", 150_000)
    assert summarization[0].trim_tokens_to_summarize == 150_000
    assert summarization[0].model.model == "claude-haiku-4-5"


def test_announcing_summarization_prints_notice_when_triggered(monkeypatch, capsys):
    middleware = AnnouncingSummarizationMiddleware(model=SUMMARIZATION_MODEL)
    sentinel = {"messages": ["whatever"]}
    monkeypatch.setattr(
        SummarizationMiddleware, "before_model", lambda self, state, runtime: sentinel
    )

    result = middleware.before_model({}, None)

    assert result is sentinel
    assert "summarization" in capsys.readouterr().out.lower()


def test_announcing_summarization_silent_when_not_triggered(monkeypatch, capsys):
    middleware = AnnouncingSummarizationMiddleware(model=SUMMARIZATION_MODEL)
    monkeypatch.setattr(
        SummarizationMiddleware, "before_model", lambda self, state, runtime: None
    )

    result = middleware.before_model({}, None)

    assert result is None
    assert capsys.readouterr().out == ""


def test_main_skips_summarization_for_model_without_profile(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr("cli.repl.SANDBOX_ROOT", tmp_path / "sandbox")
    monkeypatch.setattr("cli.repl.TRAJECTORIES_DIR", tmp_path / "trajectories")
    (tmp_path / "sandbox").mkdir()
    (tmp_path / "trajectories").mkdir()

    captured_kwargs = {}

    def fake_create_agent(model, **kwargs):
        captured_kwargs.update(kwargs)
        return FakeAgent([[("messages", (FakeMessage("hello there"), {}))]])

    monkeypatch.setattr("cli.repl.create_agent", fake_create_agent)
    monkeypatch.setattr("builtins.input", _drive_input(["hi", EOFError]))

    main(["--model", "ollama:qwen3:8b"])

    middleware = captured_kwargs["middleware"]
    summarization = [m for m in middleware if isinstance(m, SummarizationMiddleware)]
    assert summarization == []


def test_main_without_flag_uses_picker(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr("cli.repl.SANDBOX_ROOT", tmp_path / "sandbox")
    monkeypatch.setattr("cli.repl.TRAJECTORIES_DIR", tmp_path / "trajectories")
    (tmp_path / "sandbox").mkdir()
    (tmp_path / "trajectories").mkdir()

    captured_models = []

    def fake_create_agent(model, **kwargs):
        captured_models.append(model)
        return FakeAgent([[("messages", (FakeMessage("hello there"), {}))]])

    monkeypatch.setattr("cli.repl.create_agent", fake_create_agent)
    # First input() answers the model picker (empty -> default), second is the chat turn.
    monkeypatch.setattr("builtins.input", _drive_input(["", "hi", EOFError]))

    main([])

    default_model = load_model_config()["default"]
    assert captured_models == [default_model]
    assert "hello there" in capsys.readouterr().out
