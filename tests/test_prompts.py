from agent import load_system_prompt


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
