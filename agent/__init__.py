from pathlib import Path

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
_SYSTEM_PROMPT_PATH = _PROMPTS_DIR / "system.md"
_SUBAGENT_SYSTEM_PROMPT_PATH = _PROMPTS_DIR / "subagent_system.md"


def load_system_prompt() -> str:
    return _SYSTEM_PROMPT_PATH.read_text()


def load_subagent_system_prompt() -> str:
    return _SUBAGENT_SYSTEM_PROMPT_PATH.read_text()


__all__ = ["load_subagent_system_prompt", "load_system_prompt"]
