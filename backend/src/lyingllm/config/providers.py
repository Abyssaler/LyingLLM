"""Provider / model catalog.

Loaded from ``configs/providers.yaml``.  Exposes available adapters and
capabilities so the engine can dispatch requests correctly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from lyingllm.config.loader import load_providers_catalog


@dataclass(slots=True)
class ModelCapabilities:
    structured_output: bool = False
    json_mode: bool = False
    tool_calling: bool = False
    reasoning_summary: bool = False
    reasoning_content: bool = False
    encrypted_reasoning: bool = False
    reasoning_effort: bool = False
    max_context_tokens: int | None = None


@dataclass(slots=True)
class ModelDefaults:
    temperature: float | None = None
    top_p: float | None = None
    max_output_tokens: int = 2000
    reasoning_effort: str | None = None
    reasoning_capture: str = "auto"


@dataclass(slots=True)
class ModelCatalogItem:
    id: str
    display_name: str
    capabilities: ModelCapabilities
    defaults: ModelDefaults


@dataclass(slots=True)
class ProviderConfig:
    id: str
    display_name: str
    adapter: str
    base_url_env: str | None = None
    api_key_env: str | None = None
    models: list[ModelCatalogItem] = field(default_factory=list)

    @property
    def is_configured(self) -> bool:
        """True when at least the API key env var is present."""
        import os

        if self.api_key_env is None:
            return True  # provider that doesn't require a key (e.g. mock)
        return os.getenv(self.api_key_env, "") != ""


def _parse_capabilities(raw: dict[str, Any]) -> ModelCapabilities:
    return ModelCapabilities(
        structured_output=raw.get("structured_output", False),
        json_mode=raw.get("json_mode", False),
        tool_calling=raw.get("tool_calling", False),
        reasoning_summary=raw.get("reasoning_summary", False),
        reasoning_content=raw.get("reasoning_content", False),
        encrypted_reasoning=raw.get("encrypted_reasoning", False),
        reasoning_effort=raw.get("reasoning_effort", False),
        max_context_tokens=raw.get("max_context_tokens"),
    )


def _parse_defaults(raw: dict[str, Any]) -> ModelDefaults:
    return ModelDefaults(
        temperature=raw.get("temperature"),
        top_p=raw.get("top_p"),
        max_output_tokens=raw.get("max_output_tokens", 2000),
        reasoning_effort=raw.get("reasoning_effort"),
        reasoning_capture=raw.get("reasoning_capture", "auto"),
    )


def _parse_model(raw: dict[str, Any]) -> ModelCatalogItem:
    return ModelCatalogItem(
        id=raw["id"],
        display_name=raw.get("display_name", raw["id"]),
        capabilities=_parse_capabilities(raw.get("capabilities", {})),
        defaults=_parse_defaults(raw.get("defaults", {})),
    )


def _parse_provider(raw: dict[str, Any]) -> ProviderConfig:
    return ProviderConfig(
        id=raw["id"],
        display_name=raw.get("display_name", raw["id"]),
        adapter=raw["adapter"],
        base_url_env=raw.get("base_url_env"),
        api_key_env=raw.get("api_key_env"),
        models=[_parse_model(m) for m in raw.get("models", [])],
    )


def get_provider_catalog() -> list[ProviderConfig]:
    """Return parsed provider configurations from ``providers.yaml``.

    Safe to call during import — it reads YAML lazily but doesn't
    perform any network I/O.
    """
    data = load_providers_catalog()
    providers = data.get("providers", [])
    return [_parse_provider(p) for p in providers]


def get_provider_config(provider_id: str) -> ProviderConfig | None:
    for pc in get_provider_catalog():
        if pc.id == provider_id:
            return pc
    return None


def get_model_config(provider_id: str, model_id: str) -> ModelCatalogItem | None:
    pc = get_provider_config(provider_id)
    if pc is None:
        return None
    for m in pc.models:
        if m.id == model_id:
            return m
    return None
