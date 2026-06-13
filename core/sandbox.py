"""Stage 1 — Sandbox: every path must resolve inside the sandbox root."""

from dataclasses import dataclass
from pathlib import Path

from core.errors import SandboxViolation


@dataclass(frozen=True)
class Sandbox:
    root: Path

    def resolve(self, value) -> Path:
        candidate = Path(value)
        if not candidate.is_absolute():
            candidate = Path(self.root) / candidate
        resolved = candidate.resolve()
        root = Path(self.root).resolve()
        if not resolved.is_relative_to(root):
            raise SandboxViolation(
                f"'{value}' resolves outside the sandbox — the world ends at {root}"
            )
        return resolved
