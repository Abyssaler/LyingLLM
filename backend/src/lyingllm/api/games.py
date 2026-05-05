"""Game REST API routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from lyingllm.domain.models.game import GameSetupConfig, PlayerSetupConfig, RuntimeConfig
from lyingllm.domain.models.setup import ModelConfig, ReasoningConfig
from lyingllm.services.game_service import get_game_service

router = APIRouter(prefix="/games", tags=["games"])


class _ReasoningConfigIn(BaseModel):
    enabled: bool = False
    effort: str | None = None
    capture: str = "auto"
    show_to_observer: bool = True
    show_to_self: bool = True
    persist_raw_response: bool = True


class _ModelConfigIn(BaseModel):
    model_config = {"populate_by_name": True}
    provider_id: str
    model_id: str
    display_name: str | None = None
    persona: str | None = None
    temperature: float | None = None
    top_p: float | None = None
    max_output_tokens: int = 2000
    timeout_seconds: int = 30
    retry_limit: int = 2
    reasoning: _ReasoningConfigIn = Field(default_factory=_ReasoningConfigIn)


class _PlayerSetupIn(BaseModel):
    model_config = {"populate_by_name": True}
    player_id: int
    display_name: str | None = None
    cfg: _ModelConfigIn | None = Field(default=None, alias="model_config")


class _RuntimeConfigIn(BaseModel):
    max_output_tokens: int = 2000
    timeout_seconds: int = 30
    retry_limit: int = 2


class CreateGameRequest(BaseModel):
    players: list[_PlayerSetupIn]
    runtime: _RuntimeConfigIn | None = None


class GameSummaryOut(BaseModel):
    game_id: str
    phase: str
    round_no: int
    alive_count: int
    death_count: int
    winner: str | None = None


@router.post("")
async def create_game(req: CreateGameRequest) -> dict:
    svc = get_game_service()
    import uuid

    game_id = f"game-{uuid.uuid4().hex[:8]}"

    def _to_mc(m: _ModelConfigIn | None) -> ModelConfig | None:
        if m is None:
            return None
        return ModelConfig(
            provider_id=m.provider_id,
            model_id=m.model_id,
            display_name=m.display_name,
            persona=m.persona,
            temperature=m.temperature,
            top_p=m.top_p,
            max_output_tokens=m.max_output_tokens,
            timeout_seconds=m.timeout_seconds,
            retry_limit=m.retry_limit,
            reasoning=ReasoningConfig(
                enabled=m.reasoning.enabled,
                effort=m.reasoning.effort,  # type: ignore[arg-type]
                capture=m.reasoning.capture,  # type: ignore[arg-type]
                show_to_observer=m.reasoning.show_to_observer,
                show_to_self=m.reasoning.show_to_self,
                persist_raw_response=m.reasoning.persist_raw_response,
            ),
        )

    players = [
        PlayerSetupConfig(
            player_id=p.player_id,
            display_name=p.display_name,
            model_config=_to_mc(p.cfg),
        )
        for p in req.players
    ]
    runtime = (
        RuntimeConfig(
            max_output_tokens=req.runtime.max_output_tokens,
            timeout_seconds=req.runtime.timeout_seconds,
            retry_limit=req.runtime.retry_limit,
        )
        if req.runtime
        else None
    )
    setup = GameSetupConfig(players=players, runtime=runtime)
    svc.create(game_id, setup)
    return {"game_id": game_id}


@router.post("/{game_id}/start")
async def start_game(game_id: str) -> dict:
    svc = get_game_service()
    runner = svc.get(game_id)
    if runner is None:
        raise HTTPException(status_code=404, detail="Game not found")
    svc.start_game(game_id)
    return {"status": "started"}


@router.post("/{game_id}/step")
async def step_game(game_id: str) -> dict:
    svc = get_game_service()
    runner = svc.get(game_id)
    if runner is None:
        raise HTTPException(status_code=404, detail="Game not found")
    ended = await runner.step()
    svc.notify(game_id)
    return {"ended": ended}


@router.get("")
async def list_games() -> list[dict]:
    svc = get_game_service()
    return svc.list_all()


@router.get("/{game_id}")
async def get_game(game_id: str) -> dict:
    svc = get_game_service()
    runner = svc.get(game_id)
    if runner is None:
        raise HTTPException(status_code=404, detail="Game not found")
    s = runner.state
    winner = None
    if s.phase.value == "game_end":
        end_events = [e for e in runner.events.all_events() if e.event_type == "game_end"]
        if end_events:
            winner = end_events[0].data.get("winner")
    return {
        "game_id": s.game_id,
        "phase": s.phase.value,
        "round_no": s.round_no,
        "alive_count": len(s.alive_players),
        "death_count": sum(1 for p in s.players if not p.alive),
        "winner": winner,
        "players": [
            {
                "id": p.id,
                "role": p.role.value,
                "faction": p.faction.value,
                "alive": p.alive,
                "is_sheriff": p.is_sheriff,
            }
            for p in s.players
        ],
    }


@router.get("/{game_id}/events")
async def get_events(game_id: str, after_id: int = 0) -> list[dict]:
    svc = get_game_service()
    runner = svc.get(game_id)
    if runner is None:
        raise HTTPException(status_code=404, detail="Game not found")
    events = runner.events.after(after_id)
    return [_event_to_dict(e) for e in events]


@router.get("/{game_id}/log")
async def get_log(game_id: str) -> list[dict]:
    svc = get_game_service()
    runner = svc.get(game_id)
    if runner is None:
        raise HTTPException(status_code=404, detail="Game not found")
    return [_event_to_dict(e) for e in runner.events.observer_view()]


def _event_to_dict(e) -> dict:
    return {
        "event_id": e.event_id,
        "game_id": e.game_id,
        "round_no": e.round_no,
        "phase": e.phase.value,
        "event_type": e.event_type,
        "player_id": e.player_id,
        "visibility": e.visibility,
        "data": e.data,
        "timestamp": e.timestamp,
    }
