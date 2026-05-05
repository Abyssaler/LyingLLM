from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional

from app.models.role import Faction, RoleConfig, SkillDefinition


@dataclass
class ActionResult:
    success: bool = True
    action_type: str = ""
    target_id: Optional[int] = None
    data: dict[str, Any] = field(default_factory=dict)
    message: str = ""


@dataclass
class GameContext:
    round: int = 0
    phase: str = ""
    alive_player_ids: list[int] = field(default_factory=list)
    wolf_kill_target: Optional[int] = None
    deaths_this_round: list[int] = field(default_factory=list)
    rules: dict[str, Any] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)


class BaseRole(ABC):
    def __init__(self, config: RoleConfig) -> None:
        self.name: str = config.name
        self.faction: Faction = config.faction
        self.night_priority: Optional[int] = config.night_priority
        self.description: str = config.description
        self.skills: list[SkillDefinition] = config.skills
        self.prompt_hint: str = config.prompt_hint

    @abstractmethod
    async def night_action(self, agent: Any, context: GameContext) -> ActionResult:
        ...

    async def day_action(self, agent: Any, context: GameContext) -> ActionResult:
        return ActionResult(success=False, action_type="none", message=f"{self.name} has no day action")

    async def on_death(self, agent: Any, context: GameContext) -> Optional[ActionResult]:
        return None

    def get_night_prompt(self, context: GameContext) -> str:
        return f"现在是夜晚，你是{self.name}。{self.prompt_hint}"

    def get_day_prompt(self, context: GameContext) -> str:
        return f"现在是白天，你是{self.name}。{self.prompt_hint}"

    def has_night_action(self) -> bool:
        return any(s.phase.value == "night" for s in self.skills)

    def has_on_death_skill(self) -> bool:
        return any(s.phase.value == "on_death" or s.trigger == "on_death" for s in self.skills)

    def get_skill_by_name(self, skill_name: str) -> Optional[SkillDefinition]:
        for s in self.skills:
            if s.name == skill_name:
                return s
        return None

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name!r}, faction={self.faction.value!r})"