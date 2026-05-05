from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class NightActionSet(BaseModel):
    round: int
    guard_target: Optional[int] = None
    wolf_kill_target: Optional[int] = None
    witch_save_target: Optional[int] = None
    witch_poison_target: Optional[int] = None
    seer_check_target: Optional[int] = None


class DeathCause(str, Enum):
    WOLF_KILL = "wolf_kill"
    WITCH_POISON = "witch_poison"
    VOTE_EXECUTE = "vote_execute"
    HUNTER_SHOOT = "hunter_shoot"


class DeathRecord(BaseModel):
    player_id: int
    causes: list[DeathCause] = Field(default_factory=list)


class PrivateResult(BaseModel):
    player_id: int
    result_type: str
    data: dict[str, Any] = Field(default_factory=dict)


class NightResolutionResult(BaseModel):
    deaths: list[DeathRecord] = Field(default_factory=list)
    death_causes: list[DeathRecord] = Field(default_factory=list)
    private_results: list[PrivateResult] = Field(default_factory=list)
    public_announcement: str = ""


class EventVisibility(str, Enum):
    PUBLIC = "public"
    OBSERVER = "observer"
    FACTION = "faction"
    PRIVATE = "private"


class GameEvent(BaseModel):
    event_id: int
    schema_version: str = "1.0"
    game_id: str = ""
    round: int = 0
    phase: str = ""
    event_type: str = ""
    player_id: Optional[int] = None
    visibility: list[str] = Field(default_factory=lambda: ["public"])
    causation_id: Optional[int] = None
    data: dict[str, Any] = Field(default_factory=dict)
    raw_model_output: Optional[dict[str, Any]] = None
    validated_action: Optional[dict[str, Any]] = None
    state_hash: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class VoteResult(str, Enum):
    MAJORITY = "majority"
    TIE = "tie"
    ALL_ABSTAIN = "all_abstain"


class VoteRecord(BaseModel):
    voter_id: int
    target_id: Optional[int] = None
    is_abstain: bool = False


class VoteSummary(BaseModel):
    round: int
    votes: list[VoteRecord] = Field(default_factory=list)
    result: VoteResult = VoteResult.MAJORITY
    eliminated_id: Optional[int] = None
    tied_ids: list[int] = Field(default_factory=list)


class GameLog(BaseModel):
    schema_version: str = "1.0"
    game_id: str = ""
    config: dict[str, Any] = Field(default_factory=dict)
    day_log: list[GameEvent] = Field(default_factory=list)
    night_log: list[GameEvent] = Field(default_factory=list)
    observer_log: list[GameEvent] = Field(default_factory=list)
    private_events: list[GameEvent] = Field(default_factory=list)
    result: Optional[dict[str, Any]] = None
    mvp: Optional[dict[str, Any]] = None