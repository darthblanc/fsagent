"""Minimal REPL: wires Pipeline + agent tools to a LangChain agent loop."""

import argparse
import readline
import secrets
from datetime import datetime, timezone
from pathlib import Path

from langchain.agents import create_agent
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from agent import load_system_prompt
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
HISTORY_FILE = Path.home() / ".fsagent_history"


def load_history(path: Path = HISTORY_FILE) -> None:
    try:
        readline.read_history_file(path)
    except FileNotFoundError:
        pass


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


def main(argv=None) -> None:
    args = parse_args(argv)
    model = select_model(load_model_config(), flag=args.model, input_func=input)
    print(f"model: {model}")

    session_id = make_session_id()
    pipeline = build_pipeline(session_id)
    approvals = Approvals()
    agent = create_agent(
        model,
        tools=build_tools(pipeline, approvals),
        system_prompt=load_system_prompt(),
        checkpointer=InMemorySaver(),
    )
    config = {"configurable": {"thread_id": session_id}}

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

        result = agent.invoke(
            {"messages": [{"role": "user", "content": user_input}]}, config=config
        )
        while "__interrupt__" in result:
            decision = cli_decision(result["__interrupt__"][0].value)
            result = agent.invoke(Command(resume=decision), config=config)

        print(result["messages"][-1].text)
    save_history(HISTORY_FILE)


if __name__ == "__main__":
    main()
