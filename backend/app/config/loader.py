from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


class YAMLLoader:
    def __init__(self, configs_dir: Path | str | None = None) -> None:
        if configs_dir is None:
            configs_dir = Path(__file__).resolve().parent.parent.parent / "configs"
        self.configs_dir = Path(configs_dir)

    def load(self, relative_path: str) -> dict[str, Any]:
        file_path = self.configs_dir / relative_path
        if not file_path.exists():
            raise FileNotFoundError(f"Config file not found: {file_path}")
        with open(file_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data if data is not None else {}

    def load_roles(self, name: str = "classic") -> dict[str, Any]:
        return self.load(f"roles/{name}.yaml")

    def load_rules(self, name: str = "classic") -> dict[str, Any]:
        return self.load(f"rules/{name}.yaml")

    def load_models(self, name: str = "providers") -> dict[str, Any]:
        return self.load(f"models/{name}.yaml")

    def list_configs(self, category: str) -> list[str]:
        category_dir = self.configs_dir / category
        if not category_dir.exists():
            return []
        return [f.stem for f in sorted(category_dir.glob("*.yaml"))]