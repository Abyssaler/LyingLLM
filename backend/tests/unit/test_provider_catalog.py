"""Provider catalog loading tests."""

import os

from lyingllm.config.providers import get_provider_catalog, get_provider_config, get_model_config


def test_catalog_loaded():
    catalog = get_provider_catalog()
    ids = {p.id for p in catalog}
    assert "mock" in ids
    assert "openai" in ids


def test_mock_provider_is_configured():
    cfg = get_provider_config("mock")
    assert cfg is not None
    assert cfg.is_configured is True


def test_openai_provider_configured_when_key_set(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    cfg = get_provider_config("openai")
    assert cfg is not None
    assert cfg.is_configured is True


def test_openai_provider_not_configured_when_key_missing(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    cfg = get_provider_config("openai")
    assert cfg is not None
    assert cfg.is_configured is False


def test_model_config_lookup():
    m = get_model_config("mock", "mock-default")
    assert m is not None
    assert m.capabilities.structured_output is True


def test_unknown_provider_returns_none():
    assert get_provider_config("unknown") is None
