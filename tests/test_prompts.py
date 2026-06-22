from agent import load_subagent_system_prompt, load_system_prompt


def test_system_prompt_non_empty():
    prompt = load_system_prompt()
    assert prompt.strip()


def test_system_prompt_never_mentions_trash():
    prompt = load_system_prompt()
    assert "trash" not in prompt.lower()


def test_system_prompt_explains_retry_and_approval():
    prompt = load_system_prompt()
    lower = prompt.lower()
    assert "retry" in lower or "re-read" in lower
    assert "approv" in lower


def test_system_prompt_explains_scratchpad():
    prompt = load_system_prompt()
    lower = prompt.lower()
    assert "scratchpad" in lower
    assert ".fsagent" in lower


def test_subagent_system_prompt_non_empty():
    prompt = load_subagent_system_prompt()
    assert prompt.strip()


def test_subagent_system_prompt_forbids_mutation():
    lower = load_subagent_system_prompt().lower()
    for mutating_tool in ("write", "edit", "append", "create_dir", "move", "copy", "delete"):
        assert mutating_tool in lower


def test_subagent_system_prompt_explains_synthesis():
    lower = load_subagent_system_prompt().lower()
    assert "summary" in lower or "synthesis" in lower or "summarize" in lower
