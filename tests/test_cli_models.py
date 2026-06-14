from cli.models import load_model_config, prompt_model_choice, select_model

SAMPLE_CONFIG = {
    "default": "anthropic:claude-opus-4-8",
    "models": [
        "anthropic:claude-opus-4-8",
        "anthropic:claude-sonnet-4-6",
        "ollama:qwen3:8b",
    ],
}


def test_load_model_config_default_path():
    config = load_model_config()
    assert "default" in config
    assert config["default"] in config["models"]
    assert len(config["models"]) >= 1


def test_load_model_config_custom_path(tmp_path):
    path = tmp_path / "models.yaml"
    path.write_text("default: ollama:qwen3:8b\nmodels:\n  - ollama:qwen3:8b\n")

    config = load_model_config(path)

    assert config == {"default": "ollama:qwen3:8b", "models": ["ollama:qwen3:8b"]}


def test_prompt_model_choice_empty_input_returns_default():
    assert prompt_model_choice(SAMPLE_CONFIG, input_func=lambda prompt="": "") == (
        "anthropic:claude-opus-4-8"
    )


def test_prompt_model_choice_numeric_input_selects_by_index():
    assert prompt_model_choice(SAMPLE_CONFIG, input_func=lambda prompt="": "3") == (
        "ollama:qwen3:8b"
    )


def test_prompt_model_choice_invalid_input_falls_back_to_default():
    assert prompt_model_choice(SAMPLE_CONFIG, input_func=lambda prompt="": "nope") == (
        "anthropic:claude-opus-4-8"
    )
    assert prompt_model_choice(SAMPLE_CONFIG, input_func=lambda prompt="": "99") == (
        "anthropic:claude-opus-4-8"
    )


def test_select_model_flag_skips_prompt():
    def boom(prompt=""):
        raise AssertionError("should not prompt when --model is given")

    assert select_model(SAMPLE_CONFIG, flag="openai:gpt-5.5", input_func=boom) == (
        "openai:gpt-5.5"
    )


def test_select_model_without_flag_prompts():
    assert select_model(SAMPLE_CONFIG, flag=None, input_func=lambda prompt="": "2") == (
        "anthropic:claude-sonnet-4-6"
    )
