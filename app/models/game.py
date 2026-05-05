from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, Field

from app.models.player import Player
from app.models.role import Faction


class GameConfig(BaseModel):
    player_count: int = 9
    roles_config: str = "classic"
    rules_config: str = "classic"
    enable_sheriff: bool = True
    enable_last_words: bool = True
    role_assignments: Optional[dict[int, str]] = None
    player_models: Optional[dict[int, dict]] = None


class GameCreateRequest(BaseModel):
    player_count: int = 9
    roles_config: str = "classic"
    rules_config: str = "classic"
    enable_sheriff: bool = True
    enable_last_words: bool = True
    role_assignments: Optional[dict[int, str]] = None
    player_models: Optional[dict[int, dict]] = None


class Game(BaseModel):
    game_id: str = Field(default_factory=lambda: uuid4().hex)
    config: GameConfig = Field(default_factory=GameConfig)
    current_phase: str = "WAITING"
    round: int = 0
    players: list[Player] = Field(default_factory=list)
    sheriff_id: Optional[int] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    winner: Optional[str] = None
    mvp_player_id: Optional[int] = None
    mvp_reason: Optional[str] = None

    def get_player(self, player_id: int) -> Optional[Player]:
        for p in self.players:
            if p.player_id == player_id:
                return p
        return None

    def get_alive_players(self) -> list[Player]:
        return [p for p in self.players if p.is_alive]

    def get_alive_wolves(self) -> list[Player]:
        return [p for p in self.players if p.is_alive and p.faction == Faction.WOLF]

    def get_alive_villagers(self) -> list[Player]:
        return [p for p in self.players if p.is_alive and p.faction == Faction.VILLAGE]
