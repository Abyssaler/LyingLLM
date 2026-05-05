from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class Faction(str, Enum):
    WOLF = "wolf"
    VILLAGE = "village"
    OTHER = "other"


class SkillPhase(str, Enum):
    NIGHT = "night"
    ON_DEATH = "on_death"


class SkillTargetType(str, Enum):
    SINGLE_PLAYER = "single_player"
    WOLF_TARGET = "wolf_target"
    SELF = "self"
    NONE = "none"


class SkillDefinition(BaseModel):
    name: str
    phase: SkillPhase
    description: str = ""
    target_type: SkillTargetType = SkillTargetType.SINGLE_PLAYER
    uses: Optional[int] = None
    result_type: Optional[str] = None
    self_save_allowed: bool = True
    cannot_guard_same_twice: bool = False
    can_empty_guard: bool = False
    can_shoot_on_witch_kill: bool = True
    faction_discuss: bool = False
    trigger: Optional[str] = None


class RoleConfig(BaseModel):
    name: str
    faction: Faction
    night_priority: Optional[int] = None
    description: str = ""
    skills: list[SkillDefinition] = Field(default_factory=list)
    prompt_hint: str = ""


class RolesFile(BaseModel):
    name: str
    version: str = "1.0"
    description: str = ""
    roles: dict[str, RoleConfig]