from __future__ import annotations

from typing import Any, Optional

from app.config.loader import YAMLLoader


class RuleConfig:
    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data

    @property
    def name(self) -> str:
        return self._data.get("name", "")

    @property
    def version(self) -> str:
        return self._data.get("version", "1.0")

    @property
    def phases(self) -> dict[str, Any]:
        return self._data.get("phases", {})

    @property
    def night_order(self) -> list[str]:
        return self.phases.get("night_order", ["guard", "werewolf", "witch", "seer"])

    @property
    def day_order(self) -> list[str]:
        return self.phases.get("day_order", ["announce", "discuss", "vote", "execute"])

    @property
    def enable_sheriff(self) -> bool:
        return self.phases.get("enable_sheriff", True)

    @property
    def enable_last_words(self) -> bool:
        return self.phases.get("enable_last_words", True)

    @property
    def enable_wolf_discuss(self) -> bool:
        return self.phases.get("enable_wolf_discuss", True)

    @property
    def day_speech_order(self) -> str:
        return self.phases.get("day_speech_order", "sheriff_choose_or_random_clockwise")

    @property
    def voting(self) -> dict[str, Any]:
        return self._data.get("voting", {})

    @property
    def vote_type(self) -> str:
        return self.voting.get("type", "majority")

    @property
    def tie_handling(self) -> str:
        return self.voting.get("tie_handling", "revote")

    @property
    def max_revote_rounds(self) -> int:
        return self.voting.get("max_revote_rounds", 2)

    @property
    def final_tie_resolution(self) -> str:
        return self.voting.get("final_tie_resolution", "no_elimination")

    @property
    def allow_abstain(self) -> bool:
        return self.voting.get("allow_abstain", True)

    @property
    def sheriff_vote_weight(self) -> float:
        return self.voting.get("sheriff_vote_weight", 1.5)

    @property
    def win_conditions(self) -> dict[str, str]:
        return self._data.get("win_conditions", {})

    @property
    def roles(self) -> dict[str, dict[str, int]]:
        return self._data.get("roles", {})

    @property
    def special_rules(self) -> dict[str, Any]:
        return self._data.get("special_rules", {})

    @property
    def logs(self) -> dict[str, Any]:
        return self._data.get("logs", {})

    @property
    def memory_compression(self) -> dict[str, Any]:
        return self._data.get("memory_compression", {})

    def get_special_rule(self, key: str, default: Any = None) -> Any:
        return self.special_rules.get(key, default)

    @property
    def witch_can_self_save(self) -> bool:
        return self.get_special_rule("witch_can_self_save", False)

    @property
    def hunter_can_shoot_on_witch_kill(self) -> bool:
        return self.get_special_rule("hunter_can_shoot_on_witch_kill", True)

    @property
    def guard_cannot_guard_same_twice(self) -> bool:
        return self.get_special_rule("guard_cannot_guard_same_twice", True)

    @property
    def guard_blocks_wolf_kill(self) -> bool:
        return self.get_special_rule("guard_blocks_wolf_kill", True)

    @property
    def witch_save_blocks_wolf_kill(self) -> bool:
        return self.get_special_rule("witch_save_blocks_wolf_kill", True)

    @property
    def guard_witch_same_target_dies(self) -> bool:
        return self.get_special_rule("guard_witch_same_target_dies", True)

    @property
    def merge_death_causes(self) -> bool:
        return self.get_special_rule("merge_death_causes", True)

    @property
    def first_night_has_last_words(self) -> bool:
        return self.get_special_rule("first_night_has_last_words", True)

    @property
    def mvp_include_dead_players(self) -> bool:
        return self.get_special_rule("mvp_include_dead_players", True)

    @property
    def sheriff_can_transfer(self) -> bool:
        return self.get_special_rule("sheriff_can_transfer", True)

    def get_role_range(self, role_key: str) -> tuple[int, int]:
        role_range = self.roles.get(role_key, {})
        return (role_range.get("min", 0), role_range.get("max", 99))

    def validate_player_count(self, count: int) -> bool:
        total_min = sum(r.get("min", 0) for r in self.roles.values())
        if count < total_min:
            return False
        for role_key, role_range in self.roles.items():
            min_val, max_val = role_range.get("min", 0), role_range.get("max", 99)
            if min_val > 0 and min_val > count:
                return False
        return True

    def to_dict(self) -> dict[str, Any]:
        return dict(self._data)

    def __repr__(self) -> str:
        return f"RuleConfig(name={self.name!r}, version={self.version!r})"


class RuleManager:
    def __init__(self, loader: Optional[YAMLLoader] = None) -> None:
        self._loader = loader or YAMLLoader()
        self._configs: dict[str, RuleConfig] = {}

    def load(self, name: str = "classic") -> RuleConfig:
        if name not in self._configs:
            data = self._loader.load_rules(name)
            self._configs[name] = RuleConfig(data)
        return self._configs[name]

    def get(self, name: str = "classic") -> RuleConfig:
        if name not in self._configs:
            return self.load(name)
        return self._configs[name]

    def list_available(self) -> list[str]:
        return self._loader.list_configs("rules")

    def reload(self, name: str = "classic") -> RuleConfig:
        data = self._loader.load_rules(name)
        config = RuleConfig(data)
        self._configs[name] = config
        return config