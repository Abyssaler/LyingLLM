from __future__ import annotations

import os
from pathlib import Path
from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CONFIGS_DIR = PROJECT_ROOT / "configs"
LOGS_DIR = PROJECT_ROOT / "logs"


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        env_prefix="APP_",
        extra="ignore",
    )

    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False
    log_dir: Path = LOGS_DIR
    configs_dir: Path = CONFIGS_DIR


class OpenAISettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        env_prefix="OPENAI_",
        extra="ignore",
    )

    api_key: str = ""
    base_url: str = "https://api.openai.com/v1"
    default_model: str = "gpt-4o"


class AnthropicSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        env_prefix="ANTHROPIC_",
        extra="ignore",
    )

    api_key: str = ""
    base_url: str = "https://api.anthropic.com"
    default_model: str = "claude-3-5-sonnet-20241022"


class CustomProviderSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    api_key: str = ""
    base_url: str = ""
    model: str = ""


class Settings:
    def __init__(self) -> None:
        self.app = AppSettings()
        self.openai = OpenAISettings()
        self.anthropic = AnthropicSettings()
        self.custom_providers: dict[str, CustomProviderSettings] = {}
        self._load_custom_providers()

    def _load_custom_providers(self) -> None:
        idx = 1
        while True:
            prefix = f"CUSTOM_PROVIDER_{idx}_"
            api_key = os.environ.get(f"{prefix}API_KEY", "")
            base_url = os.environ.get(f"{prefix}BASE_URL", "")
            model = os.environ.get(f"{prefix}MODEL", "")
            if not base_url and not api_key:
                break
            name = os.environ.get(f"{prefix}NAME", f"custom_{idx}")
            self.custom_providers[name] = CustomProviderSettings(
                api_key=api_key,
                base_url=base_url,
                model=model,
            )
            idx += 1


@lru_cache
def get_settings() -> Settings:
    return Settings()
