from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from app.models.role import Faction


class PlayerStatus(str, Enum):
    ALIVE = "alive"
    DEAD = "dead"


class LLMConfig(BaseModel):
    provider: str
    model_name: str = ""
    base_url: str = ""
    api_key: str = ""


class Personality(BaseModel):
    name: str = ""
    description: str = ""
    traits: list[str] = Field(default_factory=list)


class PlayerMemory(BaseModel):
    public: list[dict] = Field(default_factory=list)
    private: list[dict] = Field(default_factory=list)
    faction: list[dict] = Field(default_factory=list)


class Player(BaseModel):
    player_id: int
    name: str = ""
    role: Optional[str] = None
    faction: Optional[Faction] = None
    status: PlayerStatus = PlayerStatus.ALIVE
    is_sheriff: bool = False
    llm_config: Optional[LLMConfig] = None
    personality: Personality = Field(default_factory=Personality)
    thinking_mode: bool = True
    memory: PlayerMemory = Field(default_factory=PlayerMemory)
    death_cause: Optional[list[str]] = None
    death_round: Optional[int] = None

    @property
    def is_alive(self) -> bool:
        return self.status == PlayerStatus.ALIVE