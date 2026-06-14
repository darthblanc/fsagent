import os
import re
import readline

import pytest
from langgraph.types import Interrupt

from cli.models import load_model_config
from cli.repl import (
    build_pipeline,
    cli_decision,
    load_env,
    load_history,
    main,
    make_session_id,
    save_history,
)


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


class FakeMessage:
    def __init__(self, text):
        self.text = text


class FakeAgent:
    def __init__(self, responses):
        self._responses = list(responses)
        self.configs = []

    def invoke(self, _input, config=None):
        self.configs.append(config)
        return self._responses.pop(0)


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

    fake_agent = FakeAgent([{"messages": [FakeMessage("hello there")]}])
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
        {"messages": [FakeMessage("")], "__interrupt__": (Interrupt(value=interrupt_payload),)},
        {"messages": [FakeMessage("done")]},
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

    fake_agent = FakeAgent([{"messages": [FakeMessage("hello there")]}])
    monkeypatch.setattr("cli.repl.create_agent", lambda *a, **k: fake_agent)
    monkeypatch.setattr("builtins.input", _drive_input(["hi", EOFError]))

    main(["--model", "anthropic:claude-opus-4-8"])

    config = fake_agent.configs[0]
    assert config["configurable"]["thread_id"] == "s-test"
    assert config["tags"] == ["anthropic:claude-opus-4-8"]
    assert config["metadata"] == {"session_id": "s-test", "model": "anthropic:claude-opus-4-8"}


def test_main_uses_model_flag(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr("cli.repl.SANDBOX_ROOT", tmp_path / "sandbox")
    monkeypatch.setattr("cli.repl.TRAJECTORIES_DIR", tmp_path / "trajectories")
    (tmp_path / "sandbox").mkdir()
    (tmp_path / "trajectories").mkdir()

    captured_models = []

    def fake_create_agent(model, **kwargs):
        captured_models.append(model)
        return FakeAgent([{"messages": [FakeMessage("hello there")]}])

    monkeypatch.setattr("cli.repl.create_agent", fake_create_agent)
    monkeypatch.setattr("builtins.input", _drive_input(["hi", EOFError]))

    main(["--model", "ollama:qwen3:8b"])

    assert captured_models == ["ollama:qwen3:8b"]
    assert "model: ollama:qwen3:8b" in capsys.readouterr().out


def test_load_history_missing_file_does_not_raise(tmp_path):
    load_history(tmp_path / "no-such-history")


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

    fake_agent = FakeAgent([{"messages": [FakeMessage("hello there")]}])
    monkeypatch.setattr("cli.repl.create_agent", lambda *a, **k: fake_agent)
    monkeypatch.setattr("builtins.input", _drive_input(["hi", EOFError]))

    main(["--model", "anthropic:claude-opus-4-8"])

    assert history_path.exists()
    assert "hi" in history_path.read_text()


def test_main_without_flag_uses_picker(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr("cli.repl.SANDBOX_ROOT", tmp_path / "sandbox")
    monkeypatch.setattr("cli.repl.TRAJECTORIES_DIR", tmp_path / "trajectories")
    (tmp_path / "sandbox").mkdir()
    (tmp_path / "trajectories").mkdir()

    captured_models = []

    def fake_create_agent(model, **kwargs):
        captured_models.append(model)
        return FakeAgent([{"messages": [FakeMessage("hello there")]}])

    monkeypatch.setattr("cli.repl.create_agent", fake_create_agent)
    # First input() answers the model picker (empty -> default), second is the chat turn.
    monkeypatch.setattr("builtins.input", _drive_input(["", "hi", EOFError]))

    main([])

    default_model = load_model_config()["default"]
    assert captured_models == [default_model]
    assert "hello there" in capsys.readouterr().out
