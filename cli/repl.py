"""Minimal REPL: wires Pipeline + agent tools to a LangChain agent loop."""

import argparse
import os
import readline
import secrets
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.agents.middleware import SummarizationMiddleware
from langchain.chat_models import init_chat_model
from langchain_anthropic.middleware import AnthropicPromptCachingMiddleware
from langchain_core.callbacks import BaseCallbackHandler
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from agent import load_subagent_system_prompt, load_system_prompt
from agent.subagent import build_subagent_tool
from agent.tools import Approvals, build_tools
from cli.models import load_model_config, select_model
from core.pipeline import Pipeline
from core.policy import YamlPolicy
from core.sandbox import Sandbox
from core.trajectory import Trajectory
from tools import ALL_TOOLS

REPO_ROOT = Path(__file__).resolve().parent.parent
SANDBOX_ROOT = REPO_ROOT / "sandbox"
TRAJECTORIES_DIR = REPO_ROOT / "trajectories"
POLICY_PATH = REPO_ROOT / "configs" / "policy.yaml"
ENV_FILE = REPO_ROOT / ".env"
HISTORY_FILE = Path.home() / ".fsagent_history"
SUMMARIZATION_MODEL = "anthropic:claude-haiku-4-5"


def load_env(path: Path = ENV_FILE) -> None:
    load_dotenv(path)
    if "LANGSMITH_PROJECT" not in os.environ and "LANGCHAIN_PROJECT" not in os.environ:
        os.environ["LANGSMITH_PROJECT"] = "fsagent"


def load_history(path: Path = HISTORY_FILE) -> None:
    try:
        readline.read_history_file(path)
    except OSError:
        pass  # missing, unreadable, or a format libedit's history parser rejects


def save_history(path: Path = HISTORY_FILE) -> None:
    readline.write_history_file(path)


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="fsagent")
    parser.add_argument(
        "--model",
        help=(
            "Provider-prefixed model, e.g. anthropic:claude-opus-4-8, "
            "openai:gpt-5.5, ollama:qwen3:8b. Skips the interactive picker."
        ),
    )
    return parser.parse_args(argv)


def make_session_id() -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"s-{timestamp}-{secrets.token_hex(4)}"


def build_pipeline(session_id, sandbox_root=None, trajectories_dir=None) -> Pipeline:
    sandbox_root = sandbox_root if sandbox_root is not None else SANDBOX_ROOT
    trajectories_dir = trajectories_dir if trajectories_dir is not None else TRAJECTORIES_DIR
    return Pipeline(
        sandbox=Sandbox(sandbox_root),
        policy=YamlPolicy.from_file(POLICY_PATH, sandbox_root),
        trajectory=Trajectory(trajectories_dir / f"{session_id}.jsonl", session_id=session_id),
        tools=ALL_TOOLS,
    )


def cli_decision(payload: dict) -> str:
    print(f"\napproval needed — {payload['tool']} {payload['args']}")
    print(payload["message"])
    answer = input("Allow? [y]es / [a]lways / [N]o: ").strip().lower()
    if answer in ("y", "yes"):
        return "yes"
    if answer in ("a", "always"):
        return "always"
    return "no"


def stream_response(agent, input_, config) -> dict | None:
    """Streams one turn, printing assistant text as it arrives.

    Returns the interrupt payload dict if the run paused for approval, else None.
    """
    interrupt_payload = None
    printed = False
    for mode, data in agent.stream(input_, config=config, stream_mode=["messages", "values"]):
        if mode == "messages":
            message, _metadata = data
            if getattr(message, "type", None) == "tool":
                continue  # ToolActivityCallback already printed this result
            if message.text:
                print(message.text, end="", flush=True)
                printed = True
        elif mode == "values" and "__interrupt__" in data:
            interrupt_payload = data["__interrupt__"][0].value
    if printed:
        print()
    return interrupt_payload


_LABEL_KEYS = ("path", "src", "pattern", "task")


class ToolActivityCallback(BaseCallbackHandler):
    """Prints a header when any tool starts, and its result when it ends."""

    def __init__(self):
        self._runs: dict = {}

    def on_tool_start(self, serialized, input_str, *, run_id, inputs=None, **kwargs):
        name = serialized.get("name")
        inputs = inputs or {}
        label = next((inputs[key] for key in _LABEL_KEYS if key in inputs), "")
        print(f"[{name}] {label}")
        self._runs[run_id] = name

    def on_tool_end(self, output, *, run_id, **kwargs):
        self._runs.pop(run_id, None)
        print(getattr(output, "content", output))

    def on_tool_error(self, error, *, run_id, **kwargs):
        self._runs.pop(run_id, None)


class AnnouncingSummarizationMiddleware(SummarizationMiddleware):
    """Like SummarizationMiddleware, but prints a notice when it actually fires.

    LangGraph wires middleware before_model hooks with trace=False, so
    callback handlers (e.g. ToolActivityCallback) never see this happen —
    overriding before_model is the only way to observe it.
    """

    def before_model(self, state, runtime):
        result = super().before_model(state, runtime)
        if result is not None:
            print(
                "\n[summarization] condensed earlier conversation history "
                "to stay under the context limit\n"
            )
        return result


def main(argv=None) -> None:
    load_env()
    args = parse_args(argv)
    model = select_model(load_model_config(), flag=args.model, input_func=input)
    print(f"model: {model}")

    session_id = make_session_id()
    pipeline = build_pipeline(session_id)
    approvals = Approvals()

    resolved_model = init_chat_model(model)
    middleware = []
    if model.split(":", 1)[0] == "anthropic":
        middleware.append(AnthropicPromptCachingMiddleware())
    profile = getattr(resolved_model, "profile", None)
    max_input_tokens = profile.get("max_input_tokens") if isinstance(profile, dict) else None
    if isinstance(max_input_tokens, int):
        middleware.append(
            AnnouncingSummarizationMiddleware(
                model=SUMMARIZATION_MODEL,
                trigger=("tokens", int(max_input_tokens * 0.8)),
                keep=("tokens", int(max_input_tokens * 0.15)),
                trim_tokens_to_summarize=150_000,
            )
        )
    else:
        print(f"note: no context-window profile for {model}; skipping auto-summarization")

    subagent_tool = build_subagent_tool(resolved_model, pipeline, load_subagent_system_prompt())

    agent = create_agent(
        model,
        tools=build_tools(pipeline, approvals) + [subagent_tool],
        system_prompt=load_system_prompt(),
        checkpointer=InMemorySaver(),
        middleware=middleware,
    )
    config = {
        "configurable": {"thread_id": session_id},
        "tags": [model],
        "metadata": {"session_id": session_id, "model": model},
        "callbacks": [ToolActivityCallback()],
    }

    load_history(HISTORY_FILE)
    while True:
        try:
            user_input = input("> ")
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not user_input.strip():
            continue
        readline.add_history(user_input)

        interrupt_payload = stream_response(
            agent, {"messages": [{"role": "user", "content": user_input}]}, config
        )
        while interrupt_payload is not None:
            decision = cli_decision(interrupt_payload)
            interrupt_payload = stream_response(agent, Command(resume=decision), config)
    save_history(HISTORY_FILE)


if __name__ == "__main__":
    main()
