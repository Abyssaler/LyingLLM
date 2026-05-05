from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from app.llm.message import ConversationManager
from app.memory.game_memory import GameMemory, MemoryVisibility
from app.agents.personality import Personality
from app.models.player import LLMConfig
from app.roles.base import BaseRole


@dataclass
class Agent:
    player_id: int
    name: str = ""
    role: Optional[BaseRole] = None
    faction: Optional[Faction] = None
    is_alive: bool = True
    is_sheriff: bool = False
    thinking_mode: bool = True
    llm_config: Optional[LLMConfig] = None
    personality: Personality = field(default_factory=Personality)
    memory: GameMemory = field(default_factory=GameMemory)
    conversation: ConversationManager = field(default_factory=ConversationManager)

    @property
    def role_name(self) -> str:
        return self.role.name if self.role else "未分配"

    @property
    def is_wolf(self) -> bool:
        return self.faction == Faction.WOLF

    def add_public_memory(self, phase: str, event_type: str, content: str, **metadata: Any) -> None:
        self.memory.add_public(phase=phase, event_type=event_type, content=content, **metadata)

    def add_private_memory(self, phase: str, event_type: str, content: str, **metadata: Any) -> None:
        self.memory.add_private(phase=phase, event_type=event_type, content=content, **metadata)

    def add_faction_memory(self, phase: str, event_type: str, content: str, **metadata: Any) -> None:
        self.memory.add_faction(phase=phase, event_type=event_type, content=content, **metadata)

    def get_visible_memory_text(self, max_rounds: Optional[int] = None) -> str:
        include_faction = self.is_wolf
        return self.memory.get_context_for_agent(include_faction=include_faction, max_rounds=max_rounds)

    def build_system_prompt(self, rules_text: str, phase_context: str) -> str:
        from app.agents.prompts import PromptBuilder
        builder = PromptBuilder(rules_text=rules_text)
        return builder.build(
            role=self.role,
            personality=self.personality,
            memory_text=self.get_visible_memory_text(),
            phase_context=phase_context,
            is_alive=self.is_alive,
            is_sheriff=self.is_sheriff,
            thinking_mode=self.thinking_mode,
            player_id=self.player_id,
            player_name=self.name,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "player_id": self.player_id,
            "name": self.name,
            "role": self.role_name,
            "faction": self.faction.value if self.faction else None,
            "is_alive": self.is_alive,
            "is_sheriff": self.is_sheriff,
            "thinking_mode": self.thinking_mode,
            "personality": {
                "name": self.personality.name,
                "description": self.personality.description,
                "traits": [t.value for t in self.personality.traits],
            },
        }


from app.models.role import Faction