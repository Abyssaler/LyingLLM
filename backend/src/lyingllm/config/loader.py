"""YAML configuration loader.

Reads ``configs/providers.yaml`` and ``configs/runtime.yaml`` from
the configured config directory (default ``./configs``).
"""

from pathlib import Path

import yaml

from lyingllm.config.settings import get_settings


def _config_path(filename: str) -> Path:
    return get_settings().config_dir / filename


def load_yaml(filename: str) -> dict:
    path = _config_path(filename)
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_providers_catalog() -> dict:
    return load_yaml("providers.yaml")


def load_runtime_config() -> dict:
    return load_yaml("runtime.yaml")
