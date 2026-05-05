from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from app.models.role import Faction
from app.models.player import LLMConfig, PlayerStatus
from app.memory.game_memory import GameMemory
from app.roles.base import BaseRole


class PersonalityTrait(str, Enum):
    AGGRESSIVE = "aggressive"
    CAUTIOUS = "cautious"
    ANALYTICAL = "analytical"
    EMOTIONAL = "emotional"
    DECEPTIVE = "deceptive"
    HONEST = "honest"
    LEADER = "leader"
    FOLLOWER = "follower"
    STRATEGIC = "strategic"
    INTUITIVE = "intuitive"


@dataclass
class Personality:
    name: str = ""
    description: str = ""
    traits: list[PersonalityTrait] = field(default_factory=list)
    speaking_style: str = ""
    decision_style: str = ""

    def to_prompt_text(self) -> str:
        parts: list[str] = []
        if self.name:
            parts.append(f"你的性格名称：{self.name}")
        if self.description:
            parts.append(f"性格描述：{self.description}")
        if self.traits:
            trait_names = [t.value for t in self.traits]
            parts.append(f"性格特质：{'、'.join(trait_names)}")
        if self.speaking_style:
            parts.append(f"说话风格：{self.speaking_style}")
        if self.decision_style:
            parts.append(f"决策风格：{self.decision_style}")
        return "\n".join(parts) if parts else "你是一位普通的狼人杀玩家。"