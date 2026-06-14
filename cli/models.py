"""Model selection: config-driven defaults, CLI flag, interactive picker."""

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
MODELS_CONFIG_PATH = REPO_ROOT / "configs" / "models.yaml"


def load_model_config(path=None) -> dict:
    path = path if path is not None else MODELS_CONFIG_PATH
    return yaml.safe_load(Path(path).read_text())


def prompt_model_choice(config: dict, input_func=input) -> str:
    models = config["models"]
    default = config["default"]
    print("Available models:")
    for index, model in enumerate(models, start=1):
        marker = " (default)" if model == default else ""
        print(f"  {index}. {model}{marker}")
    raw = input_func(f"Select a model [1-{len(models)}] or press enter for default: ").strip()
    if raw.isdigit():
        index = int(raw)
        if 1 <= index <= len(models):
            return models[index - 1]
    return default


def select_model(config: dict, flag: str | None = None, input_func=input) -> str:
    if flag:
        return flag
    return prompt_model_choice(config, input_func=input_func)
