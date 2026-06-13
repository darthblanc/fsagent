"""Stage 5 — Git: gated tools auto-commit the whole tree (git add -A),
message tagged with session + request ID; tier-3 files excluded by size
policy. Read-group tools (git=False) never reach this stage's commit.
"""

import subprocess
from pathlib import Path
from typing import Protocol

from core.errors import ToolError
from core.tiers import DEFAULT_SIZE_THRESHOLD
from core.tool_definition import ToolDefinition


class GitStage(Protocol):
    def commit(self, definition: ToolDefinition, request_id: int) -> None: ...


class NoGit:
    def commit(self, definition: ToolDefinition, request_id: int) -> None:
        return None


class GitCommit:
    def __init__(self, root, session_id: str, tier_threshold: int = DEFAULT_SIZE_THRESHOLD):
        self.root = Path(root)
        self.session_id = session_id
        self.tier_threshold = tier_threshold

    def commit(self, definition: ToolDefinition, request_id: int) -> None:
        self._ensure_repo()
        self._exclude_oversized()
        self._git("add", "-A")
        self._git(
            "commit", "--allow-empty", "-q", "-m",
            f"{definition.name} [session={self.session_id} request={request_id}]",
        )

    def _ensure_repo(self) -> None:
        if (self.root / ".git").is_dir():
            return
        self._git("init", "-q")
        self._git("config", "user.name", "fsagent")
        self._git("config", "user.email", "fsagent@sandbox.local")

    def _exclude_oversized(self) -> None:
        oversized = sorted(
            path.relative_to(self.root).as_posix()
            for path in self.root.rglob("*")
            if ".git" not in path.parts
            and path.is_file()
            and path.stat().st_size > self.tier_threshold
        )
        exclude = self.root / ".git" / "info" / "exclude"
        exclude.parent.mkdir(parents=True, exist_ok=True)
        exclude.write_text(
            "# fsagent: tier-3 files excluded by size policy\n"
            + "".join(f"/{path}\n" for path in oversized)
        )

    def _git(self, *args: str) -> str:
        result = subprocess.run(
            ["git", *args], cwd=self.root, capture_output=True, text=True
        )
        if result.returncode != 0:
            raise ToolError(f"git {args[0]} failed: {result.stderr.strip()}")
        return result.stdout
