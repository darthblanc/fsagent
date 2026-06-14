"""Live end-to-end smoke test: real Pipeline, real agent, one turn.

Not collected by pytest (testpaths = ["tests"]). Requires ANTHROPIC_API_KEY.

    uv run python live_agent_smoke.py
"""

import tempfile
from pathlib import Path

from langchain.agents import create_agent
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from agent import load_system_prompt
from agent.tools import Approvals, build_tools
from cli.repl import MODEL, build_pipeline, make_session_id


def auto_decision(payload: dict) -> str:
    print(f"[auto-approving] {payload['tool']} {payload['args']}: {payload['message']}")
    return "always"


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        sandbox_root = root / "sandbox"
        trajectories_dir = root / "trajectories"
        sandbox_root.mkdir()
        trajectories_dir.mkdir()
        (sandbox_root / "hello.txt").write_text("hello world\n")

        session_id = make_session_id()
        pipeline = build_pipeline(
            session_id, sandbox_root=sandbox_root, trajectories_dir=trajectories_dir
        )
        approvals = Approvals()
        agent = create_agent(
            MODEL,
            tools=build_tools(pipeline, approvals),
            system_prompt=load_system_prompt(),
            checkpointer=InMemorySaver(),
        )
        config = {"configurable": {"thread_id": session_id}}

        result = agent.invoke(
            {"messages": [{"role": "user", "content": "What's in hello.txt?"}]},
            config=config,
        )
        while "__interrupt__" in result:
            decision = auto_decision(result["__interrupt__"][0].value)
            result = agent.invoke(Command(resume=decision), config=config)

        print(result["messages"][-1].text)


if __name__ == "__main__":
    main()
