"""Environment-based runtime settings.

API keys are NEVER stored here — only their environment variable names.
"""

import os
import subprocess
from pathlib import Path

from pydantic_settings import BaseSettings


def _resolve_config_dir() -> Path:
    """Try to find the configs directory.

    Uses ``LYINGLLM_CONFIG_DIR`` if set, otherwise tries ``./configs``.
    If that doesn't exist, walks up the filesystem from this file
    looking for ``configs/providers.yaml``.
    """
    env = os.getenv("LYINGLLM_CONFIG_DIR")
    if env:
        return Path(env).resolve()

    cwd = Path.cwd() / "configs"
    if cwd.exists():
        return cwd.resolve()

    # Walk up from this file (src/lyingllm/config/settings.py)
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "configs"
        if candidate.exists() and (candidate / "providers.yaml").exists():
            return candidate.resolve()

    # Also try git root
    try:
        root = (
            subprocess.check_output(["git", "rev-parse", "--show-toplevel"], text=True)
            .strip()
        )
        candidate = Path(root) / "configs"
        if candidate.exists():
            return candidate.resolve()
    except Exception:
        pass

    return cwd.resolve()


class Settings(BaseSettings):
    """Global runtime settings.

    Use ``settings = get_settings()`` to access.
    """

    app_name: str = "LyingLLM"
    config_dir: Path = _resolve_config_dir()
    max_output_tokens: int = 2000
    max_retries: int = 3
    default_timeout_seconds: int = 30

    model_config = {"env_prefix": "LYINGLLM_"}


# simple singleton — safe because Settings is immutable
_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
