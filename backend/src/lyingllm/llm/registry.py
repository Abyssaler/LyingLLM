"""Adapter registry.

Maps provider IDs to instantiated adapters.
"""

from __future__ import annotations

from lyingllm.llm.adapters import MockAdapter, ProviderAdapter


class AdapterRegistry:
    def __init__(self) -> None:
        self._adapters: dict[str, ProviderAdapter] = {
            "mock": MockAdapter(),
        }

    def get(self, provider_id: str) -> ProviderAdapter | None:
        return self._adapters.get(provider_id)

    def register(self, provider_id: str, adapter: ProviderAdapter) -> None:
        self._adapters[provider_id] = adapter


# Module-level singleton
_registry = AdapterRegistry()


def get_registry() -> AdapterRegistry:
    return _registry
