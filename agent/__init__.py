from pathlib import Path

_SYSTEM_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "system.md"


def load_system_prompt() -> str:
    return _SYSTEM_PROMPT_PATH.read_text()


__all__ = ["load_system_prompt"]
